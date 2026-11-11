from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend import store
from backend.comparison import compare, predecessor
from backend.coes import discover, download_url, synchronize
from backend.main import app
from backend.parser import read_workbook, SLOTS


def workbook(values=(100.0, 50.0), missing=False, reverse=False):
    w = Workbook()
    s = w.active
    s.title = "Térmica"
    s.append(["ETAPA", *(('BETA', 'ALFA') if reverse else ('ALFA', 'BETA'))])
    for i, t in enumerate(SLOTS):
        row = [values[0], values[1]]
        if missing and i == 0:
            row[0] = None
        s.append([t, *(reversed(row) if reverse else row)])
    b = BytesIO()
    w.save(b)
    return b.getvalue()


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_data = store.DATA
        store.DATA = Path(self.temp.name)
        self.client = TestClient(app)

    def tearDown(self):
        store.DATA = self.previous_data
        self.temp.cleanup()

    def save(self, code, raw):
        return store.save('2026-11-03', code, raw, code+'.xlsx', 'test', read_workbook(raw))

    def test_consecutive_chain_never_skips_missing_version(self):
        self.save('PDO', workbook())
        self.save('A', workbook((120, 0)))
        self.save('C', workbook((130, 0)))
        d = compare('2026-11-03', 'A')
        self.assertEqual(d['previous'], 'PDO')
        self.assertEqual(d['metrics']['energy'], -720)
        with self.assertRaisesRegex(ValueError, 'Falta B'):
            compare('2026-11-03', 'C')
        self.save('B', workbook((125, 0)))
        self.assertEqual(compare('2026-11-03', 'C')['previous'], 'B')
        self.assertEqual(predecessor('AA'), 'Z')

    def test_matches_by_name_not_column_and_threshold_is_inclusive(self):
        self.save('PDO', workbook())
        self.save('A', workbook((200, 50), reverse=True))
        d = compare('2026-11-03', 'A', threshold=100)
        a = next(x for x in d['assets'] if x['name'] == 'ALFA')
        self.assertEqual(a['peak'], 100)
        self.assertEqual(a['alerts'], 48)
        self.assertEqual(d['metrics']['alert_assets'], 1)
        self.assertEqual(d['metrics']['energy'], 2400)

    def test_missing_is_not_zero_and_zero_base_has_no_percent(self):
        self.save('PDO', workbook((0, 50)))
        self.save('A', workbook((100, 50), missing=True))
        d = compare('2026-11-03', 'A')
        a = next(x for x in d['assets'] if x['name'] == 'ALFA')
        self.assertIsNone(a['delta'][0])
        self.assertIsNone(a['percent'])
        self.assertIsNone(a['energy'])
        self.assertIsNone(d['metrics']['energy'])
        self.assertIsNone(d['series'][0]['new'])

    def test_period_filter_integrates_only_selected_hours(self):
        self.save('PDO', workbook())
        self.save('A', workbook((120, 50)))
        d = compare('2026-11-03', 'A', start=16, end=32)
        self.assertEqual(len(d['times']), 16)
        self.assertEqual(d['times'][0], '08:30')
        self.assertEqual(d['metrics']['energy'], 160)

    def test_immutable_archive_idempotency_and_revision_history(self):
        raw = workbook()
        a, created = self.save('PDO', raw)
        b, created_again = self.save('PDO', raw)
        self.assertEqual(a, b)
        self.assertTrue(created)
        self.assertFalse(created_again)
        c, _ = self.save('PDO', workbook((125, 50)))
        items = store.all_versions()
        self.assertEqual(len(items), 2)
        self.assertEqual(sum(x['current'] for x in items), 1)
        self.assertEqual(store.latest('2026-11-03', 'PDO', 'official')['id'], c)
        response = self.client.get(f'/api/files/{a}')
        self.assertEqual(response.content, raw)

    def test_official_and_reference_never_mix(self):
        raw = workbook()
        store.save('2026-11-03', 'ANTERIOR', raw, 'ref.xlsm', 'test', read_workbook(raw), family='reference')
        self.save('A', raw)
        with self.assertRaisesRegex(ValueError, 'Falta PDO'):
            compare('2026-11-03', 'A')

    def test_horizontal_layout_and_skip_totals(self):
        w = Workbook()
        s = w.active
        s.title = 'Despacho'
        s.append(['CENTRAL', *SLOTS])
        s.append(['CENTRALES HIDROELÉCTRICAS'])
        s.append(['MANTARO', *([500]*48)])
        s.append(['TOTAL HIDRO', *([500]*48)])
        b = BytesIO();w.save(b)
        p = read_workbook(b.getvalue())
        self.assertEqual(len(p['assets']), 1)
        self.assertEqual(p['assets'][0]['category'], 'hidro')

    def test_listing_discovery_and_exact_user_url(self):
        codes = discover(b'Reprog_0311C.xlsx\n0311A\n0311B', '2026-11-03')
        self.assertEqual(codes, ['A', 'B', 'C'])
        url, filename = download_url('2026-11-03', 'A')
        from urllib.parse import parse_qs, urlparse
        self.assertEqual(parse_qs(urlparse(url).query)['url'][0], 'Operación/Programa de Operación/Reprograma Diario Operación/2026/11_NOVIEMBRE/Día 03/Reprog 0311A/Reprog_0311A.xlsx')
        self.assertEqual(filename, 'Reprog_0311A.xlsx')
        with self.assertRaises(ValueError):
            discover(b'<html>Access denied</html>', '2026-11-03')

    def test_sync_discovers_beyond_e_and_is_repeatable(self):
        raw = workbook()
        def fake(url):
            return b'0311A 0311B 0311C 0311D 0311E 0311F' if 'DescargarListado' in url else raw
        with patch('backend.coes.fetch', side_effect=fake):
            result = synchronize('2026-11-03')
            self.assertTrue(result['listing_verified'])
            self.assertEqual(len(result['results']), 7)
            self.assertIn('F', result['discovered'])
            repeat = synchronize('2026-11-03')
            self.assertFalse(any(x['created'] for x in repeat['results']))

    def test_api_upload_then_compare_and_invalid_inputs(self):
        for code, raw in [('PDO', workbook()), ('A', workbook((200, 50)))]:
            r = self.client.post('/api/upload', data={'day':'2026-11-03','code':code}, files={'file':(code+'.xlsx',raw)})
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.json()['ready'])
        r = self.client.get('/api/comparison', params={'day':'2026-11-03','code':'A'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['metrics']['peak'], 100)
        r = self.client.post('/api/upload', data={'day':'2026-11-03','code':'B'}, files={'file':('bad.xlsx',b'bad')})
        self.assertFalse(r.json()['ready'])
        self.assertEqual(self.client.get('/api/comparison?day=2026-11-03&code=B').status_code,409)
        self.assertEqual(self.client.get('/api/comparison?day=invalid&code=A').status_code,422)
        self.assertEqual(self.client.get('/api/comparison?day=2026-11-03&code=A&threshold=-1').status_code,422)


if __name__ == '__main__':
    unittest.main()
