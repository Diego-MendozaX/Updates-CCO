"""Check the generated standalone HTML with a real COES archive.

python tests/smoke_static.py --base base_coes --chromium /usr/bin/chromium
Needs Playwright only for development. Does not download or change COES data.
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from threading import Thread
from urllib.parse import unquote

from playwright.sync_api import expect, sync_playwright


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, default=Path('base_coes'))
    parser.add_argument('--chromium', default='/usr/bin/chromium')
    parser.add_argument('--screenshots', type=Path, default=Path('artifacts'))
    args = parser.parse_args()
    base = args.base.resolve()
    html = (base / 'index.html').read_text(encoding='utf-8')
    data = json.loads(re.search(r'<script id="cco-data" type="application/json">(.*?)</script>', html, re.S).group(1))
    # Verify the independent component sum against the authoritative published total.
    checked = 0
    for version in data['versions']:
        total = next((s for s in version['series'] if s['role'] == 'generation_total'), None)
        if not total:
            continue
        generators = [s for s in version['series'] if s['generation']]
        for i, value in enumerate(total['values']):
            if value is not None:
                assert abs(sum(s['values'][i] or 0 for s in generators) - value) < 0.01, (version['day'], version['code'], i)
                checked += 1
        assert (base / unquote(version['file'])).is_file()
    for extra in data['supplements'].values():
        for source in extra['files']:
            assert (base / source['file']).is_file()
    args.screenshots.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(base)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}/'
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.chromium, headless=True, args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1600, 'height': 1100}, locale='es-PE', accept_downloads=True)
            errors, requests = [], []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('request', lambda r: requests.append(r.url))
            page.goto(url, wait_until='networkidle')
            expect(page.locator('#refresh-button')).to_be_visible()
            expect(page.locator('#auto-refresh')).to_have_count(0)
            latest = page.locator('#versions button').last.inner_text()
            expect(page.locator('#pair')).to_contain_text(latest)
            assert page.locator('canvas').count() == 3
            # Demand must not be stacked with generation or the maximum-demand line.
            assert page.evaluate('Chart.getChart(document.querySelector("canvas")).scales.y.max') < 15000
            if page.locator('#day option').count() > 1:
                latest_day = page.locator('#day').input_value()
                page.locator('#day').select_option(index=1)
                historic_day = page.locator('#day').input_value()
                historic = [v for v in data['versions'] if v['current'] and v['day']==historic_day][-1]
                expect(page.locator('#coverage-note')).to_contain_text(historic['reference_revision'][:12])
                page.locator('#day').select_option(latest_day)
            page.screenshot(path=str(args.screenshots / 'kallpa-resumen-v3.png'), full_page=True)
            nav = page.locator('#navigation button').evaluate_all('(els)=>els.map(e=>e.dataset.page)')
            chart_counts = {}
            for section in nav:
                page.locator(f'#navigation [data-page="{section}"]').click()
                chart_counts[section] = page.locator('canvas').count()
                assert page.locator('#content').inner_text().strip()
                if section in ('inkia', 'hydro', 'maintenance', 'changes'):
                    page.screenshot(path=str(args.screenshots / f'kallpa-{section}-v3.png'), full_page=True)
            assert sum(chart_counts[k] for k in ('executive','inkia','hydro','thermal','renewable','reserves','maintenance')) == 18
            page.locator('#navigation [data-page="reserves"]').click()
            if page.locator('[data-table="delegations"][data-action="next"]').is_enabled():
                page.locator('[data-table="delegations"][data-action="next"]').click()
                expect(page.locator('[data-table="delegations"][data-action="prev"]')).to_be_enabled()
                # A second table with fewer rows must not reset the first one's page.
                assert page.locator('#delegations').locator('..').locator('..').inner_text().find('2 /') >= 0
            if page.locator('#urs option').count() > 1:
                latest_version = [v for v in data['versions'] if v['current']][-1]
                reserve = data['supplements'][latest_version['day']]['reserves'][latest_version['code']]
                unit = next(u for u in reserve['units'] if any(n is not None for n in u['up']))
                page.locator('#urs').select_option(unit['urs'])
                expect(page.locator('.kpi-value').nth(3)).not_to_contain_text('—')
                if latest_version['series'][0]['first_interval_index'] >= 16:
                    page.locator('#period').select_option('morning')
                    expect(page.locator('.kpi-value').first).to_contain_text('—')
                    page.locator('#period').select_option('common')
            page.locator('#navigation [data-page="hydro"]').click()
            assert page.locator('#period').is_disabled()
            hydro = data['supplements'][latest_version['day']]['daily']['hydrology']['data']
            assert page.evaluate('Chart.getChart(document.getElementById("hydro-flow")).data.labels.length') == len(hydro['inkia_plants'])
            for i in (3, 4, 5):
                expect(page.locator('.kpi-value').nth(i)).not_to_contain_text('—')
            if page.locator('#reservoir option').count() > 1:
                page.locator('#reservoir').select_option(index=1)
            expect(page.locator('#reservoir option')).to_have_count(len(hydro['reservoirs']))
            page.locator('#hydro-flow-scope').select_option('all')
            assert page.evaluate('Chart.getChart(document.getElementById("hydro-flow")).data.labels.length') == len(hydro['reference_plants'])
            page.locator('#reservoir-scope').select_option('others')
            expected_reservoirs = [r for r in hydro['reservoirs'] if not r['inkia']]
            expect(page.locator('#reservoir option')).to_have_count(len(expected_reservoirs))
            selected_reservoir = page.locator('#reservoir').input_value()
            page.locator('#refresh-button').click()
            page.wait_for_load_state('networkidle')
            expect(page.locator('#reservoir-scope')).to_have_value('others')
            expect(page.locator('#reservoir')).to_have_value(selected_reservoir)
            expect(page.locator('#hydro-flow-scope')).to_have_value('all')
            page.locator('#navigation [data-page="maintenance"]').click()
            page.locator('#event-search').fill('KALLPA')
            page.wait_for_timeout(300)
            assert 'KALLPA' in page.locator('#events-table').inner_text()
            page.locator('#event-view').select_option('restrictions')
            page.locator('#reset-filters').click()
            page.locator('#navigation [data-page="changes"]').click()
            page.locator('#threshold').fill('50000')
            page.locator('#threshold').dispatch_event('change')
            assert page.locator('.kpi-value').nth(2).inner_text().strip() == '0'
            page.locator('#period').select_option('evening')
            expect(page.locator('#interval-table tbody tr')).to_have_count(16)
            page.locator('#change-kind').select_option('cost')
            expect(page.locator('#content')).to_contain_text('USD/MWh')
            with page.expect_download() as download_info:
                page.locator('#export-page').click()
            csv = Path(download_info.value.path()).read_text(encoding='utf-8-sig')
            assert 'USD/MWh' in csv and 'Anterior' in csv
            page.locator('#versions button').first.click()
            expect(page.locator('#pair')).to_contain_text('PDO · programa base')
            page.reload(wait_until='networkidle')
            expect(page.locator('#pair')).to_contain_text('PDO · programa base')
            page.locator('#latest-button').click()
            expect(page.locator('#pair')).to_contain_text(latest)
            page.locator('#navigation [data-page="executive"]').click()
            if latest_version['series'][0]['first_interval_index'] >= 16:
                page.locator('#period').select_option('morning')
                expect(page.locator('.insight-peak')).to_contain_text('—')
                page.locator('#period').select_option('common')
            page.locator('#scope').select_option('inkia')
            page.locator('#company').select_option('KALLPA')
            assert page.locator('#plant option').count() > 1
            page.locator('#plant').select_option(index=1)
            assert page.locator('canvas').count() == 3
            selected_plant = page.locator('#plant').input_value()
            page.locator('#refresh-button').click()
            page.wait_for_load_state('networkidle')
            expect(page.locator('#company')).to_have_value('KALLPA')
            expect(page.locator('#plant')).to_have_value(selected_plant)
            page.locator('#reset-filters').click()
            page.locator('#navigation [data-page="catalog"]').click()
            expect(page.locator('#matrix-sources tbody tr')).to_have_count(4)
            for tab in ('inventory','parameters','history','alerts'):
                page.locator('#catalog-tab').select_option(tab)
                assert page.locator('#catalog-table tbody tr').count() > 0
            page.locator('#catalog-search').fill('PUNTA')
            page.wait_for_timeout(300)
            expect(page.locator('#catalog-table')).to_contain_text('PUNTA')
            with page.expect_download() as matrix_info:
                page.locator('#matrix-sources a').first.click()
            assert Path(matrix_info.value.path()).read_bytes().startswith(b'PK')
            page.locator('#navigation [data-page="notes"]').click()
            note = 'Verificación local del monitor Kallpa.'
            page.locator('#notes-text').fill(note)
            page.reload(wait_until='networkidle')
            expect(page.locator('#notes-text')).to_have_value(note)
            with page.expect_download() as note_info:
                page.locator('[data-action="export-notes"]').click()
            assert json.loads(Path(note_info.value.path()).read_text())['notes'] == note
            page.locator('#notes-text').fill('')
            page.locator('#import-notes').set_input_files(str(note_info.value.path()))
            expect(page.locator('#notes-text')).to_have_value(note)
            page.set_viewport_size({'width': 390, 'height': 844})
            for section in nav:
                page.locator(f'#navigation [data-page="{section}"]').click()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), section
            page.locator('#navigation [data-page="executive"]').click()
            page.screenshot(path=str(args.screenshots / 'kallpa-mobile-v3.png'), full_page=True)
            page.locator('#method-button').click()
            expect(page.locator('#method-dialog')).to_be_visible()
            page.locator('#method-ok').click()
            # The embedded data and charts also work without a data server.
            offline = browser.new_page(viewport={'width': 1440, 'height': 1000})
            offline.on('pageerror', lambda e: errors.append(str(e)))
            offline.set_content(html, wait_until='load')
            assert offline.locator('canvas').count() == 3
            assert not errors, errors
            assert not [r for r in requests if r.startswith(('http://', 'https://')) and not r.startswith(url)], requests
            print(json.dumps({'result': 'PASS', 'pages': len(nav), 'PBIX_charts': 18, 'published_totals_checked': checked, 'reservoirs': len(hydro['reservoirs']), 'hydraulic_references':len(hydro['reference_plants']), 'manual_refresh_preserves_filters':True, 'charts_by_page': chart_counts, 'javascript_errors': errors, 'mobile_width': 390}, ensure_ascii=False))
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == '__main__':
    main()
