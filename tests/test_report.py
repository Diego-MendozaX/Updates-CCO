"""Source semantics and failure recovery for the standalone RDO report."""
from io import BytesIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import httpx
from openpyxl import Workbook, load_workbook

from backend import store
from backend.dashboard import enrich, hydro_totals
from backend.pipeline import excel_export
from backend.supplements import (
    parse_electrical, parse_hydrology, parse_maintenance, parse_restrictions,
    parse_rpf, parse_rsf, update,
)


def raw_book(book):
    out = BytesIO()
    book.save(out)
    return out.getvalue()


def archive(name, raw):
    out = BytesIO()
    with ZipFile(out, 'w') as z:
        z.writestr(name, raw)
    return out.getvalue()


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = store.DATA
        store.DATA = Path(self.tmp.name)

    def tearDown(self):
        store.DATA = self.original
        self.tmp.cleanup()

    def test_hydrology_preserves_daily_endpoints_and_zero_flow(self):
        w = Workbook()
        s = w.active
        s.title = 'Embalses'
        s.append([])
        for i, value in enumerate(['CERRO DEL AGUILA', 3.1, 3.2, None, 0, 20, 0, 0, 0], 1):
            s.cell(10, i, value)
        s = w.create_sheet('Generadores')
        for i, value in enumerate(['CERRO DEL AGUILA', 0, 20, 19, 0], 1):
            s.cell(10, i, value)
        result = parse_hydrology(raw_book(w))
        self.assertEqual(result['frequency'], 'daily_endpoints')
        self.assertEqual(result['reservoirs'][0]['final'], 3.2)
        self.assertEqual(result['plants'][0]['natural'], 0)
        self.assertEqual(result['plants'][0]['turbined'], 19)
        self.assertNotIn('hourly', result)

    def test_reserves_align_slots_keep_missing_and_validate_date(self):
        w = Workbook()
        w.remove(w.active)
        for direction in ['Up', 'Down']:
            s = w.create_sheet('2026-11-11 - ' + direction)
            s.cell(3, 2, 'URS-TEST')
            s.cell(4, 1, '23:59')
            s.cell(4, 2, 15 if direction == 'Up' else -7)
            s.cell(4, 3, 20 if direction == 'Up' else 12)
        w.create_sheet('Notas')
        raw = raw_book(w)
        result = parse_rsf(raw, '2026-11-11')
        self.assertIsNone(result['units'][0]['up'][0])
        self.assertEqual(result['units'][0]['up'][47], 15)
        self.assertEqual(result['units'][0]['down'][47], 7)
        self.assertEqual(result['totals']['up'][47], 20)
        with self.assertRaisesRegex(ValueError, 'fecha'):
            parse_rsf(raw, '2026-11-03')

    def test_rpf_keeps_dates_percent_and_backup(self):
        w = Workbook()
        s = w.active
        values = [None, 123, '11/11/2026', '08:00', '11/11/2026', '18:00', 'A', 'CENTRAL A', 'B', 'CENTRAL B', 45, 'Si']
        for i, value in enumerate(values, 1):
            s.cell(12, i, value)
        row = parse_rpf(raw_book(w), 'Delegación')[0]
        self.assertEqual((row['from'], row['to'], row['percent'], row['backup']), ('CENTRAL A', 'CENTRAL B', 45, 'Si'))
        self.assertEqual(row['start'], '08:00')

    def test_restriction_header_reading_and_text_preservation(self):
        w = Workbook()
        s = w.active
        s.append(['FECHA', 'INICIO', 'FINAL', 'EMPRESA', 'UBICACIÓN', 'EQUIPO', 'DESCRIPCIÓN'])
        s.append(['11/11/2026', '08:00', '18:00', 'KALLPA', 'CHILCA', 'TG1', 'Límite < 100 MW'])
        row = parse_restrictions(raw_book(w))[0]
        self.assertEqual(row['description'], 'Límite < 100 MW')
        self.assertEqual(row['location'], 'CHILCA')

    def test_interventions_use_equipment_area_and_keep_unknowns(self):
        w = Workbook()
        s = w.active
        s.title = 'MANTTOS'
        for row, code in [(10, 'GEN'), (11, 'LINE'), (12, 'UNKNOWN')]:
            values = [None, row, 'event-' + code, 'KALLPA', 'Location', 'Unit', code, '08:00', '18:00', 'Trabajo', 0, 'F/S', 'No', 'Preventivo']
            for i, value in enumerate(values, 1):
                s.cell(row, i, value)
        s = w.create_sheet('EQUIPOS')
        s.cell(8, 2, 'GEN'); s.cell(8, 10, 'C.H.')
        s.cell(9, 2, 'LINE'); s.cell(9, 10, 'L.T.')
        result = parse_maintenance(archive('Intervenciones_(Agentes).xlsm', raw_book(w)))
        self.assertEqual([r['category'] for r in result], ['Generación F/S', 'Transmisión F/S', 'Otros F/S'])
        self.assertEqual(result[0]['id'], 'event-GEN')

    def test_electrical_extracts_only_explicit_rows_and_keeps_page(self):
        page = SimpleNamespace(extract_text=lambda: 'Contingencia: caso publicado\nL-2201 / L-2202 90% / 115%\nSe recomienda reducir un 20%\nL-9999 revisión narrativa 150%\nL-2203 85,5%\nL-2204 / L-2205 72% 112% 110%')
        with patch('pypdf.PdfReader', return_value=SimpleNamespace(pages=[page])):
            result = parse_electrical(archive('Anexo2_Analisis Electrico_20261111.pdf', b'%PDF-test'))
        self.assertEqual(len(result['loadings']), 3)
        self.assertEqual(result['loadings'][0]['loading'], 115)
        self.assertEqual(result['loadings'][0]['reported'], '90% / 115%')
        self.assertEqual(result['loadings'][1]['page'], 1)
        self.assertEqual(result['loadings'][1]['loading'], 85.5)
        self.assertEqual(result['loadings'][2]['equipment'], 'L-2204 / L-2205')
        self.assertEqual(result['loadings'][2]['loading'], 112)
        self.assertEqual(result['loadings'][2]['reported'], '72% 112% 110%')
        self.assertEqual(result['pdf'], b'%PDF-test')

    def test_generation_deduplicates_components_and_excludes_nonmembers(self):
        def series(name, role, code, owner='KALLPA'):
            return {'name': name, 'role': role, 'source_code': code, 'group_label': owner}
        rows = [series('KALLPA TG1', 'dispatch', '1'), series('SAME', 'renewables', '2'),
                series('SAME', 'cogeneration', '2'), series('TOTAL', 'generation_total', ''),
                series('EXTERNAL', 'non_members', '3'), series('UNKNOWN NEW', 'dispatch', '4'),
                series('NEW TG9', 'dispatch', '5')]
        with patch('backend.dashboard.load_all', return_value={}):
            result = enrich({'versions': [{'series': rows}]})
        self.assertEqual([r['generation'] for r in rows], [True, True, False, False, False, True, True])
        self.assertEqual(rows[0]['category'], 'Térmica')
        self.assertGreater(rows[0]['capacity'], 0)
        self.assertEqual(rows[5]['category'], 'Sin clasificación')
        self.assertIsNone(rows[5]['capacity'])
        self.assertEqual(rows[6]['classification_basis'], 'unit_type')
        self.assertIsNone(rows[6]['capacity'])
        self.assertEqual(result['versions'][0]['catalog_coverage']['total'], 4)

    def test_hydro_groups_share_one_plant_reference_and_require_complete_roster(self):
        ref = {'Central_Nombre origen en Consolidado_RDO': 'PLANT', 'annex_names': ['PLANT G1', 'PLANT G2'],
               'Nombre_Empresa_Dashboard': 'KALLPA', 'Qturb max': 100}
        groups = [{'name': 'PLANT G1', 'turbined': 20}, {'name': 'PLANT G2', 'turbined': 0}]
        row = hydro_totals(groups, [ref])[0]
        self.assertEqual((row['turbined'], row['qmax'], row['factor']), (20, 100, .2))
        # A published total replaces the component sum, avoiding double counting.
        row = hydro_totals([*groups, {'name': 'PLANT', 'turbined': 25}], [ref])[0]
        self.assertEqual(row['turbined'], 25)
        row = hydro_totals(groups[:1], [ref])[0]
        self.assertFalse(row['complete_units'])
        self.assertIsNone(row['turbined'])
        self.assertIsNone(row['factor'])

    def test_failed_refresh_preserves_previous_annex_data(self):
        folder = store.DATA / 'complementos'
        folder.mkdir()
        target = folder / '2026-11-11.json'
        old = {'day': '2026-11-11', 'daily': {'hydrology': {'data': {'unchanged': 7}, 'source': {'digest': 'old'}}}, 'reserves': {}, 'files': []}
        target.write_text(json.dumps(old))
        with patch('backend.supplements.directory_files', side_effect=httpx.ConnectError('offline')):
            result = update('2026-11-11', ['A'])
        self.assertEqual(result['daily'], old['daily'])
        self.assertEqual(len(result['errors']), 3)
        self.assertEqual(json.loads(target.read_text())['daily'], old['daily'])

    def test_unreadable_annex_is_still_archived_with_failed_state(self):
        def files(directory, base):
            return [directory + 'Anexo2_Hidrologia_20261111.xlsx'] if 'Programa de Operación' in directory else []
        with patch('backend.supplements.directory_files', side_effect=files), patch('backend.supplements.fetch', return_value=b'<html>Error</html>'):
            result = update('2026-11-11', [])
        self.assertEqual(len(result['errors']), 1)
        self.assertFalse(result['files'][0]['parsed'])
        self.assertTrue((store.DATA / result['files'][0]['file']).exists())
        self.assertNotIn('hydrology', result['daily'])

    def test_consolidated_workbook_exports_annex_provenance(self):
        source = {'kind': 'hydrology', 'code': 'PDO', 'filename': 'Hydro.xlsx', 'file': 'anexos/Hydro.xlsx', 'digest': 'abc', 'checked_at': '2026-11-11', 'parsed': True, 'url': 'https://www.coes.org.pe/'}
        data = {'versions': [], 'runs': [], 'supplements': {'2026-11-11': {'files': [source], 'daily': {'hydrology': {'source': source, 'data': {'reservoirs': [{'name': 'DAM', 'initial': 0, 'final': 1}], 'plants': []}}}, 'reserves': {}}}}
        excel_export(data)
        w = load_workbook(store.DATA / 'base_excel.xlsx', read_only=True, data_only=True)
        self.assertIn('Anexos', w.sheetnames)
        self.assertIn('Hidrologia_Embalses', w.sheetnames)
        row = list(w['Hidrologia_Embalses'].values)[1]
        self.assertEqual(row, ('2026-11-11', 'PDO', 'abc', 'DAM', 0, 1))
        w.close()


if __name__ == '__main__':
    unittest.main()
