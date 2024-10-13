import os
from git import Repo
from ..graph import Graph

# build a graph capturing the git commit history
def build_commit_graph(path: str):
    repo = Repo(path)

    repo_name = os.path.split(os.path.normpath(path))[-1]
    g = Graph(repo_name)

    head_commit = repo.commit("HEAD")
    while len(head_commit.parents) > 0:
        prev_commit = head_commit.parents[0]

        # represents the changes going backward!
        # e.g. which files need to be deleted when moving back one commit
        #
        # if we were to switch "direction" going forward
        # delete events would become add event
        # e.g. which files need to be added when moving forward from this commit
        #      to the next one

        diff = head_commit.diff(prev_commit)

        print(f"hash: {head_commit.hexsha}")
        print(f"message: {head_commit.message}")

        for change in diff:
            added = []
            deleted = []
            modified = []

            if change.new_file:
                #print(f"new_file: {change.b_path}")
                added.append(change.b_path)
                pass
            elif change.deleted_file:
                print(f"deleted_file: {change.a_path}")
                deleted.append(change.a_path)
            elif change.change_type == 'M':
                #print(f"modified_file: {change.a_path}")
                modified.append(change.a_path)
                pass

            head_commit = prev_commit

            #-------------------------------------------------------------------
            # apply changes
            #-------------------------------------------------------------------

            # apply deletions

            if len(deleted_file) > 0:
                deleted_files = [
                        {'path': os.path.dirname(path),
                         'name': os.path.basename(path),
                         'ext' : os.path.splitext(path)[1]} for path in deleted]

                # remove deleted files from the graph
                g.delete_files(deleted_files)

if __name__ == "__main__":
    build_commit_graph("/Users/roilipman/Dev/FalkorDB")

