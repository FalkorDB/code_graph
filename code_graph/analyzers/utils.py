from typing import Union
from tree_sitter import Node

def print_node(node, indent=0):
    """
    Recursively print a tree-sitter node and its children.

    Args:
        node: The tree-sitter node to print.
        indent: The current indentation level for pretty printing.
    """
    indent_str = '  ' * indent
    print(f"{indent_str}{node.type}")

    for child in node.children:
        print_node(child, indent + 1)

def find_child_of_type(node: Node, child_type: str) -> Union[tuple[Node, int], None]:
    for idx, child in enumerate(node.children):
        if child.type == child_type:
            return (child, idx)

    return None
