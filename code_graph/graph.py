from .entities import *
from typing import List, Optional
from falkordb import FalkorDB, Node

class Graph():
    """
    Represents a connection to a graph database using FalkorDB.
    """

    def __init__(self, name: str, host: str = 'localhost', port: int = 6379,
                 username: Optional[str] = None, password: Optional[str] = None) -> None:
        self.db = FalkorDB(host=host, port=port, username=username,
                           password=password)
        self.g = self.db.select_graph(name)

        # create indicies

        # index File path, name and ext fields
        try:
            self.g.create_node_range_index("File", "path", "name", "ext")
        except Exception:
            pass

        # index Function
        try:
            self.g.create_node_range_index("File", "path", "name")
        except Exception:
            pass

    def add_class(self, c: Class) -> None:
        """
        Adds a class node to the graph database.

        Args:
            c (Class): The Class object to be added.
        """

        q = """MERGE (c:Class {name: $name, path: $path, src_start: $src_start,
                               src_end: $src_end})
               SET c.doc = $doc
               RETURN ID(c)"""

        params = {
            'doc': c.doc,
            'name': c.name,
            'path': c.path,
            'src_start': c.src_start,
            'src_end': c.src_end,
        }

        res = self.g.query(q, params)
        c.id = res.result_set[0][0]

    def _class_from_node(self, n: Node) -> Class:
        """
        Create a Class from a graph node
        """

        doc       = n.properties.get('doc')
        name      = n.properties.get('name')
        path      = n.properties.get('path')
        src_end   = n.properties.get('src_end')
        src_start = n.properties.get('src_start')

        c = Class(path, name, doc, src_start, src_end)
        c.id = n.id

        return c

    def get_class_by_name(self, class_name: str) -> Optional[Class]:
        q = "MATCH (c:Class) WHERE c.name = $name RETURN c LIMIT 1"
        res = self.g.query(q, {'name': class_name}).result_set

        if len(res) == 0:
            return None

        return self._class_from_node(res[0][0])

    def get_class(self, class_id: int) -> Optional[Class]:
        q = """MATCH (c:Class)
               WHERE ID(c) = $class_id
               RETURN c"""
        
        res = self.g.query(q, {'class_id': class_id})

        if len(res.result_set) == 0:
            return None

        c = res.result_set[0][0]
        return self._class_from_node(c)

    def add_function(self, func: Function) -> None:
        """
        Adds a function node to the graph database.

        Args:
            func (Function): The Function object to be added.
        """

        q = """MERGE (f:Function {path: $path, name: $name,
                                  src_start: $src_start, src_end: $src_end})
               SET f.args = $args, f.ret_type = $ret_type, f.src = $src, f.doc = $doc
               RETURN ID(f)"""

        # Prepare arguments in a more straightforward manner
        args = [[arg.name, arg.type] for arg in func.args]
        params = {
            'src': func.src,
            'doc': func.doc,
            'path': func.path,
            'name': func.name,
            'src_start': func.src_start,
            'src_end': func.src_end,
            'args': args,
            'ret_type': func.ret_type
        }


        res = self.g.query(q, params)
        func.id = res.result_set[0][0]

    def _function_from_node(self, n: Node) -> Function:
        """
        Create a Function from a graph node
        """

        src       = n.properties.get('src')
        doc       = n.properties.get('doc')
        path      = n.properties.get('path')
        name      = n.properties.get('name')
        args      = n.properties.get('args')
        src_end   = n.properties.get('src_end')
        ret_type  = n.properties.get('ret_type')
        src_start = n.properties.get('src_start')

        f = Function(path, name, doc, ret_type, src, src_start, src_end)
        for arg in args:
            name  = arg[0]
            type_ = arg[1]
            f.add_argument(name, type_)

        f.id = n.id

        return f

    
    # set functions metadata
    def set_functions_metadata(self, ids: List[int], metadata: List[dict]) -> None:
        assert(len(ids) == len(metadata))

        # TODO: Match (f:Function)
        q = """UNWIND range(0, size($ids)) as i
               WITH $ids[i] AS id, $values[i] AS v
               MATCH (f)
               WHERE ID(f) = id
               SET f += v"""
        
        params = {'ids': ids, 'values': metadata}

        self.g.query(q, params)

    # get all functions defined by file
    def get_functions_in_file(self, path: str, name: str, ext: str) -> List[Function]:
        q = """MATCH (f:File {path: $path, name: $name, ext: $ext})
               MATCH (f)-[:DEFINES]->(func:Function)
               RETURN collect(func)"""

        params = {'path': path, 'name': name, 'ext': ext}
        funcs = self.g.query(q, params).result_set[0][0]
        
        return [self._function_from_node(n) for n in funcs]

    def get_function_by_name(self, name: str) -> Optional[Function]:
        q = "MATCH (f:Function) WHERE f.name = $name RETURN f LIMIT 1"
        res = self.g.query(q, {'name': name}).result_set

        if len(res) == 0:
            return None

        return self._function_from_node(res[0][0])

    def get_function(self, func_id: int) -> Optional[Function]:
        q = """MATCH (f:Function)
               WHERE ID(f) = $func_id
               RETURN f"""
        
        res = self.g.query(q, {'func_id': func_id})

        if len(res.result_set) == 0:
            return None

        node = res.result_set[0][0]

        return self._function_from_node(node)

    def function_calls(self, func_id: int) -> List[Function]:
        q = """MATCH (f:Function)
               WHERE ID(f) = $func_id
               MATCH (f)-[:CALLS]->(callee)
               RETURN callee"""

        res = self.g.query(q, {'func_id': func_id})

        callees = []
        for row in res.result_set:
            callee = row[0]
            callees.append(self._function_from_node(callee))

        return callees
    
    def function_called_by(self, func_id: int) -> List[Function]:
        q = """MATCH (f:Function)
               WHERE ID(f) = $func_id
               MATCH (caller)-[:CALLS]->(f)
               RETURN caller"""

        res = self.g.query(q, {'func_id': func_id})

        callers = []
        for row in res.result_set:
            caller = row[0]
            callers.append(self._function_from_node(caller))

        return callers

    def add_file(self, file: File) -> None:
        """
        Add a file node to the graph database.

        Args:
            file_path (str): Path of the file.
            file_name (str): Name of the file.
            file_ext (str): Extension of the file.
        """

        q = """MERGE (f:File {path: $path, name: $name, ext: $ext})
               RETURN ID(f)"""
        params = {'path': file.path, 'name': file.name, 'ext': file.ext}

        res = self.g.query(q, params)
        file.id = res.result_set[0][0]

    def delete_files(self, files: List[dict]) -> None:
        """
        Deletes file(s) from the graph in addition to any other entity
        defined in the file

        a file is defined by its path, name and extension
        files = [{'path':_, 'name': _, 'ext': _}, ...]
        """

        q = """UNWIND $files as file
               MATCH (f:File {path: file['path'], name: file['name'], ext: file['ext']})
               CALL {
                   WITH f
                   MATCH (f)-[:DEFINES]->(e)
                   DELETE e
               }
               DELETE f
        """

        params = {'files': files}
        self.g.query(q, params)

    def get_file(self, path: str, name: str, ext: str) -> Optional[File]:
        """
        Retrieves a File entity from the graph database based on its path, name, and extension.

        Args:
            path (str): The file path.
            name (str): The file name.
            ext (str): The file extension.

        Returns:
            Optional[File]: The File object if found, otherwise None.

        This method constructs and executes a query to find a file node in the graph
        database with the specified path, name, and extension. If the file node is found,
        it creates and returns a File object with its properties and ID. If no such node
        is found, it returns None.

        Example:
            file = self.get_file('/path/to/file', 'filename', '.py')
        """

        q = """MATCH (f:File {path: $path, name: $name, ext: $ext})
               RETURN f"""
        params = {'path': path, 'name': name, 'ext': ext}

        res = self.g.query(q, params)
        if(len(res.result_set) == 0):
            return None

        node = res.result_set[0][0]

        ext  = node.properties['ext']
        path = node.properties['path']
        name = node.properties['name']
        file = File(path, name, ext)

        file.id = node.id

        return file

    # set file code coverage
    # if file coverage is 100% set every defined function coverage to 100% aswell
    def set_file_coverage(self, path: str, name: str, ext: str, coverage: float) -> None:
        q = """MATCH (f:File {path: $path, name: $name, ext: $ext})
               SET f.coverage_precentage = $coverage
               WITH f
               WHERE $coverage = 1.0
               MATCH (f)-[:DEFINES]->(func:Function)
               SET func.coverage_precentage = 1.0"""

        params = {'path': path, 'name': name, 'ext': ext, 'coverage': coverage}

        res = self.g.query(q, params)

    def connect_entities(self, relation: str, src_id: int, dest_id: int) -> None:
        """
        Establish a relationship between src and dest

        Args:
            src_id (int): ID of the source node.
            dest_id (int): ID of the destination node.
        """

        q = f"""MATCH (src), (dest)
                WHERE ID(src) = $src_id AND ID(dest) = $dest_id
                MERGE (src)-[:{relation}]->(dest)"""

        params = {'src_id': src_id, 'dest_id': dest_id}
        self.g.query(q, params)

    def function_calls_function(self, caller_id: int, callee_id: int, pos: int) -> None:
        """
        Establish a 'CALLS' relationship between two function nodes.

        Args:
            caller_id (int): ID of the caller function node.
            callee_id (int): ID of the callee function node.
            pos (int): line number on which the function call is made.
        """

        q = """MATCH (caller:Function), (callee:Function)
               WHERE ID(caller) = $caller_id AND ID(callee) = $callee_id
               MERGE (caller)-[e:CALLS {pos:$pos}]->(callee)"""

        params = {'caller_id': caller_id, 'callee_id': callee_id, 'pos': pos}
        self.g.query(q, params)

    def add_struct(self, s: Struct) -> None:
        """
        Adds a struct node to the graph database.

        Args:
            s (Struct): The Struct object to be added.
        """

        q = """MERGE (s:Struct {name: $name, path: $path, src_start: $src_start,
                               src_end: $src_end})
               SET s.doc = $doc, s.fields = $fields
               RETURN ID(s)"""

        params = {
            'doc': s.doc,
            'name': s.name,
            'path': s.path,
            'src_start': s.src_start,
            'src_end': s.src_end,
            'fields': s.fields
        }

        res = self.g.query(q, params)
        s.id = res.result_set[0][0]

    def _struct_from_node(self, n: Node) -> Struct:
        """
        Create a Struct from a graph node
        """

        doc       = n.properties.get('doc')
        name      = n.properties.get('name')
        path      = n.properties.get('path')
        src_end   = n.properties.get('src_end')
        src_start = n.properties.get('src_start')
        fields    = n.properties.get('fields')

        s = Struct(path, name, doc, src_start, src_end)

        # Populate struct fields
        if fields is not None:
            for field in fields:
                field_name = field[0]
                field_type = field[1]
                s.add_field(field_name, field_type)

        s.id = n.id

        return s

    def get_struct_by_name(self, struct_name: str) -> Optional[Struct]:
        q = "MATCH (s:Struct) WHERE s.name = $name RETURN s LIMIT 1"
        res = self.g.query(q, {'name': struct_name}).result_set

        if len(res) == 0:
            return None

        return self._struct_from_node(res[0][0])

    def get_struct(self, struct_id: int) -> Optional[Struct]:
        q = """MATCH (s:Struct)
               WHERE ID(s) = $struct_id
               RETURN s"""
        
        res = self.g.query(q, {'struct_id': struct_id})

        if len(res.result_set) == 0:
            return None

        s = res.result_set[0][0]
        return self._struct_from_node(s)

