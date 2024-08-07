import unittest
from pathlib import Path
from code_graph import *

class Test_PY_Analyzer(unittest.TestCase):
    def test_analyzer(self):
        path = Path(__file__).parent
        analyzer = SourceAnalyzer()

        g = Graph('test_py')
        analyzer.graph = g
        analyzer.analyze_sources(str(path))

        f = g.get_file('/source_files/py', 'src.py', '.py')
        self.assertEqual(File('/source_files/py', 'src.py', '.py'), f)

        log = g.get_function_by_name('log')
        expected_log = Function('/source_files/py/src.py', 'log', None, 'None', '', 0, 1)
        expected_log.add_argument('msg', 'str')
        self.assertEqual(expected_log, log)

        abort = g.get_function_by_name('abort')
        expected_abort = Function('/source_files/py/src.py', 'abort', None, 'Task', '', 9, 11)
        expected_abort.add_argument('self', 'Unknown')
        expected_abort.add_argument('delay', 'float')
        self.assertEqual(expected_abort, abort)

        init = g.get_function_by_name('__init__')
        expected_init = Function('/source_files/py/src.py', '__init__', None, None, '', 4, 7)
        expected_init.add_argument('self', 'Unknown')
        expected_init.add_argument('name', 'str')
        expected_init.add_argument('duration', 'int')
        self.assertEqual(expected_init, init)

        task = g.get_class_by_name('Task')
        expected_task = Class('/source_files/py/src.py', 'Task', None, 3, 11)
        self.assertEqual(expected_task, task)

        callees = g.function_calls(abort.id)
        self.assertEqual(len(callees), 1)
        self.assertEqual(callees[0], log)

        print_func = g.get_function_by_name('print')
        callers = g.function_called_by(print_func.id)
        callers = [caller.name for caller in callers]

        self.assertIn('__init__', callers)
        self.assertIn('log', callers)
