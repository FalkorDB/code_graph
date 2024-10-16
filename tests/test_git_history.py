import os
import unittest
from git import Repo
from code_graph import build_commit_graph

class Test_Git_History(unittest.TestCase):
    def test_git_graph_structure(self):
        # Get the current file path
        current_file_path = os.path.abspath(__file__)

        # Get the directory of the current file
        current_dir = os.path.dirname(current_file_path)

        # Append 'git_repo' to the current directory
        repo_dir = os.path.join(current_dir, 'git_repo')
        repo_dir = str(repo_dir)

        # Build git commit graph
        git_graph = build_commit_graph(repo_dir)

        # validate git graph structure
        repo = Repo(repo_dir)
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

    def test_git_transitions(self):
        pass

