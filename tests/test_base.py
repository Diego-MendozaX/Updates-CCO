from argparse import Namespace
from datetime import date
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import Workbook, load_workbook

from backend import store
from backend.coes import discover, listing_records, synchronize
from backend.excel_base import extract, ingest, read_series
from backend.pipeline import acquire, export, main, parse_days
from backend.parser import SLOTS


def annex(start=0, value=100, day="03/11/2026"):
    w=Workbook();s=w.active;s.title='COES'
    s['B3']=day;s['B6']='Día Hora'
    for col,label in [('C','MANTARO'),('D','TUMBES MAK 1'),('E','Total CoGeneracion'),('F','Cmg Santa Rosa YUPANA(US$/MWh)'),('G','Demanda COES')]:
        s[col+'6']=label
    for idx in range(start,48):
        row=7+idx-start
        s.cell(row,2,'23:59' if idx==47 else SLOTS[idx]);s.cell(row,3,value);s.cell(row,6,50);s.cell(row,7,8000)
    s.cell(7+48-start,2,'MWh')
    b=BytesIO();w.save(b);return b.getvalue()


def listing(codes=('A','B','C','D','E','F','G'), day='03/11/2026'):
    w=Workbook();s=w.active
    s.append(['FECHA','TIPO','PROGRAMADOR','CAUSA REPROGRAMA','BLOQUE HORARIO','REPROGRAMA','ÚLTIMA MODIFICACIÓN'])
    for code in reversed(codes):s.append([day,'RE-PROGRAMA','test','menor demanda','10:30',code,day+' 10:00:00'])
    b=BytesIO();w.save(b);return b.getvalue()


class BaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=store.DATA;store.DATA=Path(self.tmp.name)

    def tearDown(self):
        store.DATA=self.old;self.tmp.cleanup()

    def test_actual_listing_headers_and_empty_day(self):
        self.assertEqual(discover(listing(),'2026-11-03'),list('ABCDEFG'))
        records=listing_records(listing(),'2026-11-03')
        self.assertEqual(records[0]['cause'],'menor demanda')
        self.assertEqual(records[0]['effective_from'],'10:30')
        self.assertEqual(discover(listing(codes=()),'2026-11-03'),[])
        with self.assertRaisesRegex(ValueError,'fecha'):
            discover(listing(),'2026-11-04')

    def test_partial_window_distinguishes_unpublished_and_blank(self):
        p=extract(annex(start=41),'2026-11-03')
        s=next(s for s in p['series'] if s['name']=='MANTARO')
        self.assertIsNone(s['values'][40]);self.assertEqual(s['source_rows'][40],0)
        self.assertEqual(s['values'][41],100);self.assertEqual(s['source_rows'][41],7)
        self.assertEqual(s['raw_times'][47],'23:59');self.assertEqual(p['times'][47],'24:00')
        self.assertIsNone(next(s for s in p['series'] if s['name']=='TUMBES MAK 1')['values'][41])
        self.assertEqual(next(s for s in p['series'] if s['name'].startswith('Cmg'))['unit'],'USD/MWh')
        with self.assertRaisesRegex(ValueError,'no a'):
            extract(annex(),'2026-11-04')

    def test_sqlite_values_keep_source_provenance_and_idempotence(self):
        raw=annex(start=41)
        identifier,_=store.save('2026-11-03','G',raw,'Reprog.xlsx','test')
        ingest(identifier);ingest(identifier)
        with store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM excel_values').fetchone()[0],5*48)
            r=db.execute("SELECT * FROM excel_values WHERE version_id=? AND series_key LIKE '%MANTARO' AND interval_index=40",(identifier,)).fetchone()
            self.assertEqual(r['present_in_source'],0)
            r=db.execute("SELECT * FROM excel_values WHERE version_id=? AND series_key LIKE '%MANTARO' AND interval_index=41",(identifier,)).fetchone()
            self.assertEqual(r['source_row'],7);self.assertEqual(r['present_in_source'],1)
        self.assertEqual(read_series(identifier)[0]['first_interval_index'],41)

    def test_pipeline_creates_portable_outputs_and_exact_cells(self):
        def fetch(url):return listing(codes=('A','B')) if 'Listado' in url else annex(start=7 if '0311B' in url else 0)
        with patch('backend.coes.fetch',side_effect=fetch):
            r=acquire('2026-11-03');self.assertTrue(r['complete'])
            r2=acquire('2026-11-03');self.assertFalse(any(v['created'] for v in r2['results']))
        data=export();self.assertEqual(len(data['versions']),3)
        html=(store.DATA/'index.html').read_text()
        self.assertNotIn('__CCO_DATA__',html);self.assertIn('application/json',html)
        self.assertTrue((store.DATA/'base_excel.xlsx').exists())
        manifest=json.loads((store.DATA/'manifest.json').read_text())
        self.assertTrue(manifest['runs'][0]['complete'])
        w=load_workbook(store.DATA/'base_excel.xlsx',read_only=True,data_only=True)
        self.assertEqual(w.sheetnames,['Programas','Publicaciones','Columnas','Datos','Consultas'])
        # Rows outside B's publication window have no fictitious Excel cell address.
        rows=w['Datos'].values;header=next(rows);j=header.index('celda_origen')
        b=next(r for r in rows if r[2]=='B')
        self.assertIsNone(b[j]);w.close()

    def test_http_200_html_is_not_an_excel_download(self):
        with patch('backend.coes.fetch',side_effect=lambda u:listing(codes=()) if 'Listado' in u else b'<html>error</html>'):
            result=synchronize('2026-11-03')
        self.assertTrue(result['listing_verified']);self.assertEqual(result['results'],[])
        self.assertEqual(result['errors'][0]['code'],'PDO')

    def test_incomplete_run_still_exports_but_exits_nonzero(self):
        from httpx import ConnectError
        with patch('backend.coes.fetch',side_effect=ConnectError('offline')):
            code=main(['--base',str(store.DATA),'--fecha','2026-11-11'])
        self.assertEqual(code,2);self.assertTrue((store.DATA/'index.html').exists())
        report=json.loads((store.DATA/'manifest.json').read_text())['runs'][0]
        self.assertFalse(report['listing_verified']);self.assertFalse(report['complete'])

    def test_date_defaults_and_ranges(self):
        self.assertEqual(parse_days(Namespace(fecha=None,desde=None,hasta=None),date(2026,11,11)),['2026-11-11'])
        self.assertEqual(parse_days(Namespace(fecha=None,desde='2026-11-10',hasta=None),date(2026,11,11)),['2026-11-10','2026-11-11'])
        with self.assertRaises(ValueError):
            parse_days(Namespace(fecha=['2026-11-12'],desde=None,hasta=None),date(2026,11,11))


if __name__=='__main__':unittest.main()
