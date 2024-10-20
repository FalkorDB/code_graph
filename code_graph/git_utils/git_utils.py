import os
import time
import json
import redis
import logging
import threading
import subprocess
from git import Repo
from ..graph import Graph
from .git_graph import GitGraph
from typing import List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

monitor_thread = None
replica_process = None
monitor_exit_event = threading.Event()

def GitRepoName(repo_name):
    return "{" + repo_name + "}_git"

# setup replication to the master
def setup_replication():
    global replica_process

    # start replica server
    command = [
        "redis-server",
        "--port", "6380",
        "--replicaof", "localhost", "6379",
        "--loadmodule", "/Users/roilipman/Dev/FalkorDB/bin/macos-arm64v8-release/src/falkordb.so"
    ]
    replica_process = subprocess.Popen(command)

# closes redis replica
def teardown_replica():
    print("closing replica")

    # Gracefully terminate the process
    replica_process.terminate()

    # Wait for the process to exit
    replica_process.wait()

    print("replica terminated.")

# runs on a dedicated thread, capture GRAPH.EFFECT commands
def _monitor_effects(graph_name):
    # Connect to Redis server
    r = redis.Redis(host='localhost', port=6380)

    # Start monitoring the Redis server
    with r.monitor() as m:
        print("MONITOR ACTIVATED!")
        # Print commands as they are executed on the Redis server
        for command in m.listen():
            print("listening for monitor commands")
            # check for exit signal
            if monitor_exit_event.is_set():
                print("exit signal recived")
                break

            cmd = command['command']
            print(f"cmd: {cmd}")
            if "GRAPH.EFFECT" in cmd and graph_name in cmd:
                # "GRAPH.EFFECT" "FalkorDB" "\x01\x05\x00\x00\x00\x90\x14\x00\x00\x00\x00\x00\x00"
                print(f"Detected effect: {cmd}")

                # save effect

                #{'time': 1728840094.85141, 'db': 0, 'client_address': '[::1]', 'client_port': '6379', 'client_type': 'tcp'
                #, 'command': 'set x 7'}

# monitor graph.effect commands
def start_monitor_effects(graph_name):
    print(f"graph_name: {graph_name}")
    r = redis.Redis(host='localhost', port=6380, decode_responses=True)

    # wait for replica to become responsive
    connected = False
    while not connected:
        # wait one sec
        time.sleep(1)
        try:
            role = r.role()
            connected = (role[0] == 'slave' and role[1] == 'localhost' and role[2] == 6379 and role[3] == 'connected')
        except Exception:
            pass

    print("starting monitor thread")

    monitor_thread = threading.Thread(target=_monitor_effects, args=(graph_name,))
    monitor_thread.start()

    print("monitor thread started")

# stop monitoring graph.effect commands
def stop_monitor_effects():
    print("signaling monitor thread to exit")

    # Signal the thread to exit
    monitor_exit_event.set()

    # Wait for the thread to finish
    monitor_thread.join()

    print("monitor thread exited")

# build a graph capturing the git commit history
def build_commit_graph(path: str, repo_name: str, ignore_list: Optional[List[str]] = []) -> GitGraph:
    repo = Repo(path)

    # Clone graph into a temporary graph
    g =         Graph(repo_name).clone(repo_name + "_tmp")
    git_graph = GitGraph(GitRepoName(repo_name))

    #setup_replication()

    # start monitoring graph effects
    # these capture the changes a graph goes through when moving from one
    # git commit to another
    #start_monitor_effects(g.g.name)

    head_commit = repo.commit("HEAD")

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

        diff = head_commit.diff(prev_commit)

        print(f"hash: {head_commit.hexsha}")
        #print(f"message: {head_commit.message}")

        added = []
        deleted = []
        modified = []

        for change in diff:
            if change.new_file:
                if all(not change.b_path.startswith(ignore) for ignore in ignore_list):
                    #print(f"new_file: {change.b_path}")
                    added.append(change.b_path)
            elif change.deleted_file:
                if all(not change.a_path.startswith(ignore) for ignore in ignore_list):
                    print(f"deleted_file: {change.a_path}")
                    deleted.append(change.a_path)
            elif change.change_type == 'M':
                if all(not change.a_path.startswith(ignore) for ignore in ignore_list):
                    #print(f"modified_file: {change.a_path}")
                    modified.append(change.a_path)

        #-----------------------------------------------------------------------
        # apply changes
        #-----------------------------------------------------------------------

        # apply deletions

        if len(deleted) > 0:
            # TODO: a bit of a waste, compute in previous loop
            deleted_files = [
                    {'path': os.path.dirname(path),
                     'name': os.path.basename(path),
                     'ext' : os.path.splitext(path)[1]} for path in deleted]

            # remove deleted files from the graph
            transition = g.delete_files(deleted_files, True)
            if(transition is not None):
                queries, params = transition
                # log transition action
                git_graph.set_parent_transition(head_commit.hexsha,
                                                prev_commit.hexsha, queries,
                                                json.dumps(params))

        # advance to the next commit
        head_commit = prev_commit

    # clean up
    #stop_monitor_effects()
    #teardown_replica()

    # Delete temporaty graph
    g.delete()

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

    # Determine the direction of the switch (forward or backward in commit history)
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
        p = json.loads(p)
        logging.debug(f"Executing query: {q} with params: {p}")

        # Rerun the query with parameters on the graph
        res = g.rerun_query(q, p)
        if "DELETE" in q:
            deleted_nodes = res.result_set[0][0]
            change_set['deletions']['nodes'] += deleted_nodes

    # Update the graph's commit to the new target commit
    g.set_graph_commit(to)
    logging.info(f"Graph commit updated to {to}")

    return change_set

if __name__ == "__main__":
    build_commit_graph("/Users/roilipman/Dev/FalkorDB")

