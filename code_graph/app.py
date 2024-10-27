import os
import datetime
from code_graph import *
from typing import Optional
from falkordb import FalkorDB
from dotenv import load_dotenv
from urllib.parse import urlparse
from .auto_complete import prefix_search
from flask import Flask, request, jsonify, abort

# Load environment variables from .env file
load_dotenv()

# Configure the logger
import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)

    @app.route('/graph_entities', methods=['GET'])
    def graph_entities():
        """
        Endpoint to fetch sub-graph entities from a given repository.
        The repository is specified via the 'repo' query parameter.

        Returns:
            - 200: Successfully returns the sub-graph.
            - 400: Missing or invalid 'repo' parameter.
            - 500: Internal server error or database connection issue.
        """

        # Access the 'repo' parameter from the GET request
        repo = request.args.get('repo')

        if not repo:
            logging.error("Missing 'repo' parameter in request.")
            return jsonify({"status": "Missing 'repo' parameter"}), 400

        if not graph_exists(repo):
            logging.error(f"Missing project {repo}")
            return jsonify({"status": f"Missing project {repo}"}), 400

        try:
            # Initialize the graph with the provided repo and credentials
            g = Graph(repo)

            # Retrieve a sub-graph of up to 100 entities
            sub_graph = g.get_sub_graph(100)

            logging.info(f"Successfully retrieved sub-graph for repo: {repo}")
            response = {
                'status': 'success',
                'entities': sub_graph
            }

            return jsonify(response), 200

        except Exception as e:
            logging.error(f"Error retrieving sub-graph for repo '{repo}': {e}")
            return jsonify({"status": "Internal server error"}), 500


    @app.route('/get_neighbors', methods=['GET'])
    def get_neighbors():
        """
        Endpoint to get neighbors of a specific node in the graph.
        Expects 'repo' and 'node_id' as query parameters.

        Returns:
            JSON response containing neighbors or error messages.
        """

        # Get query parameters
        repo    = request.args.get('repo')
        node_id = request.args.get('node_id')

        # Validate 'repo' parameter
        if not repo:
            logging.error("Repository name is missing in the request.")
            return jsonify({"status": "Repository name is required."}), 400

        # Validate 'node_id' parameter
        if not node_id:
            logging.error("Node ID is missing in the request.")
            return jsonify({"status": "Node ID is required."}), 400

        # Validate repo exists
        if not graph_exists(repo):
            logging.error(f"Missing project {repo}")
            return jsonify({"status": f"Missing project {repo}"}), 400

        # Try converting node_id to an integer
        try:
            node_id = int(node_id)
        except ValueError:
            logging.error(f"Invalid node ID: {node_id}. It must be an integer.")
            return jsonify({"status": "Invalid node ID. It must be an integer."}), 400

        # Initialize the graph with the provided repository
        g = Graph(repo)

        # Fetch the neighbors of the specified node
        neighbors = g.get_neighbors(node_id)

        # Log and return the neighbors
        logging.info(f"Successfully retrieved neighbors for node ID {node_id} in repo '{repo}'.")

        response = {
            'status': 'success',
            'neighbors': neighbors
        }

        return jsonify(response), 200


    @app.route('/process_repo', methods=['POST'])
    def process_repo():
        """
        Process a GitHub repository.

        Expected JSON payload:
        {
            "repo_url": "string",
            "ignore": ["string"]  # optional
        }

        Returns:
            JSON response with processing status
        """

        data = request.get_json()
        url = data.get('repo_url')
        if url is None:
            return jsonify({'status': f'Missing mandatory parameter "url"'}), 400
        logger.debug(f'Received repo_url: {url}')

        ignore = data.get('ignore', [])

        proj = Project.from_git_repository(url)
        proj.analyze_sources(ignore)
        proj.process_git_history(ignore)

        # Create a response
        response = {
            'status': 'success',
        }

        return jsonify(response), 200

    @app.route('/process_local_repo', methods=['POST'])
    def process_local_repo():
        # Get JSON data from the request
        data = request.get_json()

        # Process the data
        repo = data.get('repo')
        if repo is None:
            return jsonify({'status': f'Missing mandatory parameter "repo"'}), 400
        logger.debug(f'Received repo: {repo}')

        ignore = data.get('ignore')
        if ignore is not None:
            logger.debug(f"Ignoring the following paths: {ignore}")

        # Create source code analyzer
        analyzer = SourceAnalyzer()

        try:
            analyzer.analyze_local_repository(repo, ignore)
        except Exception as e:
            logger.error(f'An error occurred: {e}')
            return jsonify({'status': f'Failed to process repository: {repo}'}), 400

        # Create a response
        response = {
            'status': 'success',
        }

        return jsonify(response), 200

    @app.route('/process_code_coverage', methods=['POST'])
    def process_code_coverage():
        """
        Endpoint to process code coverage data for a given repository.

        Returns:
            JSON response indicating success or an error message.
        """

        # Get JSON data from the request
        data = request.get_json()

        # Validate that 'repo' is provided
        repo = data.get('repo')
        if repo is None:
            logging.warning("Missing mandatory parameter 'repo'")
            return jsonify({'status': 'error', 'message': 'Missing mandatory parameter "repo"'}), 400

        # Validate that 'lcov' is provided
        lcov = data.get('lcov')
        if lcov is None:
            logging.warning("Missing mandatory parameter 'lcov'")
            return jsonify({'status': f'Missing mandatory parameter "lcov"'}), 400

        # Process the lcov data for the repository
        process_lcov(repo, lcov)

        # Create a success response
        response = {
            'status': 'success',
        }

        return jsonify(response), 200


    @app.route('/switch_commit', methods=['POST'])
    def switch_commit():
        """
        Endpoint to switch a repository to a specific commit.

        Returns:
            JSON response with the change set or an error message.
        """

        # Get JSON data from the request
        data = request.get_json()

        # Validate that 'repo' is provided
        repo = data.get('repo')
        if repo is None:
            return jsonify({'status': f'Missing mandatory parameter "repo"'}), 400

        # Validate that 'commit' is provided
        commit = data.get('commit')
        if commit is None:
            return jsonify({'status': f'Missing mandatory parameter "commit"'}), 400

        # Attempt to switch the repository to the specified commit
        change_set = switch_commit(repo, commit)

        # Create a success response
        response = {
            'status': 'success',
            'change_set': change_set
        }

        return jsonify(response), 200

    @app.route('/auto_complete', methods=['POST'])
    def auto_complete():
        """
        Endpoint to process auto-completion requests for a repository based on a prefix.

        Returns:
            JSON response with auto-completion suggestions or an error message.
        """

        # Get JSON data from the request
        data = request.get_json()

        # Validate that 'repo' is provided
        repo = data.get('repo')
        if repo is None:
            return jsonify({'status': f'Missing mandatory parameter "repo"'}), 400

        # Validate that 'prefix' is provided
        prefix = data.get('prefix')
        if prefix is None:
            return jsonify({'status': f'Missing mandatory parameter "prefix"'}), 400

        # Validate repo exists
        if not graph_exists(repo):
            return jsonify({'status': f'Missing project {repo}'}), 400

        # Fetch auto-completion results
        completions = prefix_search(repo, prefix)

        # Create a success response
        response = {
            'status': 'success',
            'completions': completions
        }

        return jsonify(response), 200


    @app.route('/list_repos', methods=['GET'])
    def list_repos():
        """
        Endpoint to list all available repositories.

        Returns:
            JSON response with a list of repositories or an error message.
        """

        # Fetch list of repositories
        repos = get_repos()

        # Create a success response with the list of repositories
        response = {
            'status': 'success',
            'repositories': repos
        }

        return jsonify(response), 200


    @app.route('/list_commits', methods=['POST'])
    def list_commits():
        """
        Endpoint to list all commits of a specified repository.

        Request JSON Structure:
        {
            "repo": "repository_name"
        }

        Returns:
            JSON response with a list of commits or an error message.
        """

        # Get JSON data from the request
        data = request.get_json()

        # Validate the presence of the 'repo' parameter
        repo = data.get('repo')
        if repo is None:
            return jsonify({'status': f'Missing mandatory parameter "repo"'}), 400

        # Initialize GitGraph object to interact with the repository
        git_graph = GitGraph(GitRepoName(repo))

        # Fetch commits from the repository
        commits = git_graph.list_commits()

        # Return success response with the list of commits
        response = {
            'status': 'success',
            'commits': commits
        }

        return jsonify(response), 200


    @app.route('/repo_info', methods=['POST'])
    def repo_info():
        """
        Endpoint to retrieve information about a specific repository.

        Expected JSON payload:
            {
                "repo": <repository name>
            }

        Returns:
            JSON: A response containing the status and graph statistics (node and edge counts).
                - 'status': 'success' if successful, or an error message.
                - 'info': A dictionary with the node and edge counts if the request is successful.
        """

        # Get JSON data from the request
        data = request.get_json()

        # Validate the 'repo' parameter
        repo = data.get('repo')
        if repo is None:
            return jsonify({'status': f'Missing mandatory parameter "repo"'}), 400

        # Initialize the graph with the provided repository name
        g = Graph(repo)

        # Retrieve statistics from the graph
        stats = g.stats()
        info = get_repo_info(repo)

        if stats is None or info is None:
            return jsonify({'status': f'Missing repository "{repo}"'}), 400

        stats |= info 

        # Create a response
        response = {
            'status': 'success',
            'info': stats
        }

        print(f"response: {response}")

        return jsonify(response), 200

    @app.route('/find_paths', methods=['POST'])
    def find_paths():
        """
        Finds all paths between a source node (src) and a destination node (dest) in the graph.
        The graph is associated with the repository (repo) provided in the request.

        Request Body (JSON):
            - repo (str): Name of the repository.
            - src (int): ID of the source node.
            - dest (int): ID of the destination node.

        Returns:
            A JSON response with:
            - status (str): Status of the request ("success" or "error").
            - paths (list): List of paths between the source and destination nodes.
        """

        # Get JSON data from the request
        data = request.get_json()

        # Validate 'repo' parameter
        repo = data.get('repo')
        if repo is None:
            return jsonify({'status': f'Missing mandatory parameter "repo"'}), 400

        # Validate 'src' parameter
        src = data.get('src')
        if src is None:
            return jsonify({'status': f'Missing mandatory parameter "src"'}), 400
        if not isinstance(src, int):
            return jsonify({'status': "src node id must be int"}), 400

        # Validate 'dest' parameter
        dest = data.get('dest')
        if dest is None:
            return jsonify({'status': f'Missing mandatory parameter "dest"'}), 400
        if not isinstance(dest, int):
            return jsonify({'status': "dest node id must be int"}), 400

        if not graph_exists(repo):
            logging.error(f"Missing project {repo}")
            return jsonify({"status": f"Missing project {repo}"}), 400

        # Initialize graph with provided repo and credentials
        g = Graph(repo)

        # Find paths between the source and destination nodes
        paths = g.find_paths(src, dest)

        # Create and return a successful response
        response = { 'status': 'success', 'paths': paths }

        return jsonify(response), 200


    @app.route('/unreachable', methods=['POST'])
    def unreachable_entities():
        """
        Endpoint to retrieve unreachable entities in the graph.
        Expects 'repo', optional 'label', and optional 'relation' as parameters in the POST request.

        Returns:
            JSON response with unreachable entities or error message.
        """

        # Get JSON data from the request
        data = request.get_json()

        # Validate 'repo' parameter
        repo = data.get('repo')
        if repo is None:
            return jsonify({'status': f'Missing mandatory parameter "repo"'}), 400

        # Get optional 'label' and 'relation' parameters
        lbl = data.get('label', None)
        rel = data.get('relation', None)

        # Initialize graph with provided repo and credentials
        g = Graph(repo)

        # Fetch unreachable entities based on optional label and relation
        unreachable_entities = g.unreachable_entities(lbl, rel)

        # Create and return a successful response
        response = { 'status': 'success', 'unreachables ': unreachable_entities }

        return jsonify(response), 200

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)

