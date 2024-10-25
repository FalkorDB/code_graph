import os
import time
import json
import redis
import logging
import threading
import subprocess
from git import Repo
from pathlib import Path
from ..graph import Graph
from .git_graph import GitGraph
from typing import List, Optional
from ..analyzers import SourceAnalyzer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

monitor_thread = None
replica_process = None
monitor_exit_event = threading.Event()

def GitRepoName(repo_name):
    return "{" + repo_name + "}_git"

def is_ignored(file_path: str, ignore_list: List[str]) -> bool:
    """
    Checks if a file should be ignored based on the ignore list.

    Args:
        file_path (str): The file path to check.
        ignore_list (List[str]): List of patterns to ignore.

    Returns:
        bool: True if the file should be ignored, False otherwise.
    """

    return any(file_path.startswith(ignore) for ignore in ignore_list)

def classify_changes(diff, ignore_list: List[str]) -> (List[str], List[str], List[str]):
    """
    Classifies changes into added, deleted, and modified files.

    Args:
        diff: The git diff object representing changes between two commits.
        ignore_list (List[str]): List of file patterns to ignore.

    Returns:
        (List[str], List[str], List[str]): A tuple of lists representing added, deleted, and modified files.
    """

    added, deleted, modified = [], [], []

    for change in diff:
        if change.new_file and not is_ignored(change.b_path, ignore_list):
            print(f"new file: {change.b_path}")
            added.append(Path(change.b_path))
        if change.deleted_file and not is_ignored(change.a_path, ignore_list):
            print(f"deleted file: {change.a_path}")
            deleted.append(change.a_path)
        if change.change_type == 'M' and not is_ignored(change.a_path, ignore_list):
            print(f"change file: {change.a_path}")
            modified.append(Path(change.a_path))

    return added, deleted, modified

# build a graph capturing the git commit history
def build_commit_graph(
        path: str,
        repo_name: str,
        ignore_list: Optional[List[str]] = []
    ) -> GitGraph:
    """
    Builds a graph representation of the git commit history.

    Args:
        path (str): Path to the git repository.
        repo_name (str): Name of the repository.
        ignore_list (List[str], optional): List of file patterns to ignore.

    Returns:
        GitGraph: Graph object representing the commit history.
    """

    # Store original working directory
    original_dir = Path.cwd()

    # change working directory to local repository
    print(f"chdir to: {path}")
    os.chdir(path)

    repo = Repo('.')

    # Clone graph into a temporary graph
    g =         Graph(repo_name).clone(repo_name + "_tmp")
    g.enable_backlog()

    git_graph = GitGraph(GitRepoName(repo_name))
    analyzer = SourceAnalyzer()
    supported_types = analyzer.supported_types()

    # Initialize with the head commit
    head_commit = repo.commit("HEAD")
    head_commit_hexsha = head_commit.hexsha

    repo.git.checkout(head_commit.hexsha)

    # add commit to the git graph
    git_graph.add_commit(head_commit.hexsha, head_commit.author.name,
                 head_commit.message, head_commit.committed_date)

    while len(head_commit.parents) > 0:
        prev_commit = head_commit.parents[0]

        # add commit to the git graph
        git_graph.add_commit(prev_commit.hexsha, prev_commit.author.name,
                 prev_commit.message, prev_commit.committed_date)

        # connect child parent commits relation
        git_graph.connect_commits(head_commit.hexsha, prev_commit.hexsha)

        # represents the changes going backward!
        # e.g. which files need to be deleted when moving back one commit
        #
        # if we were to switch "direction" going forward
        # delete events would become add event
        # e.g. which files need to be added when moving forward from this commit
        #      to the next one

        # Process file changes in this commit
        print(f"commit hash: {head_commit.hexsha}")
        print(f"commit message: {head_commit.message}")
        print(f"prev commit hash: {prev_commit.hexsha}")
        print(f"prev commit message: {prev_commit.message}")
        diff = head_commit.diff(prev_commit)
        added, deleted, modified = classify_changes(diff, ignore_list)

        # Use the repo's git interface to checkout the commit
        repo.git.checkout(prev_commit.hexsha)

        #-----------------------------------------------------------------------
        # apply changes
        #-----------------------------------------------------------------------

        # apply deletions
        # TODO: a bit of a waste, compute in previous loop
        deleted_files = []
        for deleted_file_path in deleted:
            _ext = os.path.splitext(deleted_file_path)[1]
            if _ext in supported_types:
                _path = os.path.dirname(deleted_file_path)
                _name = os.path.basename(deleted_file_path)
                deleted_files.append(
                        {'path': _path, 'name': _name, 'ext' : _ext})

        # remove deleted files from the graph
        print(f"deleted_files: {deleted_files}")
        if len(deleted_files) > 0:
            g.delete_files(deleted_files)

        if len(added) > 0:
            for new_file in added:
                # New file been added
                print(f"new_file: {new_file}")
                analyzer.analyze_file(new_file, g)

        queries, params = g.clear_backlog()
        if len(queries) > 0:
            assert(len(queries) == len(params))
            params = [json.dumps(p) for p in params]

            # log transitions
            git_graph.set_parent_transition(head_commit.hexsha, prev_commit.hexsha,
                                            queries, params)
        # advance to the next commit
        head_commit = prev_commit

    # clean up
    #stop_monitor_effects()
    #teardown_replica()

    # Restore original commit
    repo.git.checkout(head_commit_hexsha)

    # Delete temporaty graph
    g.disable_backlog()
    g.delete()

    # restore working dir
    os.chdir(original_dir)

    return git_graph

def switch_commit(repo: str, to: str) -> dict[str, dict[str, list]]:
    """
    Switches the state of a graph repository from its current commit to the given commit.

    This function handles switching between two git commits for a graph-based repository.
    It identifies the changes (additions, deletions, modifications) in nodes and edges between
    the current commit and the target commit and then applies the necessary transitions.

    Args:
        repo (str): The name of the graph repository to switch commits.
        to (str): The target commit hash to switch the graph to.

    Returns:
        dict: A dictionary containing the changes made during the commit switch, organized by:
            - 'deletions': {
                'nodes': List of node IDs deleted,
                'edges': List of edge IDs deleted
            },
            - 'additions': {
                'nodes': List of new Node objects added,
                'edges': List of new Edge objects added
            },
            - 'modifications': {
                'nodes': List of modified Node objects,
                'edges': List of modified Edge objects
            }
    """

    # Validate input arguments
    if not repo or not isinstance(repo, str):
        raise ValueError("Invalid repository name")

    if not to or not isinstance(to, str):
        raise ValueError("Invalid desired commit value")

    # Initialize return value to an empty change set
    change_set = {
        'deletions': {
            'nodes': [],
            'edges': []
        },
        'additions': {
            'nodes': [],
            'edges': [],
        },
        'modifications': {
            'nodes': [],
            'edges': []
        }
    }

    # Initialize the graph and GitGraph objects
    g = Graph(repo)
    git_graph = GitGraph(GitRepoName(repo))

    # Get the current commit hash of the graph
    current_hash = g.get_graph_commit()
    logging.info(f"Current graph commit: {current_hash}")

    if current_hash == to:
        # No change remain at the current commit
        return change_set

    # Find the path between the current commit and the desired commit
    commits = git_graph.get_commits([current_hash, to])

    # Ensure both current and target commits are present
    if len(commits) != 2:
        logging.error("Missing commits. Unable to proceed.")
        raise ValueError("Commits not found")

    # Identify the current and new commits based on their hashes
    current_commit, new_commit = (commits if commits[0]['hash'] == current_hash else reversed(commits))

    # Determine the direction of the switch (forward or backward in the commit history)
    if current_commit['date'] > new_commit['date']:
        logging.info(f"Moving backward from {current_commit['hash']} to {new_commit['hash']}")
        # Get the transitions (queries and parameters) for moving backward
        queries, params = git_graph.get_parent_transitions(current_commit['hash'], new_commit['hash'])
    else:
        logging.info(f"Moving forward from {current_commit['hash']} to {new_commit['hash']}")
        # Get the transitions (queries and parameters) for moving forward
        queries, params = git_graph.get_child_transitions(current_commit['hash'], new_commit['hash'])

    # Apply each transition query with its respective parameters
    for q, p in zip(queries, params):
        print(f"Switch commit, params: {p}")
        for _q, _p in zip(q, p):
            _p = json.loads(_p)
            logging.debug(f"Executing query: {_q} with params: {_p}")

            # Rerun the query with parameters on the graph
            res = g.rerun_query(_q, _p)
            if "DELETE" in _q:
                deleted_nodes = res.result_set[0][0]
                change_set['deletions']['nodes'] += deleted_nodes

    # Update the graph's commit to the new target commit
    g.set_graph_commit(to)
    logging.info(f"Graph commit updated to {to}")

    return change_set

if __name__ == "__main__":
    build_commit_graph("/Users/roilipman/Dev/FalkorDB")

