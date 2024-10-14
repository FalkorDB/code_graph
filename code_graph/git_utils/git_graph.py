class GitGraph():
    """
    Represents a git commit graph
    nodes are commits where one commit leads to its parents and children
    edges contains queries and parameters for transitioning the code-graph
    from the current commit to parent / child
    """

    def __init__(self, name: str, host: str = 'localhost', port: int = 6379,
                 username: Optional[str] = None, password: Optional[str] = None):

        self.db = FalkorDB(host=host, port=port, username=username,
                           password=password)
        self.g = self.db.select_graph(name)

        # create indicies
        # index commit hash
        try:
            self.g.create_node_range_index("Commit", "hash")
        except Exception:
            pass


    def add_commit(self, commit_hash: str, author: str, message: str, date, int) -> None:
        """
            Add a new commit to the graph
        """
        q = "MERGE (c:Commit {hash: $hash, author: $author, message: $message, date: $date})"
        params = {'hash': commit_hash, 'author': author, 'message': message, 'date': $date}
        self.g.query(q, params)


    def connect_commits(child: str, parent: str) -> None:
        """
            connect commits via both PARENT and CHILD edges
        """

        q = """MATCH (child :Commit {hash: $child_hash}), (parent :Commit {hash: $parent_hash})
               MERGE (child)-[:PARENT]->(parent)
               MERGE (parent)-[:CHILD]->(child)"""

        params = {'child_hash': child, 'parent_hash': parent}

        self.g.query(q, parent)

    def set_parent_transition(child: str, parent: str, queries: [tuple[str: dict]]) -> None:
        """
            Sets the queries and parameters needed to transition the code-graph
            from the child commit to the parent commit
        """

        q = """MATCH (child: Commit {hash: $child})-[e:PARENT]->(parent {hash: $parent})
               SET e.queries = $queries, e.params = $params"""

        params = {'child': child, 'parent': parent, 'queries': queries}

        self.g.query(q, params)

    def set_child_transition(child: str, parent: str, queries: [tuple[str: dict]]) -> None:
        """
            Sets the queries and parameters needed to transition the code-graph
            from the parent commit to the child commit
        """

        q = """MATCH (parent {hash: $parent})-[e:CHILD]->(child: Commit {hash: $child})
               SET e.queries = $queries, e.params = $params"""

        params = {'child': child, 'parent': parent, 'queries': queries}

        self.g.query(q, params)
