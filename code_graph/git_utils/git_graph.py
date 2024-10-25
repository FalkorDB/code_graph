import os
from falkordb import FalkorDB, Node
from typing import List, Optional

class GitGraph():
    """
    Represents a git commit graph
    nodes are commits where one commit leads to its parents and children
    edges contains queries and parameters for transitioning the code-graph
    from the current commit to parent / child
    """

    def __init__(self, name: str):

        self.db = FalkorDB(host=os.getenv('FALKORDB_HOST', 'localhost'),
                           port=os.getenv('FALKORDB_PORT', 6379),
                           username=os.getenv('FALKORDB_USERNAME', None),
                           password=os.getenv('FALKORDB_PASSWORD', None))

        self.g = self.db.select_graph(name)

        # create indicies
        # index commit hash
        try:
            self.g.create_node_range_index("Commit", "hash")
        except Exception:
            pass

    def _commit_from_node(self, node:Node) -> dict:
        """
            Returns a dict representing a commit node
        """

        return {'hash':    node.properties['hash'],
                'date':    node.properties['date'],
                'author':  node.properties['author'],
                'message': node.properties['message']}

    def add_commit(self, commit_hash: str, author: str, message: str, date: int) -> None:
        """
            Add a new commit to the graph
        """
        q = "MERGE (c:Commit {hash: $hash, author: $author, message: $message, date: $date})"
        params = {'hash': commit_hash, 'author': author, 'message': message, 'date': date}
        self.g.query(q, params)

    def list_commits(self) -> List[Node]:
        """
        List all commits
        """

        q = "MATCH (c:Commit) RETURN c ORDER BY c.date"
        result_set = self.g.query(q).result_set

        return [self._commit_from_node(row[0]) for row in result_set]

    def get_commits(self, hashes: List[str]) -> List[dict]:
        q = """MATCH (c:Commit)
               WHERE c.hash IN $hashes
               RETURN c"""

        params = {'hashes': hashes}
        res = self.g.query(q, params).result_set

        commits = []
        for row in res:
            commit = self._commit_from_node(row[0])
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


    def set_parent_transition(self, child: str, parent: str, queries: [str], params: [str]) -> None:
        """
            Sets the queries and parameters needed to transition the code-graph
            from the child commit to the parent commit
        """

        q = """MATCH (child :Commit {hash: $child})-[e:PARENT]->(parent :Commit {hash: $parent})
               SET e.queries = $queries, e.params = $params"""

        _params = {'child': child, 'parent': parent, 'queries': queries, 'params': params}

        self.g.query(q, _params)


    def set_child_transition(self, child: str, parent: str, queries: [str], params: [str]) -> None:
        """
            Sets the queries and parameters needed to transition the code-graph
            from the parent commit to the child commit
        """

        q = """MATCH (parent :Commit {hash: $parent})-[e:CHILD]->(child :Commit {hash: $child})
               SET e.queries = $queries, e.params = $params"""

        _params = {'child': child, 'parent': parent, 'queries': queries}

        self.g.query(q, _params)


    def get_parent_transitions(self, child: str, parent: str) -> List[tuple[str: dict]]:
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


    def get_child_transitions(self, child: str, parent: str) -> List[tuple[str: dict]]:
        """
            Get queries and parameters transitioning from parent commit to child commit
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

