from falkordb import FalkorDB
from typing import List, Optional

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


    def add_commit(self, commit_hash: str, author: str, message: str, date: int) -> None:
        """
            Add a new commit to the graph
        """
        q = "MERGE (c:Commit {hash: $hash, author: $author, message: $message, date: $date})"
        params = {'hash': commit_hash, 'author': author, 'message': message, 'date': date}
        self.g.query(q, params)

    def get_commits(self, hashes: List[str]) -> List[dict]:
        q = """MATCH (c:Commit)
               WHERE c.hash IN $hashes
               RETURN c"""

        params = {'hashes': hashes}
        res = self.g.query(q, params).result_set

        commits = []
        for row in res:
            commit = row[0]
            commit = {'hash':    commit.properties['hash'],
                      'date':    commit.properties['date'],
                      'author':  commit.properties['author'],
                      'message': commit.properties['message']}

            commits.append(commit)

        return commits

    def connect_commits(self, child: str, parent: str) -> None:
        """
            connect commits via both PARENT and CHILD edges
        """

        q = """MATCH (child :Commit {hash: $child_hash}), (parent :Commit {hash: $parent_hash})
               MERGE (child)-[:PARENT]->(parent)
               MERGE (parent)-[:CHILD]->(child)"""

        params = {'child_hash': child, 'parent_hash': parent}

        self.g.query(q, params)


    def set_parent_transition(self, child: str, parent: str, queries: [str], params: [dict]) -> None:
        """
            Sets the queries and parameters needed to transition the code-graph
            from the child commit to the parent commit
        """

        q = """MATCH (child :Commit {hash: $child})-[e:PARENT]->(parent :Commit {hash: $parent})
               SET e.queries = $queries, e.params = $params"""

        params = {'child': child, 'parent': parent, 'queries': queries, 'params': params}

        self.g.query(q, params)


    def set_child_transition(self, child: str, parent: str, queries: List[tuple[str: dict]]) -> None:
        """
            Sets the queries and parameters needed to transition the code-graph
            from the parent commit to the child commit
        """

        q = """MATCH (parent :Commit {hash: $parent})-[e:CHILD]->(child :Commit {hash: $child})
               SET e.queries = $queries, e.params = $params"""

        params = {'child': child, 'parent': parent, 'queries': queries}

        self.g.query(q, params)


    def get_parent_transition(self, child: str, parent: str) -> List[tuple[str: dict]]:
        """
            Get queries and parameters transitioning from child commit to parent commit
        """
        q = """MATCH path = (:Commit {hash: $child_hash})-[:PARENT*]->(:Commit {hash: $parent_hash})
               WITH path
               LIMIT 1
               UNWIND relationships(path) AS e
               WITH e
               WHERE e.queries is not NULL
               RETURN collect(e.queries), collect(e.params)
        """

        res = self.g.query(q, {'child_hash': child, 'parent_hash': parent}).result_set

        return (res[0][0], res[0][1])


    def get_child_transition(self, child: str, parent: str) -> List[tuple[str: dict]]:
        """
            Get queries transitioning from parent to child
        """
        q = """MATCH path = (:Commit {hash: $parent_hash})-[:CHILD*]->(:Commit {hash: $child_hash})
               WITH path
               LIMIT 1
               UNWIND relationships(path) AS e
               WITH e
               WHERE e.queries is not NULL
               RETURN collect(e.queries), collect(e.params)
        """

        res = self.g.query(q, {'child_hash': child, 'parent_hash': parent}).result_set

        return (res[0][0], res[0][1])

