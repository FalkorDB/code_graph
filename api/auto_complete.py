from .graph import Graph

def prefix_search(repo: str, prefix: str) -> str:
    g = Graph(repo)
    return g.prefix_search(prefix)

