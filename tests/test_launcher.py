"""Regression checks for missing packages and Spyder execution."""
from contextlib import redirect_stderr
from io import StringIO
import unittest
from unittest.mock import patch

from backend.launcher import cli, install_command, launch, missing_dependencies


class LauncherTests(unittest.TestCase):
    def test_missing_annex_readers_are_reported_together(self):
        def load(name):
            if name in ('pypdf', 'xlrd'):
                raise ModuleNotFoundError(name)
            return object()
        with patch('backend.launcher.import_module', side_effect=load):
            self.assertEqual(missing_dependencies(), ['pypdf', 'xlrd'])
            self.assertEqual(missing_dependencies(include_annexes=False), [])

    def test_missing_packages_stop_before_downloads_and_show_interpreter_command(self):
        errors = StringIO()
        with patch('backend.launcher.missing_dependencies', return_value=['pypdf', 'xlrd']), \
             patch('backend.pipeline.run') as run, redirect_stderr(errors):
            result = launch([])
        self.assertEqual(result, 2)
        run.assert_not_called()
        message = errors.getvalue()
        for expected in ('pypdf', 'xlrd', 'Python utilizado:', install_command(), 'reinicia el kernel'):
            self.assertIn(expected, message)

    def test_offline_and_dispatch_only_do_not_require_annex_packages(self):
        for option in ('--sin-descargar', '--solo-despacho'):
            with self.subTest(option=option), \
                 patch('backend.launcher.missing_dependencies', return_value=[]) as check, \
                 patch('backend.pipeline.run', return_value=0) as run:
                self.assertEqual(launch([option, '--no-abrir']), 0)
                check.assert_called_once_with(False)
                run.assert_called_once_with([option, '--no-abrir'])

    def test_windows_command_quotes_paths_and_uses_console_python(self):
        command = install_command(
            executable=r'C:\Program Files\Spyder\pythonw.exe',
            requirements=r'C:\Users\Diego Mendoza\Updates-CCO\requirements-base.txt',
            windows=True,
        )
        self.assertEqual(command, '"C:\\Program Files\\Spyder\\python.exe" -m pip install -r "C:\\Users\\Diego Mendoza\\Updates-CCO\\requirements-base.txt"')

    def test_spyder_reports_partial_result_without_system_exit(self):
        with patch('backend.launcher.launch', return_value=2), \
             patch('builtins.get_ipython', return_value=object(), create=True):
            self.assertEqual(cli(), 2)

    def test_terminal_keeps_failure_exit_status_and_success_returns_zero(self):
        with patch('builtins.get_ipython', return_value=None, create=True):
            with patch('backend.launcher.launch', return_value=2), self.assertRaises(SystemExit) as error:
                cli()
            self.assertEqual(error.exception.code, 2)
            with patch('backend.launcher.launch', return_value=0):
                self.assertEqual(cli(), 0)


if __name__ == '__main__':
    unittest.main()
