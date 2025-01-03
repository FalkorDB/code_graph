import io
import os
from ..utils import *
from pathlib import Path
from ...entities import *
from ...graph import Graph
from typing import Optional
from ..analyzer import AbstractAnalyzer

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser, Node

JAVA_LANGUAGE = Language(tsjava.language())

import logging
logger = logging.getLogger('code_graph')

class JavaAnalyzer(AbstractAnalyzer):
    def __init__(self) -> None:
        self.parser = Parser(JAVA_LANGUAGE)

    def process_method_declaration(self, node: Node, path: Path, source_code: str) -> Optional[Function]:
        """
        Processes a method declaration node to extract method details.

        Args:
            node (Node): The AST node representing a method declaration.
            path (Path): The file path where the method is defined.

        Returns:
            Optional[Function]: A Function object containing details about the method, or None if the method name cannot be determined.
        """

        # Extract method name
        res = find_child_of_type(node, 'identifier')
        if res is None:
            return None

        identifier = res[0]
        method_name = identifier.text.decode('utf-8')
        logger.info(f"Method declaration: {method_name}")

        # Extract method return type
        res = find_child_of_type(node, 'type')
        ret_type = 'Unknown'
        if res is not None:
            ret_type = res[0]
            ret_type = ret_type.text.decode('utf-8')

        # Extract method parameters
        args = []
        res = find_child_of_type(node, 'formal_parameters')
        if res is not None:
            parameters = res[0]

            # Extract arguments and their types
            for child in parameters.children:
                if child.type == 'formal_parameter':
                    arg_type = find_child_of_type(child, 'type')[0].text.decode('utf-8')
                    arg_name = find_child_of_type(child, 'identifier')[0].text.decode('utf-8')
                    args.append((arg_name, arg_type))

        # Extract method definition line numbers
        start_line = node.start_point[0]
        end_line = node.end_point[0]

        # Create Function object
        docs = ''
        src = source_code[node.start_byte:node.end_byte]
        f = Function(str(path), method_name, docs, ret_type, src, start_line, end_line)

        # Add arguments to Function object
        for arg in args:
            name, type_ = arg
            f.add_argument(name, type_)

        return f

    def process_class_declaration(self, node: Node, path: Path) -> Optional[Class]:
        """
        Processes a class declaration node to extract class details.

        Args:
            node (Node): The AST node representing a class declaration.
            path (Path): The file path where the class is defined.

        Returns:
            Optional[Class]: A Class object containing details about the class, or None if the class name cannot be determined.
        """

        # Extract class name
        res = find_child_of_type(node, 'identifier')
        if res is None:
            return None

        identifier = res[0]
        class_name = identifier.text.decode('utf-8')
        logger.info(f"Class declaration: {class_name}")

        # Extract class definition line numbers
        start_line = node.start_point[0]
        end_line = node.end_point[0]

        # Create Class object
        docs = ''
        c = Class(str(path), class_name, docs, start_line, end_line)

        return c

    def first_pass(self, path: Path, f: io.TextIOWrapper, graph: Graph) -> None:
        """
        Perform the first pass processing of a Java source file.

        Args:
            path (Path): The path to the Java source file.
            f (io.TextIOWrapper): The file object representing the opened Java source file.
            graph (Graph): The Graph object where entities will be added.

        Returns:
            None
        """

        if path.suffix != '.java':
            logger.debug(f"Skipping none Java file {path}")
            return

        logger.info(f"Processing {path}")

        # Create file entity
        file = File(os.path.dirname(path), path.name, path.suffix)
        graph.add_file(file)

        # Parse file
        source_code = f.read()
        tree = self.parser.parse(source_code)
        try:
            source_code = source_code.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed decoding source code: {e}")
            source_code = ''

        # Process class declarations
        query = JAVA_LANGUAGE.query("(class_declaration) @class")
        captures = query.captures(tree.root_node)
        if 'class' in captures:
            classes = captures['class']
            for node in classes:
                entity = self.process_class_declaration(node, path)
                if entity is not None:
                    graph.add_class(entity)
                    graph.connect_entities('DEFINES', file.id, entity.id)

        # Process method declarations
        query = JAVA_LANGUAGE.query("(method_declaration) @method")
        captures = query.captures(tree.root_node)
        if 'method' in captures:
            methods = captures['method']
            for node in methods:
                entity = self.process_method_declaration(node, path, source_code)
                if entity is not None:
                    graph.add_function(entity)
                    graph.connect_entities('DEFINES', file.id, entity.id)

    def second_pass(self, path: Path, f: io.TextIOWrapper, graph: Graph) -> None:
        """
        Perform the second pass processing of a Java source file to establish method call relationships.

        Args:
            path (Path): The path to the Java source file.
            f (io.TextIOWrapper): The file object representing the opened Java source file.
            graph (Graph): The Graph object containing entities (methods and files) to establish relationships.

        Returns:
            None
        """

        if path.suffix != '.java':
            logger.debug(f"Skipping none Java file {path}")
            return

        logger.info(f"Processing {path}")

        # Get file entity
        file = graph.get_file(os.path.dirname(path), path.name, path.suffix)
        if file is None:
            logger.error(f"File entity not found for: {path}")
            return

        try:
            # Parse file
            content = f.read()
            tree = self.parser.parse(content)
        except Exception as e:
            logger.error(f"Failed to process file {path}: {e}")
            return

        # Locate method invocation
        query_call_exp = JAVA_LANGUAGE.query("(method_invocation) @call")

        # Locate method declarations
        query_method_def = JAVA_LANGUAGE.query("(method_declaration) @method")

        method_defs = query_method_def.captures(tree.root_node)
        for method_def in method_defs:
            caller = method_def[0]
            caller_name = caller.child_by_field_name('identifier').text.decode('utf-8')
            caller_f = graph.get_function_by_name(caller_name)
            assert(caller_f is not None)

            method_calls = query_call_exp.captures(caller.parent.parent)
            for method_call in method_calls:
                callee = method_call[0]
                callee_name = callee.child_by_field_name('identifier').text.decode('utf-8')
                callee_f = graph.get_function_by_name(callee_name)

                if callee_f is None:
                    # Create missing method
                    # Assuming this is a call to a native method e.g. 'println'
                    callee_f = Function('/', callee_name, None, None, None, 0, 0)
                    graph.add_function(callee_f)

                # Connect the caller and callee in the graph
                graph.connect_entities('CALLS', caller_f.id, callee_f.id)
