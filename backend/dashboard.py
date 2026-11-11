"""Report semantics backed by editable matrices and a versioned local catalog."""
import json
import re
from zipfile import BadZipFile

from . import store
from .catalog_audit import CatalogAudit
from .matrices import OWNER, SOURCE, archive_references, atomic_json, for_day, read_matrices
from .parser import normalized
from .supplements import load_all

INKIA = {'KALLPA', 'ORAZUL', 'KONDU', 'JOYA SOLAR'}


def key(value):
    return re.sub(r'[^A-Z0-9]', '', normalized(value))


def company(value):
    n = normalized(value)
    for needle, label in [('KALLPA','KALLPA'), ('ORAZU','ORAZUL'), ('KONDU','KONDU'), ('JOYA SOLAR','JOYA SOLAR'),
                          ('JOYAS','JOYA SOLAR'), ('ENGIE','ENGIE'), ('ORYGEN','ORYGEN'), ('FENIX','FENIX POWER'),
                          ('ENEL GENERACION PIURA','PIURA'), ('STATKRAFT','STATKRAFT')]:
        if needle in n:
            return label
    return str(value or 'Sin empresa identificada').strip()


def category(technology):
    n = normalized(technology)
    for needle, label in [('HIDRO','Hidráulica'), ('HIDRAUL','Hidráulica'), ('TERM','Térmica'), ('EOL','Eólica'), ('SOLAR','Solar')]:
        if needle in n:
            return label
    if n == 'RER INKIA':
        return 'Solar'
    return 'Otras RER' if technology else 'Sin clasificación'


def forms(value):
    roman = {'I':'1','II':'2','III':'3','IV':'4','V':'5','VI':'6'}
    variants = [str(value or ''), re.sub(r'\b(VI|IV|III|II|V|I)\b', lambda m: roman[m[0]], normalized(value))]
    result = set()
    for value in variants:
        n = key(value)
        result.add(n)
        if n.endswith('GAS'):result.add(n[:-3])
        if n.endswith('D2'):result.add(n[:-2])
        if n.endswith('SOLAR'):result.add(n[:-5])
        if n.endswith('CS'):result.add('CS'+n[:-2])
        for prefix in ('CH','CT','CS','CE','PE'):
            if n.startswith(prefix) and len(n) > len(prefix)+3:result.add(n[len(prefix):])
        if n.startswith(('PQEEOLICO','PQEEOLICA')):result.add(n[9:])
    return result


class Resolver:
    def __init__(self, bundle, audit):
        self.bundle, self.audit = bundle, audit
        self.lookup = {key(p['source']): p for p in bundle['plants']}
        self.aliases = {}
        for p in bundle['plants']:
            for alias in forms(p['source']) | forms(p['plant']):
                self.aliases.setdefault(alias, []).append(p)
        for alias, target in bundle['options'].get('generation_aliases', {}).items():
            self.aliases[key(alias)] = [self.lookup[key(target)]]

    def resolve(self, series, hydro_names):
        p = self.lookup.get(key(series['name']))
        if p:
            return p
        matches = {p['source']: p for name in forms(series['name']) for p in self.aliases.get(name, [])}
        candidates = list(matches.values())
        owner = company(series.get('group_label'))
        preferred = [p for p in candidates if company(p['company']) == owner]
        if preferred:candidates = preferred
        cats = {category(p['technology']) for p in candidates}
        if len(cats) == 1:
            techs = {p['technology'] for p in candidates}
            caps = {p['capacity_reference'] for p in candidates}
            names = {p['plant'] for p in candidates}
            owners = {company(p['company']) for p in candidates}
            reference = candidates[0] if len(candidates) == 1 else {}
            return {**reference, 'plant':next(iter(names)) if len(names)==1 else series['name'],
                    'company':next(iter(owners)) if len(owners)==1 else owner,
                    'technology':next(iter(techs)) if len(techs)==1 else next(iter(cats))+' · unidad COES',
                    'capacity_reference':next(iter(caps)) if len(caps)==1 and len(techs)==1 else None,
                    'category':next(iter(cats))}
        binding = self.audit.binding(series, self.lookup, owner)
        if binding:return binding
        name = normalized(series['name'])
        if forms(name) & hydro_names:
            return {'plant':series['name'], 'company':owner, 'technology':'Hidroelectrica · anexo COES',
                    'capacity_reference':None, 'category':'Hidráulica', 'origin':'annex_type'}
        if re.search(r'(?:TG|GT|TV)\s*\d*$',name) or re.match(r'^UTI[_ ]*\d',name):
            return {'plant':series['name'], 'company':owner, 'technology':'Térmica · unidad COES (modo no indicado)',
                    'capacity_reference':None, 'category':'Térmica', 'origin':'unit_type'}
        if series['role'] == 'renewables':
            return {'plant':series['name'], 'company':owner, 'technology':'RER · tipo pendiente de matriz',
                    'capacity_reference':None, 'category':'Otras RER', 'origin':'annex_type'}
        return {}


def commercial_status(series, reference, day, options):
    for record in options.get('commercial_status', []):
        if record['effective_from'] <= day and (
            record.get('coes_code') and str(record['coes_code']) == str(series.get('source_code')) or
            record.get('source') and key(record['source']) == key(reference.get('source'))
        ):
            return record['status']
    return 'sin_retiro_confirmado'


def enrich(data):
    catalog_errors = []
    try:
        bundle = read_matrices()
    except (ValueError, OSError, BadZipFile) as error:
        state_path = store.DATA / 'catalogos' / 'referencias.json'
        if not state_path.exists():raise ValueError(f'CATÁLOGO: {error}') from error
        state = json.loads(state_path.read_text(encoding='utf-8'))
        revision = state.get('active_revision') or state['versions'][-1]['revision']
        bundle = json.loads((store.DATA / 'catalogos' / 'versiones' / (revision+'.json')).read_text(encoding='utf-8'))
        catalog_errors.append(f'Matriz no aplicada: {error}. Se conserva la última revisión válida.')
    history = archive_references(bundle)
    audit = CatalogAudit(bundle, history)
    data['supplements'] = load_all()
    resolvers = {}

    def context(day):
        if day not in resolvers:resolvers[day] = Resolver(for_day(bundle, history, day), audit)
        return resolvers[day]

    for v in data['versions']:
        day = v.get('day', '0001-01-01')
        resolver = context(day)
        hydro_data = data['supplements'].get(day, {}).get('daily', {}).get('hydrology', {}).get('data', {})
        hydro_names = set().union(*(forms(p['name']) for p in hydro_data.get('plants', []))) if hydro_data.get('plants') else set()
        seen, matched, count, inferred = set(), 0, 0, 0
        for s in v['series']:
            p = resolver.resolve(s, hydro_names)
            s.update(plant=p.get('plant',s['name']), company=company(p.get('company') or s.get('group_label')),
                     technology=p.get('technology'), capacity=p.get('capacity_reference'),
                     category=p.get('category',category(p.get('technology'))), reference_source=p.get('source'),
                     matrix_file=p.get('matrix_file'), matrix_row=p.get('matrix_row'), matrix_sha256=p.get('matrix_sha256'),
                     reference_revision=resolver.bundle['revision'])
            s['inkia'] = s['company'] in INKIA
            s['classification_basis'] = p.get('origin','catalog') if p else 'unclassified'
            s['commercial_status'] = commercial_status(s,p,day,resolver.bundle['options'])
            identity = s['source_code'] or key(s['name'])
            s['generation'] = s['role'] in ('dispatch','renewables','cogeneration') and identity not in seen
            if s['generation']:
                seen.add(identity);count += 1;matched += bool(p);inferred += bool(p) and s['classification_basis'] not in ('catalog','coes_code')
                audit.observe(v,s)
        v['catalog_coverage'] = {'classified':matched,'total':count,'unit_type':inferred,'catalog':matched-inferred}
        v['reference_revision'] = resolver.bundle['revision']

    for day, extra in data['supplements'].items():
        resolver = context(day)
        units = {u['urs']:u for u in resolver.bundle['units']}
        for rsf in extra.get('reserves',{}).values():
            for u in rsf['units']:
                ref = units.get(u['urs']) or units.get(u['urs'].replace('KAL-003','KALL-003')) or {}
                u.update(name=ref.get('name',u['urs']), company=company(ref.get('company')), matrix_file=ref.get('matrix_file'))
                u['inkia'] = u['company'] in INKIA
                audit.supplement('URS',u['urs'],day,company=u['company'],mapped=bool(ref))
        for kind in ('maintenance','restrictions'):
            for r in extra.get('daily',{}).get(kind,{}).get('data',[]):
                r['company_canonical'] = company(r['company']);r['inkia'] = r['company_canonical'] in INKIA
        hydro = resolver.bundle['hydrology']
        h = extra.get('daily',{}).get('hydrology',{}).get('data',{})
        h['reference_plants'] = hydro_totals(h.get('plants',[]),hydro)
        for plant in h['reference_plants']:
            canonical = resolver.lookup.get(key(plant['name']))
            if canonical:
                plant['display'] = canonical['plant']
        h['inkia_plants'] = [p for p in h['reference_plants'] if p['inkia']]
        hydro_lookup = {key(name):r for r in hydro for name in [r[SOURCE], *r['annex_names']]}
        for plant in h.get('plants',[]):
            ref = hydro_lookup.get(key(plant['name']),{})
            p = resolver.lookup.get(key(plant['name']),{})
            plant['company'] = company(ref.get(OWNER) or p.get('company'));plant['inkia'] = plant['company'] in INKIA
            whole = bool(ref) and (len(ref['annex_names'])==1 or key(plant['name'])==key(ref[SOURCE]))
            plant['qmax'] = ref.get('Qturb max') if whole else None
            plant['factor'] = plant['turbined']/plant['qmax'] if plant['qmax'] and plant['turbined'] is not None else None
        reservoirs = {key(r['Nombre_Anexo_Hidrologia']):r for r in hydro}
        for r in h.get('reservoirs',[]):
            ref = reservoirs.get(key(r['name']),{})
            r['company'] = company(ref.get(OWNER));r['inkia'] = r['company'] in INKIA
            r['linked_plant'] = ref.get('Nombre_Central_Dashboard')
            audit.supplement('embalse',r['name'],day,company=r['company'],mapped=bool(ref))
    data['catalog'] = audit.finish(data)
    data['catalog']['errors'] = catalog_errors
    for error in catalog_errors:
        data['catalog']['alerts'].append({'kind':'matriz_no_aplicada','asset':'Matrices del catálogo','day':'',
                                         'message':error,'action':'Corregir el Excel y ejecutar nuevamente el script.',
                                         'severity':'warning','automatic':False,'details':''})
    data['catalog']['pending'] += len(catalog_errors)
    atomic_json(store.DATA/'catalogos'/'revision_actual.json',data['catalog'])
    data['report'] = {'name':'Resumen ejecutivo RDO · matrices del usuario','pages':9,'measures_reviewed':42,
                     'catalog_reference_day':'matrices '+bundle['revision'][:8],
                     'methodology':[
                         'La demanda se lee de Demanda COES; generación y demanda son variables distintas.',
                         'Energía = suma de MW publicados × 0,5 / 1000. Se conservan los intervalos no publicados y vacíos.',
                         'Los cogeneradores repetidos se deduplican por código COES. Los no integrantes quedan fuera del total COES.',
                         'Tecnologías y capacidades instaladas proceden de las matrices editables del usuario; potencia efectiva, eficiencia y Qmáx. corresponden a la matriz hidráulica. No se sustituyen unas magnitudes por otras.',
                         'Los factores requieren referencias para todas las unidades del grupo. Las referencias faltantes se advierten, sin inventar parámetros.',
                         'Los cambios de nombre solo se vinculan automáticamente por código COES estable, empresa coherente y referencia inequívoca. Las coincidencias ambiguas quedan por revisar.',
                         'Las reservas se presentan como medias y máximos MW. Su participación usa asignación acumulada frente al total del sistema.',
                         'Hidrología contiene caudales y extremos diarios de volumen; no se interpola una curva horaria ausente en COES.',
                         'Los grupos hidráulicos se suman una vez por central. Falta de un grupo esperado impide calcular un factor parcial.',
                         'La ausencia en un PDO o un despacho cero no prueban retiro comercial. Los retiros requieren fecha y evidencia en catalogos/ajustes.json.',
                         'Hidrología, RPF e intervenciones son diarios; RSF usa el anexo propio del reprograma cuando está disponible.',
                         'El análisis eléctrico muestra resultados publicados. El HTML no ejecuta simulaciones de red.',
                         'El botón Refrescar página relee el HTML ya generado. Para descargar nuevos programas debe ejecutarse actualizar_base.py.'
                     ]}
    return data


def hydro_totals(plants, references):
    by_name = {key(p['name']):p for p in plants}
    result = []
    for ref in references:
        name = ref[SOURCE]
        direct = by_name.get(key(name))
        members = [direct] if direct else [by_name[key(n)] for n in ref['annex_names'] if key(n) in by_name]
        if not members:continue
        complete = bool(direct) or len(members)==len(ref['annex_names'])
        owner = company(ref[OWNER])
        row = {'name':name,'display':ref.get('Nombre_Central_Dashboard',name),'company':owner,'inkia':owner in INKIA,
               'source_units':'; '.join(p['name'] for p in members),'complete_units':complete,'qmax':ref['Qturb max'],
               'matrix_file':ref.get('matrix_file'),'matrix_row':ref.get('matrix_row')}
        for field in ('natural','inflow','turbined','spilled'):
            values = [p.get(field) for p in members]
            row[field] = sum(values) if complete and all(v is not None for v in values) else None
        row['factor'] = row['turbined']/row['qmax'] if row['turbined'] is not None and row['qmax'] else None
        result.append(row)
    return result
