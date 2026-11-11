"""Real Chromium smoke test in an isolated archive, never the user's archive.

python tests/smoke_browser.py --reference-file /path/to/Comparador.xlsm
Requires Playwright and Chromium (available in the prepared cloud machine).
"""
import argparse
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

from openpyxl import Workbook
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reference-file', required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='cco-ui-') as directory:
        env = dict(os.environ, CCO_DATA_DIR=directory)
        subprocess.run([sys.executable, '-m', 'backend.import_reference', args.reference_file, '--day', '2025-12-14'], env=env, cwd=ROOT, check=True)
        server = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8001'], env=env, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try:
                    with urlopen('http://127.0.0.1:8001/api/health', timeout=1):
                        break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError('Test server did not start')
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
                page = browser.new_page(viewport={'width':1440,'height':1100}, locale='es-PE')
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto('http://127.0.0.1:8001', wait_until='networkidle')
                expect(page.locator('.reference-banner')).to_contain_text('No representan la operación de hoy')
                expect(page.locator('.kpi-value').nth(0)).to_contain_text('-229.6')
                page.get_by_role('tab', name='Térmica', exact=True).click()
                expect(page.locator('.kpi-value').nth(0)).to_contain_text('+206.0')
                page.get_by_label('Buscar equipo o barra', exact=True).fill('KALLPATG3GAS')
                expect(page.locator('.detail-panel tbody tr')).to_have_count(1)
                expect(page.locator('.detail-panel tbody tr').first).to_contain_text('+200.3')
                page.locator('.detail-panel tbody tr').first.click()
                expect(page.locator('.interval-grid > div')).to_have_count(48)
                page.get_by_label('Equipo del gráfico', exact=True).select_option('termica:KALLPATG3GAS')
                expect(page.locator('.trend-panel .panel-heading p')).to_contain_text('KALLPATG3GAS')
                page.get_by_label('Umbral de impacto en MW', exact=True).fill('250')
                expect(page.locator('.alert-kpi .kpi-value')).to_contain_text('0')
                with page.expect_download() as download_info:
                    page.get_by_role('button', name='Exportar CSV', exact=True).click()
                download = download_info.value
                csv = Path(download.path()).read_text(encoding='utf-8-sig')
                assert len(csv.splitlines()) == 49
                assert 'KALLPATG3GAS' in csv and '200.26' in csv
                page.get_by_label('Rango horario', exact=True).select_option('16-32')
                expect(page.locator('.heat-row').first.locator('.heat-cell')).to_have_count(16)
                page.get_by_role('button', name='Archivo de programas', exact=False).first.click()
                expect(page.locator('.archive tbody tr')).to_have_count(2)
                with page.expect_download() as original_info:
                    page.locator('.download-link').first.click()
                assert Path(original_info.value.path()).read_bytes() == Path(args.reference_file).read_bytes()
                page.get_by_role('button', name='Consultar hoy', exact=False).click()
                expect(page.locator('.archive .empty')).to_be_visible()
                page.get_by_role('button', name='Vista general', exact=True).click()
                expect(page.locator('.empty')).to_be_visible()
                # Exercise the complete manual-upload flow in the isolated archive.
                w = Workbook();s = w.active;s.title = 'Térmica'
                s.append(['ETAPA','TEST UNIT'])
                for i in range(1,49):
                    s.append([f'{i//2:02d}:{30 if i%2 else 0:02d}',100])
                out = BytesIO();w.save(out)
                page.get_by_role('button', name='Cargar archivo', exact=True).click()
                page.get_by_label('Versión', exact=True).fill('PDO')
                page.locator('input[type=file]').set_input_files({'name':'test-PDO.xlsx','mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','buffer':out.getvalue()})
                page.get_by_role('button', name='Guardar en el archivo', exact=True).click()
                expect(page.locator('.archive tbody tr')).to_have_count(1)
                expect(page.locator('.archive')).to_contain_text('test-PDO.xlsx')
                page.get_by_role('button', name='Explorar comparador adjunto').click()
                page.get_by_role('button', name='Vista general', exact=True).click()
                page.get_by_role('tab', name='Demanda', exact=True).click()
                expect(page.locator('.kpi-value').nth(2)).to_contain_text('/ 237')
                page.set_viewport_size({'width':390,'height':844})
                expect(page.locator('.reference-banner')).to_be_visible()
                assert page.evaluate('document.body.scrollWidth <= innerWidth')
                # Open and close the methodology dialog on mobile.
                page.get_by_role('button', name='Cargar archivo', exact=True).click()
                expect(page.get_by_role('dialog')).to_be_visible()
                page.get_by_role('button', name='Cerrar', exact=True).click()
                assert not errors, errors
                print(json.dumps({'browser':'Chromium','checks':'filters, thresholds, curve selection, period range, CSV, original download, empty day, upload, mobile','console_errors':errors,'result':'PASS'}))
                browser.close()
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == '__main__':
    main()
