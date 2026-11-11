"""Reference revisions, identity changes and conservative commercial-state checks."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from openpyxl import load_workbook

from backend import store
from backend.catalog_audit import CatalogAudit
from backend.dashboard import Resolver, commercial_status, enrich, key
from backend.matrices import ROOT, archive_references, for_day, read_matrices, reference_changes


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.original = store.DATA
        store.DATA = self.root / 'output'
        self.sources = self.root / 'sources'
        shutil.copytree(ROOT / 'catalogos' / 'fuentes', self.sources)
        self.options = self.root / 'ajustes.json'
        shutil.copyfile(ROOT / 'catalogos' / 'ajustes.json', self.options)

    def tearDown(self):
        store.DATA = self.original
        self.tmp.cleanup()

    def read(self):
        return read_matrices(self.sources, self.options)

    def edit_cell(self, filename, cell, value):
        path = self.sources / filename
        w = load_workbook(path, data_only=True)
        w.active[cell] = value
        w.save(path)
        w.close()

    def test_all_four_matrices_are_used_and_zero_capacity_is_not_a_retirement(self):
        bundle = self.read()
        self.assertEqual((len(bundle['plants']),len(bundle['hydrology']),len(bundle['units'])), (180,37,19))
        self.assertEqual(len(bundle['sources']), 4)
        zero = [p for p in bundle['plants'] if p['capacity_reference'] == 0]
        self.assertEqual(len(zero), 4)
        self.assertEqual(sum(r['field']=='Capacidad Instalada (MW)' for r in bundle['parameter_issues']), 4)
        self.assertTrue(any(r['asset']=='CHAGLLA GP1' and r['field']=='Nombre_Central_Dashboard' for r in bundle['parameter_issues']))
        self.assertTrue(all(p['matrix_row'] > 1 and len(p['matrix_sha256']) == 64 for p in bundle['plants']))
        self.assertFalse(bundle['options']['commercial_status'])
        resolver = Resolver(bundle, CatalogAudit(bundle, archive_references(bundle,self.sources)))
        block = resolver.resolve({'name':'PUN LOMITAS_EXP-BL1','role':'renewables','source_code':'58839','group_label':'ENGIE'},set())
        self.assertEqual(block['technology'],'EOLICA')
        self.assertEqual(block['capacity_reference'],0)

    def test_parameter_update_is_versioned_and_historical_day_keeps_previous_value(self):
        before = self.read()
        archive_references(before, self.sources)
        filename = 'Matriz_Hidro y termicas INKIA.xlsx'
        self.edit_cell(filename, 'E2', 250)
        options = json.loads(self.options.read_text())
        options['effective_from'] = '2000-01-01'
        self.options.write_text(json.dumps(options))
        after = self.read()
        history = archive_references(after, self.sources)
        self.assertEqual(len(history['versions']), 2)
        old = for_day(after, history, '1999-12-31')
        new = for_day(after, history, '2000-01-01')
        old_plant = next(p for p in old['plants'] if p['source'] == 'SAN GABAN III')
        new_plant = next(p for p in new['plants'] if p['source'] == 'SAN GABAN III')
        self.assertEqual(old_plant['capacity_reference'], 209.203)
        self.assertEqual(new_plant['capacity_reference'], 250)
        self.assertTrue(any(c['field'] == 'capacity_reference' for c in history['versions'][-1]['changes']))
        self.assertEqual(len(archive_references(after,self.sources)['versions']), 2)
        # Reverting to an earlier file is another application, not an ignored known hash.
        reverted = archive_references(before, self.sources)
        self.assertEqual(len(reverted['versions']), 3)
        today = datetime.now(timezone(timedelta(hours=-5))).date().isoformat()
        self.assertEqual(for_day(before,reverted,today)['revision'],before['revision'])

    def test_duplicate_reference_is_rejected(self):
        path = self.sources / 'Matriz URS.xlsx'
        w = load_workbook(path,data_only=True)
        w.active.append([c.value for c in w.active[2]])
        w.save(path);w.close()
        with self.assertRaisesRegex(ValueError, 'duplicada'):
            self.read()

    def test_inconsistent_hydraulic_parameter_is_rejected(self):
        self.edit_cell('Matriz_Anexo_Hidrologia.xlsx','H2',999)
        with self.assertRaisesRegex(ValueError, 'no coincide'):
            self.read()

    def test_retirement_requires_identifier_date_and_evidence(self):
        options = json.loads(self.options.read_text())
        record = {'coes_code':'42','status':'fuera_de_operacion_comercial','effective_from':'2026-11-12'}
        options['commercial_status'] = [record]
        self.options.write_text(json.dumps(options))
        with self.assertRaisesRegex(ValueError, 'evidence'):
            self.read()
        record['evidence'] = 'Resolución oficial de retiro'
        self.options.write_text(json.dumps(options))
        bundle = self.read()
        self.assertEqual(commercial_status({'source_code':'42'}, {}, '2026-11-11', bundle['options']), 'sin_retiro_confirmado')
        self.assertEqual(commercial_status({'source_code':'42'}, {}, '2026-11-12', bundle['options']), 'fuera_de_operacion_comercial')

    def test_removed_reference_is_a_matrix_change_not_an_automatic_retirement(self):
        before = self.read()
        after = deepcopy(before)
        removed = after['plants'].pop()
        changes = reference_changes(before,after)
        self.assertTrue(any(r['asset']==removed['source'] and r['after'] is None for r in changes))
        self.assertEqual(after['options']['commercial_status'], [])

    def series(self, name='KALLPA TG1', **kwargs):
        return {'name':name,'plant':name,'source_code':'42','group_label':'KALLPA','company':'KALLPA',
                'generation':True,'technology':'Térmicas INKIA','category':'Térmica','capacity':182.37954,
                'classification_basis':'catalog','reference_source':'KALLPA TG1','values':[0]*48, **kwargs}

    def version(self, day, series):
        return {'day':day,'code':'PDO','current':True,'structured':True,'series':series,'filename':'PDO.xlsx'}

    def report(self, day, verified=True):
        return {'day':day,'listing_verified':verified,'errors':[],'normalization_errors':[]}

    def test_code_based_rename_preserves_reference_only_with_same_owner(self):
        bundle = self.read();history = archive_references(bundle,self.sources)
        audit = CatalogAudit(bundle,history)
        version = self.version('2026-11-03',[self.series()])
        audit.observe(version,version['series'][0])
        audit.finish({'versions':[version],'runs':[self.report(version['day'])]})
        audit = CatalogAudit(bundle,history)
        lookup = {key(r['source']):r for r in bundle['plants']}
        renamed = self.series('NUEVO NOMBRE COES')
        ref = audit.binding(renamed,lookup,'KALLPA')
        self.assertEqual(ref['origin'],'coes_code')
        self.assertEqual(ref['source'],'KALLPA TG1')
        self.assertIsNone(audit.binding({**renamed,'group_label':'ENGIE'},lookup,'ENGIE'))
        renamed['classification_basis']='coes_code'
        later = self.version('2026-11-11',[renamed])
        audit.observe(later,renamed)
        result = audit.finish({'versions':[version,later],'runs':[self.report(later['day'])]})
        self.assertTrue(any(r['kind']=='nombre_actualizado' and r['automatic'] for r in result['events']))
        # Repeated offline exports do not multiply event lines.
        lines = (store.DATA/'catalogos'/'cambios.jsonl').read_text().splitlines()
        again = CatalogAudit(bundle,history)
        again.observe(later,renamed)
        again.finish({'versions':[version,later],'runs':[self.report(later['day'])]})
        self.assertEqual((store.DATA/'catalogos'/'cambios.jsonl').read_text().splitlines(),lines)

    def test_missing_unit_needs_verified_pdo_and_never_implies_retirement(self):
        bundle=self.read();history=archive_references(bundle,self.sources)
        old=self.version('2026-11-03',[self.series()])
        audit=CatalogAudit(bundle,history);audit.observe(old,old['series'][0])
        audit.finish({'versions':[old],'runs':[self.report(old['day'])]})
        latest=self.version('2026-11-11',[])
        audit=CatalogAudit(bundle,history)
        partial=audit.finish({'versions':[old,latest],'runs':[self.report(latest['day'],False)]})
        self.assertEqual(next(r for r in partial['inventory'] if r['id']=='GEN:42')['status'],'observada')
        audit=CatalogAudit(bundle,history)
        complete=audit.finish({'versions':[old,latest],'runs':[self.report(latest['day'])]})
        self.assertEqual(next(r for r in complete['inventory'] if r['id']=='GEN:42')['status'],'no_observada')
        self.assertTrue(any(r['kind']=='ausencia_en_PDO' for r in complete['alerts']))
        later=self.version('2026-11-12',[self.series()])
        audit=CatalogAudit(bundle,history);audit.observe(later,later['series'][0])
        returned=audit.finish({'versions':[old,latest,later],'runs':[self.report(later['day'])]})
        self.assertEqual(next(r for r in returned['inventory'] if r['id']=='GEN:42')['status'],'observada')
        self.assertTrue(any(r['kind']=='reaparicion' for r in returned['events']))

    def test_unknown_unit_is_added_and_zero_dispatch_does_not_mark_it_retired(self):
        bundle=self.read();history=archive_references(bundle,self.sources)
        unknown=self.series('NEW UNIT',source_code='999',capacity=None,reference_source=None,classification_basis='unclassified')
        version=self.version('2026-11-11',[unknown])
        audit=CatalogAudit(bundle,history);audit.observe(version,unknown)
        result=audit.finish({'versions':[version],'runs':[self.report(version['day'])]})
        unit=next(r for r in result['inventory'] if r['id']=='GEN:999')
        self.assertEqual(unit['status'],'observada')
        self.assertTrue(unit['review_required'])
        self.assertIsNone(unit['capacity_reference'])
        self.assertTrue(any(r['kind']=='parametro_pendiente' and r['asset']=='NEW UNIT' for r in result['alerts']))

    def test_invalid_new_matrix_keeps_last_valid_revision_and_visible_warning(self):
        bundle=self.read();archive_references(bundle,self.sources)
        with patch('backend.dashboard.read_matrices',side_effect=ValueError('encabezado cambiado')),patch('backend.dashboard.load_all',return_value={}):
            data=enrich({'versions':[],'runs':[]})
        self.assertEqual(data['catalog']['revision'],bundle['revision'])
        self.assertIn('encabezado cambiado',data['catalog']['errors'][0])
        self.assertTrue(any(r['kind']=='matriz_no_aplicada' for r in data['catalog']['alerts']))

    def test_positive_dispatch_after_confirmed_retirement_is_preserved_and_warned(self):
        options=json.loads(self.options.read_text())
        options['commercial_status']=[{'coes_code':'42','status':'fuera_de_operacion_comercial','effective_from':'2026-11-11','evidence':'Comunicación oficial de retiro'}]
        self.options.write_text(json.dumps(options))
        bundle=self.read()
        series=self.series(role='dispatch',values=[50]*48)
        version=self.version('2026-11-11',[series])
        with patch('backend.dashboard.read_matrices',return_value=bundle),patch('backend.dashboard.load_all',return_value={}):
            data=enrich({'versions':[version],'runs':[self.report(version['day'])]})
        self.assertTrue(series['generation'])
        self.assertEqual(series['values'],[50]*48)
        self.assertEqual(series['commercial_status'],'fuera_de_operacion_comercial')
        self.assertTrue(any(r['kind']=='despacho_tras_retiro' for r in data['catalog']['alerts']))


if __name__ == '__main__':
    unittest.main()
