import unittest
from falkordb import FalkorDB
from typing import List, Optional
from code_graph import *


class TestGraphOps(unittest.TestCase):
    def setUp(self):
        self.db = FalkorDB()
        self.g = self.db.select_graph('test')
        self.graph = Graph(name='test')

    def _test_add_function(self):
        # Create function
        func = Function('/path/to/function', 'func', '', 'int', '', 1, 10)
        func.add_argument('x', 'int')
        func.add_argument('y', 'float')

        func_id = self.graph.add_function(func)
        self.assertEqual(func, self.graph.get_function(func_id))

    def _test_add_file(self):
        file = File('/path/to/file', 'file', 'txt')

        file_id = self.graph.add_file(file)
        self.assertEqual(file, self.graph.get_file(file_id))

    def _test_file_add_function(self):
        file = File('/path/to/file', 'file', 'txt')
        func = Function('/path/to/function', 'func', '', 'int', '', 1, 10)

        file_id = self.graph.add_file(file)
        func_id = self.graph.add_function(func)

        self.graph.file_add_function(file_id=file_id, func_id=func_id)

        query = """MATCH (file:File)-[:CONTAINS]->(func:Function)
                   WHERE ID(func) = $func_id AND ID(file) = $file_id
                   RETURN true"""

        params = {'file_id': file_id, 'func_id': func_id}
        res = self.g.query(query, params).result_set
        self.assertTrue(res[0][0])

    def _test_function_calls_function(self):
        caller = Function('/path/to/function', 'func_A', '', 'int', '', 1, 10)
        callee = Function('/path/to/function', 'func_B', '', 'int', '', 11, 21)

        caller_id = self.graph.add_function(caller)
        callee_id = self.graph.add_function(callee)
        self.graph.function_calls_function(caller_id, callee_id, 10)

        query = """MATCH (caller:Function)-[:CALLS]->(callee:Function)
               WHERE ID(caller) = $caller_id AND ID(callee) = $callee_id
               RETURN true"""

        params = {'caller_id': caller_id, 'callee_id': callee_id}
        res = self.g.query(query, params).result_set
        self.assertTrue(res[0][0])

if __name__ == '__main__':
    unittest.main()
