import os
import time
import json
import redis
import threading
import subprocess
from git import Repo
from ..graph import Graph
from .git_graph import GitGraph
from typing import List, Optional

monitor_thread = None
replica_process = None
monitor_exit_event = threading.Event()

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
def build_commit_graph(path: str, ignore_list: Optional[List[str]] = []) -> GitGraph:
    print(f"Processing git history at: {path}")
    print(f"ignoring the following paths: {ignore_list}")

    repo = Repo(path)

    repo_name = os.path.split(os.path.normpath(path))[-1]
    g =         Graph(repo_name)
    git_graph = GitGraph('{' + repo_name + '}' + '_git')

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

    return git_graph

def switch_commit(repo: str, to: str):
    """switch graph state from its current commit to given commit"""

    g = Graph(repo)
    git_graph = GitGraph('{' + repo + '}' + 'git')

    # Get the graph's current commit
    current_hash = g.get_graph_commit()

    # Find path from current commit to desired commit
    commits = git_graph.get_commits([current_hash, to])

    if len(commits) != 2:
        print("missing commits")
        return

    # determine relation between commits
    current_commit = commits[0] if commits[0]['hash'] == current_hash else commits[1]
    new_commit     = commits[0] if commits[0]['hash'] == to else commits[1]

    if current_commit['date'] > new_commit['date']:
        print("moving backwared")
        queries, params = git_graph.get_parent_transition(current_commit['hash'], new_commit['hash'])
    else:
        print("moving forwards")
        queries, params = git_graph.get_child_transition(current_commit['hash'], new_commit['hash'])

    # Apply transitions
    for i in range(0, len(queries)):
        q = queries[i]
        p = json.loads(params[i])
        print(f"query: {q}")
        print(f"params: {p}")

        g.rerun_query(q, p)

    # update graph's commit
    g.set_graph_commit(to)

if __name__ == "__main__":
    build_commit_graph("/Users/roilipman/Dev/FalkorDB")

