"""Report semantics, classification and conservative generator de-duplication."""
import json
import re
from pathlib import Path

from .parser import normalized
from .supplements import load_all

ASSETS = Path(__file__).parent / "assets"
INKIA = {"KALLPA", "ORAZUL", "KONDU", "JOYA SOLAR"}


def key(value):
    return re.sub(r"[^A-Z0-9]", "", normalized(value))


def company(value):
    n=normalized(value)
    if "KALLPA" in n:return "KALLPA"
    if "ORAZU" in n:return "ORAZUL"
    if "KONDU" in n:return "KONDU"
    if "JOYA SOLAR" in n:return "JOYA SOLAR"
    for needle,label in [('JOYAS','JOYA SOLAR'),('ENGIE','ENGIE'),('ORYGEN','ORYGEN'),('FENIX','FENIX POWER'),('ENEL GENERACION PIURA','PIURA'),('STATKRAFT','STATKRAFT')]:
        if needle in n:return label
    return str(value or "Sin empresa identificada").strip()


def category(technology):
    n=normalized(technology)
    if "HIDRO" in n:return "Hidráulica"
    if "TERM" in n:return "Térmica"
    if "EOL" in n:return "Eólica"
    if "SOLAR" in n or n=="RER INKIA":return "Solar"
    return "Otras RER" if technology else "Sin clasificación"


def enrich(data):
    catalog=json.loads((ASSETS/'plant_catalog.json').read_text(encoding='utf-8'))
    lookup={key(p['source']):p for p in catalog['plants']}
    aliases={}
    def forms(value):
        n=key(value); result={n}
        if n.endswith('GAS'):result.add(n[:-3])
        if n.endswith('D2'):result.add(n[:-2])
        if n.endswith('SOLAR'):result.add(n[:-5])
        if n.endswith('CS'):result.add('CS'+n[:-2])
        for prefix in ('CH','CT','CS','CE','PE'):
            if n.startswith(prefix) and len(n)>len(prefix)+3:result.add(n[len(prefix):])
        if n.startswith('PQEEOLICO'):result.add(n[9:])
        if n.startswith('PQEEOLICA'):result.add(n[9:])
        return result
    for p in catalog['plants']:
        for alias in forms(p['source'])|forms(p['plant']):aliases.setdefault(alias,[]).append(p)
    def resolve(s):
        p=lookup.get(key(s['name']))
        if p:return p
        matches={p['source']:p for name in forms(s['name']) for p in aliases.get(name,[])}
        candidates=list(matches.values())
        owner=company(s.get('group_label'))
        preferred=[p for p in candidates if company(p['company'])==owner]
        if preferred:candidates=preferred
        cats={category(p['technology']) for p in candidates}
        if len(cats)!=1:
            n=normalized(s['name'])
            if re.search(r'(?:TG|GT|TV)\s*\d*$',n) or re.match(r'^UTI[_ ]*\d',n):
                return {'plant':s['name'],'company':owner,'technology':'Térmica · unidad COES (modo no indicado)','capacity_reference':None,'category':'Térmica','origin':'unit_type'}
            return {}
        techs={p['technology'] for p in candidates};caps={p['capacity_reference'] for p in candidates};names={p['plant'] for p in candidates};companies={company(p['company']) for p in candidates}
        tech=next(iter(techs)) if len(techs)==1 else next(iter(cats))+' · unidad COES'
        return {'plant':next(iter(names)) if len(names)==1 else s['name'],'company':next(iter(companies)) if len(companies)==1 else owner,
                'technology':tech,'capacity_reference':next(iter(caps)) if len(caps)==1 and len(techs)==1 else None,'category':next(iter(cats))}
    for v in data['versions']:
        seen=set(); matched=0; generators=0; inferred=0
        for s in v['series']:
            p=resolve(s)
            s.update(plant=p.get('plant',s['name']),company=company(p.get('company') or s.get('group_label')),technology=p.get('technology'),capacity=p.get('capacity_reference'),category=p.get('category',category(p.get('technology'))))
            s['inkia']=s['company'] in INKIA
            s['classification_basis']=p.get('origin','catalog') if p else 'unclassified'
            # Several qualified cogenerators appear both in renewable and cogeneration blocks.
            # Positive source codes identify the same physical unit. Non-members are not COES totals.
            identity=s['source_code'] or key(s['name'])
            s['generation']=s['role'] in ('dispatch','renewables','cogeneration') and identity not in seen
            if s['generation']:
                seen.add(identity);generators+=1;matched+=bool(p);inferred+=s['classification_basis']=='unit_type'
        v['catalog_coverage']={'classified':matched,'total':generators,'unit_type':inferred,'catalog':matched-inferred}
    data['supplements']=load_all()
    urs=json.loads((ASSETS/'urs_catalog.json').read_text(encoding='utf-8'))['units']
    units={r['urs']:r for r in urs}
    hydro=json.loads((ASSETS/'hydro_catalog.json').read_text(encoding='utf-8'))['plants']
    hydro_lookup={key(name):r for r in hydro for name in [r['Central_Nombre origen en Consolidado_RDO'], *r['annex_names']]}
    for day,extra in data['supplements'].items():
        for code,rsf in extra.get('reserves',{}).items():
            for u in rsf['units']:
                ref=units.get(u['urs']) or units.get(u['urs'].replace('KALL-','KAL-')) or {}
                u['name']=ref.get('name',u['urs']);u['company']=company(ref.get('company'))
                u['inkia']=u['company'] in INKIA
        for name in ('maintenance','restrictions'):
            for r in extra.get('daily',{}).get(name,{}).get('data',[]):
                r['company_canonical']=company(r['company']);r['inkia']=r['company_canonical'] in INKIA
        h=extra.get('daily',{}).get('hydrology',{}).get('data',{})
        for plant in h.get('plants',[]):
            p=lookup.get(key(plant['name']),{});ref=hydro_lookup.get(key(plant['name']),{})
            plant['company']=company(ref.get('Nombre_Empresa_Dashboard') or p.get('company'));plant['inkia']=plant['company'] in INKIA
            # The technical Qmax belongs to the whole plant, never to each G1/G2/G3.
            whole_plant=bool(ref) and (len(ref['annex_names'])==1 or key(plant['name'])==key(ref['Central_Nombre origen en Consolidado_RDO']))
            plant['qmax']=ref.get('Qturb max') if whole_plant else None
            plant['factor']=plant['turbined']/plant['qmax'] if plant['qmax'] and plant['turbined'] is not None else None
        h['inkia_plants']=hydro_totals(h.get('plants',[]),hydro)
        reservoirs={key(r['Nombre_Anexo_Hidrologia']):r for r in hydro}
        for r in h.get('reservoirs',[]):
            p=reservoirs.get(key(r['name']),{});r['company']=company(p.get('Nombre_Empresa_Dashboard'));r['inkia']=r['company'] in INKIA
    data['report']={'name':'Resumen ejecutivo RDO · versión beta','pages':9,'measures_reviewed':42,'catalog_reference_day':catalog['reference_day'],
                    'theme':{'magenta':'#A62E78','deep':'#79144F','purple':'#682888','orange':'#E86820','solar':'#F8A018','cyan':'#3599B8'},
                    'methodology':[
                        'La demanda se lee de la columna Demanda COES, no de la suma de generación que el DAX del PBIX llama Demanda PDO.',
                        'Energía = suma de MW publicados en la ventana elegida × 0,5 / 1000. Las horas no publicadas no se rellenan.',
                        'Los cogeneradores repetidos se deduplican por código COES. Los no integrantes no se suman al total COES.',
                        'Potencia de referencia y tecnología proceden del catálogo beta del PBIX; no constituyen una nueva certificación de potencia efectiva.',
                        'El factor de uso se calcula solo si todas las unidades del grupo tienen potencia de referencia. Las unidades sin clasificación permanecen en el resumen y en Variaciones, sin asignarlas a una tecnología arbitraria.',
                        'Los alias solo se unen cuando son inequívocos. Los nombres explícitos TG/GT/TV/UTI se identifican como unidades térmicas sin inferir combustible, ciclo ni potencia.',
                        'Las reservas UP/DOWN se muestran como potencia media y máxima en MW; su suma por intervalos no se etiqueta como potencia instantánea.',
                        'El anexo de hidrología contiene extremos diarios de volumen. No se interpola una curva de 48 medias horas.',
                        'Los caudales por grupos G1/G2/G3 se suman una sola vez por central y se comparan con su Qmáx. total. Si falta un grupo esperado, no se calcula un factor parcial.',
                        'Hidrología, RPF e intervenciones son anexos diarios. La RSF usa su anexo específico del reprograma si existe; cualquier uso del PDO se identifica.',
                        'El análisis eléctrico presenta los resultados publicados por COES. El HTML no ejecuta simulaciones de red.'
                    ]}
    return data


def hydro_totals(plants, references):
    """Aggregate an explicit group roster, preferring a published plant total."""
    by_name={key(p['name']):p for p in plants}
    result=[]
    for ref in references:
        name=ref['Central_Nombre origen en Consolidado_RDO']
        direct=by_name.get(key(name))
        members=[direct] if direct else [by_name[key(n)] for n in ref['annex_names'] if key(n) in by_name]
        if not members:continue
        complete=bool(direct) or len(members)==len(ref['annex_names'])
        row={'name':name,'company':company(ref['Nombre_Empresa_Dashboard']),'inkia':True,
             'source_units':'; '.join(p['name'] for p in members),'complete_units':complete,'qmax':ref['Qturb max']}
        for field in ('natural','inflow','turbined','spilled'):
            values=[p.get(field) for p in members]
            row[field]=sum(values) if complete and all(v is not None for v in values) else None
        row['factor']=row['turbined']/row['qmax'] if row['turbined'] is not None and row['qmax'] else None
        result.append(row)
    return result
