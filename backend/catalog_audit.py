"""Persistent discovery, conservative code-based aliases and catalog warnings."""
from datetime import datetime, timezone
import hashlib
import json

from . import store
from .matrices import atomic_json, identity


def asset_id(series):
    code = str(series.get('source_code') or '')
    return 'GEN:' + code if code.isdigit() and int(code) > 0 else 'GEN:name:' + identity(series['name'])


class CatalogAudit:
    def __init__(self, bundle, history):
        self.folder = store.DATA / 'catalogos'
        self.path = self.folder / 'inventario.json'
        self.state = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'assets': {}, 'events': []}
        self.assets = self.state['assets']
        self.events = {r['id']: r for r in self.state['events']}
        self.new_events = []
        self.bundle, self.history = bundle, history

    def event(self, kind, asset, day, message, action, *, severity='warning', automatic=False, details='', token=''):
        identifier = hashlib.sha256(json.dumps([kind, asset, day, token], ensure_ascii=False).encode()).hexdigest()[:24]
        if identifier not in self.events:
            row = {'id': identifier, 'kind': kind, 'asset': asset, 'day': day, 'message': message,
                   'action': action, 'severity': severity, 'automatic': automatic, 'details': details,
                   'detected_at': datetime.now(timezone.utc).isoformat()}
            self.events[identifier] = row
            self.new_events.append(row)
        return self.events[identifier]

    def binding(self, series, lookup, company):
        identifier = asset_id(series)
        old = self.assets.get(identifier, {})
        if not identifier.removeprefix('GEN:').isdigit():
            return None
        reference = lookup.get(identity(old.get('reference_source')))
        same_owner = identity(old.get('raw_owner')) == identity(series.get('group_label')) or old.get('company') == company
        if not reference or not same_owner or old.get('review_required'):
            return None
        return {**reference, 'origin': 'coes_code'}

    def observe(self, version, series):
        day = version.get('day')
        if not day or not version.get('current', True) or not series.get('generation'):
            return
        identifier = asset_id(series)
        old = self.assets.get(identifier)
        names = list(old.get('names', [])) if old else []
        if series['name'] not in names:
            if old and series.get('classification_basis') == 'coes_code':
                self.event('nombre_actualizado', series['name'], day,
                           f"El código COES {series['source_code']} cambió de nombre: {names[-1]} → {series['name']}.",
                           'Alias incorporado automáticamente por código COES y empresa coincidentes.',
                           severity='info', automatic=True, token=identity(series['name']))
            elif old:
                same = bool(series.get('reference_source')) and identity(old.get('reference_source')) == identity(series['reference_source']) and old.get('company') == series['company']
                self.event('nombre_actualizado' if same else 'cambio_identidad_revisar', series['name'], day,
                           f"El código COES {series['source_code']} tiene un nombre distinto: {names[-1]} → {series['name']}.",
                           'Correspondencia resuelta con la matriz de la misma referencia.' if same else 'Revisar nombre, empresa y referencia. No se heredan parámetros de una identidad distinta.',
                           severity='info' if same else 'warning', automatic=same, token=identity(series['name']))
            names.append(series['name'])
        if old and day < old['last_seen']:
            old['first_seen'] = min(day, old['first_seen'])
            old['names'] = names
            return
        status = 'fuera_de_operacion_comercial' if series.get('commercial_status') == 'fuera_de_operacion_comercial' else 'observada'
        record = {'id': identifier, 'kind': 'generation', 'code': series.get('source_code'),
                  'name': series['name'], 'display': series['plant'], 'names': names,
                  'company': series['company'], 'raw_owner': series.get('group_label'),
                  'technology': series['technology'], 'category': series['category'],
                  'capacity_reference': series['capacity'], 'reference_source': series.get('reference_source'),
                  'first_seen': min(day, old['first_seen']) if old else day, 'last_seen': day,
                  'status': status, 'review_required': series['classification_basis'] in ('unclassified', 'unit_type', 'annex_type') or not (series['capacity'] is not None and series['capacity'] > 0),
                  'classification_basis': series['classification_basis'], 'source_file': version.get('filename'),
                  'matrix_file': series.get('matrix_file'), 'matrix_row': series.get('matrix_row')}
        self.assets[identifier] = record
        if old and old.get('status') == 'no_observada':
            self.event('reaparicion', series['name'], day,
                       'La unidad volvió a aparecer en un anexo después de una ausencia.',
                       'Estado de observación actualizado; no implica una nueva entrada comercial.',
                       severity='info', automatic=True, token=identifier)
        if old is None:
            self.event('alta_detectada', series['name'], day,
                       f"Unidad incorporada al inventario local: {series['name']} (código {series.get('source_code') or 'sin código'}).",
                       'Se conserva la primera aparición; no representa la fecha de entrada comercial.',
                       severity='info', automatic=True, token=identifier)
        if series.get('commercial_status') == 'fuera_de_operacion_comercial' and any((n or 0) > .01 for n in series.get('values', [])):
            self.event('despacho_tras_retiro', series['name'], day,
                       'El anexo publica despacho positivo después del retiro comercial registrado.',
                       'Revisar la vigencia del estado y su evidencia; los valores COES se conservan.', token=identifier)

    def supplement(self, kind, name, day, *, company='', mapped=True):
        identifier = kind + ':' + identity(name)
        old = self.assets.get(identifier, {})
        if old and day < old['last_seen']:
            return
        self.assets[identifier] = {'id': identifier, 'kind': kind, 'code': name, 'name': name, 'display': name,
                                  'company': company, 'first_seen': min(day, old.get('first_seen', day)),
                                  'last_seen': day, 'status': 'observada', 'review_required': not mapped}

    def finish(self, data):
        current = [v for v in data['versions'] if v.get('current', True) and v.get('day')]
        latest_day = max((v['day'] for v in current), default='')
        alerts = []
        for record in self.assets.values():
            for status in self.bundle['options'].get('commercial_status', []):
                same = status.get('coes_code') and str(status['coes_code']) == str(record.get('code')) or status.get('source') and identity(status['source']) == identity(record.get('reference_source'))
                if same and status['effective_from'] <= latest_day:
                    record['status'] = status['status']
        for issue in self.bundle.get('parameter_issues', []):
            alerts.append({'kind':'parametro_de_matriz','asset':issue['asset'],'day':latest_day,
                           'message':issue['message'],'action':f"Revisar {issue['matrix_file']}, fila {issue['matrix_row']}.",
                           'severity':'warning','automatic':False,'details':issue['field']})
        for record in self.assets.values():
            if record['last_seen'] == latest_day and record.get('review_required'):
                kind = record['kind']
                reason = 'Falta una correspondencia en la matriz.'
                if kind == 'generation':
                    reason = 'Revisar tecnología y potencia de referencia.' if not record.get('reference_source') else 'Falta una potencia inequívoca para esta unidad o modo.'
                reservoir = kind == 'embalse'
                alerts.append({'kind': 'embalse_sin_vinculo' if reservoir else 'parametro_pendiente', 'asset': record['name'], 'day': latest_day,
                               'message': 'Embalse incorporado sin central vinculada en la matriz.' if reservoir else reason,
                               'action': 'Sus volúmenes y caudales COES están disponibles. Revisa la vinculación solo si corresponde.' if reservoir else 'Unidad incorporada automáticamente; completa o corrige la matriz y ejecuta el script.',
                               'severity': 'info' if reservoir else 'warning', 'automatic': True, 'details': record.get('code') or ''})
        pdo = next((v for v in current if v['day'] == latest_day and v.get('code') == 'PDO' and v.get('structured')), None)
        report = next((r for r in data.get('runs', []) if r['day'] == latest_day), {})
        verified = pdo and report.get('listing_verified') and not report.get('errors') and not report.get('normalization_errors')
        if verified:
            present = {asset_id(s) for s in pdo['series'] if s.get('generation')}
            for record in self.assets.values():
                if record['kind'] == 'generation' and record['last_seen'] < latest_day and record['id'] not in present:
                    if record['status'] != 'fuera_de_operacion_comercial':
                        record['status'] = 'no_observada'
                    row = self.event('ausencia_en_PDO', record['name'], latest_day,
                                     f"No aparece en el PDO verificado de {latest_day}; última aparición {record['last_seen']}.",
                                     'Verificar cambio de nombre, alcance o retiro con una fuente oficial. No se da de baja automáticamente.',
                                     token=record['id'])
                    alerts.append(row)
        # Record each parameter revision once, even when exporting offline repeatedly.
        for revision in self.history['versions']:
            for change in revision.get('changes', []):
                row = self.event('matriz_actualizada', change['asset'], revision['effective_from'],
                                 f"Matriz actualizada: {change['field']}.",
                                 'Parámetro incorporado desde el Excel; revisión anterior conservada.',
                                 severity='info', automatic=True, details=json.dumps(change, ensure_ascii=False),
                                 token=revision['revision'] + change['domain'] + change['asset'] + change['field'])
                if revision['revision'] == self.bundle['revision']:
                    alerts.append(row)
        alerts.extend(r for r in self.events.values() if r['day'] == latest_day and r['kind'] in ('nombre_actualizado', 'cambio_identidad_revisar', 'despacho_tras_retiro'))
        self.state['events'] = list(self.events.values())
        atomic_json(self.path, self.state)
        if self.new_events:
            self.folder.mkdir(parents=True, exist_ok=True)
            with (self.folder / 'cambios.jsonl').open('a', encoding='utf-8') as file:
                for row in self.new_events:
                    file.write(json.dumps(row, ensure_ascii=False) + '\n')
        result = {'revision': self.bundle['revision'], 'sources': self.bundle['sources'], 'latest_operation_day':latest_day,
                  'references': {'plants': self.bundle['plants'], 'hydrology': self.bundle['hydrology'], 'units': self.bundle['units']},
                  'history': self.history['versions'], 'inventory': list(self.assets.values()),
                  'alerts': alerts, 'events': list(self.events.values()),
                  'pending': sum(r['severity'] == 'warning' for r in alerts)}
        atomic_json(self.folder / 'revision_actual.json', result)
        return result
