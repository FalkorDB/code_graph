from typing import List
from .graph import Graph
from .entities import Function

def auto_complete(repo: str, prefix: str) -> str:
    g = Graph(repo)
    return g.prefix_search(prefix)

