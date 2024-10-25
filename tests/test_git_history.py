import os
import unittest
from git import Repo
from code_graph import (
    switch_commit,
    build_commit_graph,
    SourceAnalyzer,
    Graph
)

repo      = None
graph     = None
git_graph = None

class Test_Git_History(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This runs once before all tests in this class

        global repo
        global graph
        global git_graph

        # Get the current file path
        current_file_path = os.path.abspath(__file__)

        # Get the directory of the current file
        current_dir = os.path.dirname(current_file_path)

        # Append 'git_repo' to the current directory
        repo_dir = os.path.join(current_dir, 'git_repo')

        repo = Repo(repo_dir)
        repo.git.checkout("HEAD")

        # Create source code analyzer
        analyzer  = SourceAnalyzer()
        graph     = analyzer.analyze_local_repository(str(repo_dir))
        git_graph = build_commit_graph(repo_dir, 'git_repo')

    def test_git_graph_structure(self):
        # validate git graph structure
        c = repo.commit("HEAD")

        while True:
            commits = git_graph.get_commits([c.hexsha])

            self.assertEqual(len(commits), 1)
            actual = commits[0]

            self.assertEqual(c.hexsha, actual['hash'])
            self.assertEqual(c.committed_date, actual['date'])
            self.assertEqual(c.author.name, actual['author'])
            self.assertEqual(c.message, actual['message'])

            # Advance to previous commit
            if len(c.parents) == 0:
                break

            c = c.parents[0]

    def assert_file_not_exists(self, path: str, name: str, ext: str) -> None:
        f = graph.get_file(path, name, ext)
        self.assertIsNone(f)

    def assert_file_exists(self, path: str, name: str, ext: str) -> None:
        f = graph.get_file(path, name, ext)

        self.assertIsNotNone(f)
        self.assertEqual(f.ext, ext)
        self.assertEqual(f.path, path)
        self.assertEqual(f.name, name)

    def test_git_transitions(self):
        # our test git repo:
        #
        # commit df8d021dbae077a39693c1e76e8438006d62603e (HEAD, main)
        # removed b.py

        # commit 5ec6b14612547393e257098e214ae7748ed12c50
        # added both b.py and c.py

        # commit c4332d05bc1b92a33012f2ff380b807d3fbb9c2e
        # modified a.py

        # commit fac1698da4ee14c215316859e68841ae0b0275b0
        # created a.py
        
        #-----------------------------------------------------------------------
        # HEAD commit
        #-----------------------------------------------------------------------

        # a.py and c.py should exists
        self.assert_file_exists("", "a.py", ".py")
        self.assert_file_exists("", "c.py", ".py")

        # b.py shouldn't exists
        self.assert_file_not_exists("", "b.py", ".py")

        #-----------------------------------------------------------------------
        # commit 5ec6b14612547393e257098e214ae7748ed12c50
        #-----------------------------------------------------------------------

        switch_commit('git_repo', '5ec6b14612547393e257098e214ae7748ed12c50')

        # a.py, b.py and c.py should exists
        self.assert_file_exists("", "a.py", ".py")
        self.assert_file_exists("", "b.py", ".py")
        self.assert_file_exists("", "c.py", ".py")

        #-----------------------------------------------------------------------
        # commit c4332d05bc1b92a33012f2ff380b807d3fbb9c2e
        #-----------------------------------------------------------------------

        switch_commit('git_repo', 'c4332d05bc1b92a33012f2ff380b807d3fbb9c2e')

        # only a.py, should exists
        self.assert_file_exists("", "a.py", ".py")

        # b.py and c.py shouldn't exists
        self.assert_file_not_exists("", "b.py", ".py")
        self.assert_file_not_exists("", "c.py", ".py")

        #-----------------------------------------------------------------------
        # commit fac1698da4ee14c215316859e68841ae0b0275b0
        #-----------------------------------------------------------------------

        switch_commit('git_repo', 'fac1698da4ee14c215316859e68841ae0b0275b0')

        # only a.py, should exists
        self.assert_file_exists("", "a.py", ".py")

        # b.py and c.py shouldn't exists
        self.assert_file_not_exists("", "b.py", ".py")
        self.assert_file_not_exists("", "c.py", ".py")

