"""Read the user's editable reference matrices; archive every revision locally."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil

from openpyxl import load_workbook

from . import store
from .parser import number, normalized

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'Central_Nombre origen en Consolidado_RDO'
DISPLAY = 'Nombre_Central_Dashboard'
OWNER = 'Nombre_Empresa_Dashboard'


def identity(value):
    return ''.join(c for c in normalized(value) if c.isalnum())


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def read_matrices(folder=None, adjustments=None):
    folder = Path(folder or ROOT / 'catalogos' / 'fuentes')
    adjustments = Path(adjustments or ROOT / 'catalogos' / 'ajustes.json')
    options = json.loads(adjustments.read_text(encoding='utf-8'))
    plants, hydro, units, sources, seen, issues = [], [], [], [], set(), []
    for path in sorted(folder.glob('*.xlsx')):
        if path.name.startswith('~$'):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        w = load_workbook(path, data_only=True, read_only=True)
        try:
            for sheet in w:
                rows = list(sheet.values)
                if not rows:
                    continue
                headers = [str(c).strip() if c is not None else '' for c in rows[0]]
                if {'URS', 'UNIDAD/CENTRAL', 'EMPRESA'} <= set(headers):
                    kind, required = 'urs', ('URS', 'UNIDAD/CENTRAL', 'EMPRESA')
                elif {SOURCE, DISPLAY, OWNER, 'Nombre_Anexo_Hidrologia', 'Qturb max'} <= set(headers):
                    kind, required = 'hydrology', (SOURCE, DISPLAY, OWNER, 'Nombre_Anexo_Hidrologia')
                elif {SOURCE, DISPLAY, OWNER, 'Tecnologia', 'Capacidad Instalada (MW)'} <= set(headers):
                    kind, required = 'generation', (SOURCE, DISPLAY, OWNER, 'Tecnologia')
                else:
                    raise ValueError(f'Matriz no reconocida: {path.name}, hoja {sheet.title}. Revisa sus encabezados.')
                count = 0
                for rownum, row in enumerate(rows[1:], 2):
                    if all(c is None for c in row):
                        continue
                    r = dict(zip(headers, row))
                    if any(not str(r.get(k) or '').strip() for k in required):
                        raise ValueError(f'{path.name}, fila {rownum}: faltan campos obligatorios ({", ".join(required)}).')
                    key = (kind, identity(r['URS'] if kind == 'urs' else r[SOURCE]))
                    if key in seen:
                        raise ValueError(f'{path.name}, fila {rownum}: referencia duplicada {key[1]}.')
                    seen.add(key)
                    provenance = {'matrix_file': path.name, 'matrix_sheet': sheet.title, 'matrix_row': rownum, 'matrix_sha256': digest}
                    if kind == 'generation':
                        cap = number(r['Capacidad Instalada (MW)'])
                        if cap is not None and cap < 0:
                            raise ValueError(f'{path.name}, fila {rownum}: capacidad instalada negativa.')
                        if cap is None or cap == 0:
                            issues.append({'asset':str(r[SOURCE]),'field':'Capacidad Instalada (MW)',
                                           'message':'Capacidad vacía o cero en la matriz; no se calcula factor ni se infiere retiro.', **provenance})
                        plants.append({'source': str(r[SOURCE]).strip(), 'plant': str(r[DISPLAY]).strip(),
                                       'company': str(r[OWNER]).strip(), 'technology': str(r['Tecnologia']).strip(),
                                       'capacity_reference': cap, 'capacity_kind': 'Capacidad Instalada (MW)', **provenance})
                    elif kind == 'hydrology':
                        qmax, power, efficiency = number(r['Qturb max']), number(r.get('Potencia Efectiva (MW)')), number(r.get('Eficiencia'))
                        if qmax is None or qmax <= 0 or power is None or power <= 0 or efficiency is None or efficiency <= 0:
                            raise ValueError(f'{path.name}, fila {rownum}: revisa potencia, eficiencia y Qturb max; guarda el Excel con valores calculados.')
                        if abs(power / efficiency - qmax) > max(.001, qmax * .001):
                            raise ValueError(f'{path.name}, fila {rownum}: Qturb max no coincide con potencia / eficiencia.')
                        r = {k: v for k, v in r.items() if k}
                        r['annex_names'] = options.get('hydrology_groups', {}).get(r[SOURCE], [str(r['Nombre_Anexo_Hidrologia']).strip()])
                        # Reservoir names and generator names are different domains.
                        r['annex_names'] = list(dict.fromkeys(r['annex_names']))
                        hydro.append({**r, **provenance})
                    else:
                        units.append({'urs': str(r['URS']).strip(), 'name': str(r['UNIDAD/CENTRAL']).strip(),
                                      'company': str(r['EMPRESA']).strip(), **provenance})
                    count += 1
                sources.append({'file': path.name, 'sheet': sheet.title, 'kind': kind, 'rows': count, 'sha256': digest})
        finally:
            w.close()
    if not plants or not hydro or not units:
        raise ValueError('Se necesitan matrices de generación, hidrología y URS en catalogos/fuentes.')
    known = {identity(p['source']) for p in plants}
    generation = {identity(p['source']): p for p in plants}
    for h in hydro:
        g = generation.get(identity(h[SOURCE]))
        if g and identity(g['plant']) != identity(h[DISPLAY]):
            issues.append({'asset': h[SOURCE], 'field': DISPLAY,
                           'message': f"Nombre diferente entre matrices: hidráulica «{h[DISPLAY]}», generación «{g['plant']}». La gráfica usa el nombre de generación para esta referencia exacta.",
                           **{k:v for k,v in h.items() if k.startswith('matrix_')}})
    for alias, target in options.get('generation_aliases', {}).items():
        if identity(target) not in known:
            raise ValueError(f'El alias {alias} apunta a una referencia inexistente: {target}.')
    for record in options.get('commercial_status', []):
        if record.get('status') not in ('en_operacion', 'fuera_de_operacion_comercial') or not record.get('evidence') or not record.get('effective_from') or not (record.get('coes_code') or record.get('source')):
            raise ValueError('Los estados comerciales requieren código o referencia, status, effective_from y evidence.')
        date.fromisoformat(record['effective_from'])
    bundle = {'plants': plants, 'hydrology': hydro, 'units': units, 'sources': sources, 'options': options, 'parameter_issues':issues}
    revision_data = {k:v for k,v in bundle.items() if k != 'parameter_issues'}
    bundle['revision'] = hashlib.sha256(json.dumps(revision_data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return bundle


def reference_changes(before, after):
    changes = []
    for domain, name in [('plants', 'source'), ('hydrology', SOURCE), ('units', 'urs')]:
        old = {identity(r[name]): r for r in before.get(domain, [])}
        new = {identity(r[name]): r for r in after.get(domain, [])}
        for key in sorted(old.keys() | new.keys()):
            a, b = old.get(key), new.get(key)
            if a is None or b is None:
                changes.append({'domain': domain, 'asset': (b or a)[name], 'field': 'referencia', 'before': 'Presente' if a else None, 'after': 'Presente' if b else None})
                continue
            for field in sorted(a.keys() | b.keys()):
                if field.startswith('matrix_'):
                    continue
                if a.get(field) != b.get(field):
                    changes.append({'domain': domain, 'asset': b[name], 'field': field, 'before': a.get(field), 'after': b.get(field)})
    if before.get('options') != after.get('options'):
        changes.append({'domain': 'options', 'asset': 'Ajustes del catálogo', 'field': 'options', 'before': before.get('options'), 'after': after.get('options')})
    return changes


def archive_references(bundle, source_folder=None):
    """Version parameters independently of operating facts; preserve historical days."""
    folder = store.DATA / 'catalogos'
    state_path = folder / 'referencias.json'
    previous = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {'versions': []}
    revision = bundle['revision']
    today = datetime.now(timezone(timedelta(hours=-5))).date().isoformat()
    path = folder / 'versiones' / (revision + '.json')
    known = previous.get('active_revision') == revision
    changes = []
    if not known:
        if previous['versions']:
            before = json.loads((folder / 'versiones' / (previous['versions'][-1]['revision'] + '.json')).read_text(encoding='utf-8'))
            changes = reference_changes(before, bundle)
        effective = bundle['options'].get('effective_from') or (today if previous['versions'] else '0001-01-01')
        date.fromisoformat(effective)
        previous['versions'].append({'revision': revision, 'effective_from': effective, 'imported_at': datetime.now(timezone.utc).isoformat(), 'changes': changes})
        atomic_json(path, bundle)
        for source in bundle['sources']:
            original = Path(source_folder or ROOT / 'catalogos' / 'fuentes') / source['file']
            target = folder / 'fuentes' / source['sha256'] / source['file']
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copyfile(original, target)
        atomic_json(state_path, previous)
    previous['active_revision'] = revision
    atomic_json(state_path, previous)
    return previous


def for_day(bundle, history, day):
    candidates = [(i, r) for i, r in enumerate(history['versions']) if r['effective_from'] <= day]
    record = max(candidates, key=lambda item: (item[1]['effective_from'], item[0]))[1] if candidates else history['versions'][0]
    if record['revision'] == bundle['revision']:
        return bundle
    return json.loads((store.DATA / 'catalogos' / 'versiones' / (record['revision'] + '.json')).read_text(encoding='utf-8'))
