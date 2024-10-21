import os
import redis
import datetime
from code_graph import *
from typing import Optional
from falkordb import FalkorDB
from dotenv import load_dotenv
from urllib.parse import urlparse
from flask import Flask, request, jsonify, abort

# Load environment variables from .env file
load_dotenv()

# Access environment variables
app = Flask(__name__, static_folder='static')

# Configure the logger
import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_org_name_from_url(url: str) -> Optional[tuple[str, str]]:
    components = url.split('/')
    n = len(components)
    
    # https://github.com/falkordb/falkordb
    # Expecting atleast 4 components
    if n < 4:
        return None
    
    return (components[n-2], components[n-1])

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
        return jsonify({"error": "Missing 'repo' parameter"}), 400

    try:
        # Initialize the graph with the provided repo and credentials
        g = Graph(repo)

        # Retrieve a sub-graph of up to 100 entities
        sub_graph = g.get_sub_graph(100)

        logging.info(f"Successfully retrieved sub-graph for repo: {repo}")
        return jsonify(sub_graph), 200

    except Exception as e:
        logging.error(f"Error retrieving sub-graph for repo '{repo}': {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/get_neighbors', methods=['GET'])
def get_neighbors():
    """
    Endpoint to get neighbors of a specific node in the graph.
    Expects 'repo' and 'node_id' as query parameters.
    """
    repo = request.args.get('repo')
    node_id = request.args.get('node_id')

    if not repo:
        logging.error("Repository name is missing in the request.")
        return jsonify({"error": "Repository name is required."}), 400

    if not node_id:
        logging.error("Node ID is missing in the request.")
        return jsonify({"error": "Node ID is required."}), 400

    try:
        # Validate and convert node_id to integer
        node_id = int(node_id)
    except ValueError:
        logging.error(f"Invalid node ID: {node_id}. It must be an integer.")
        return jsonify({"error": "Invalid node ID. It must be an integer."}), 400

    try:
        # Initialize the graph with the provided repo and credentials
        g = Graph(repo)

        # Get neighbors of the given node
        neighbors = g.get_neighbors(node_id)

        logging.info(f"Successfully retrieved neighbors for node ID {node_id} in repo '{repo}'.")
        return jsonify(neighbors), 200

    except Exception as e:
        logging.error(f"Error retrieving node neighbors for repo '{repo}': {e}")
        return jsonify({"error": "Internal server error"}), 500


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
    repo_url = data.get('repo_url')
    if repo_url is None:
        return jsonify({'status': f'Missing mandatory parameter "repo_url"'}), 400
    logger.debug(f'Received repo_url: {repo_url}')

    ignore = data.get('ignore', [])

    # Validate and normalize URL
    try:
        urlparse(repo_url)
    except ValueError:
        return jsonify({'status': 'Invalid repository URL'}), 400

    # Convert repo_url to git URL
    git_url = repo_url + '.git'
    parsed_url = urlparse(git_url)
    logging.debug(f"Processing git URL: {git_url}")

    repo_name = parsed_url.path.rstrip('.git').split('/')[-1]
    if not repo_name:
        raise ValueError(f"Could not extract repository name from URL: {url}")

    base_path = Path("./repositories")
    repo_path = base_path / repo_name
    logging.debug(f"Repository name: {repo_name}")

    # Create source code analyzer
    analyzer = SourceAnalyzer()

    try:
        analyzer.analyze_github_repository(git_url, repo_path, repo_name, ignore)
        build_commit_graph(repo_path, repo_name, ignore)
    except Exception as e:
        logger.error(f'An error occurred: {e}')
        return jsonify({'status': f'Failed to process repository: {git_url}'}), 400

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
    analyzer = SourceAnalyzer(host     = FALKORDB_HOST,
                              port     = FALKORDB_PORT,
                              username = FALKORDB_USERNAME,
                              password = FALKORDB_PASSWORD)

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

    # Get JSON data from the request
    data = request.get_json()

    # Process the data
    repo = data.get('repo')
    lcov = data.get('lcov')

    if repo is None:
        return jsonify({'status': f'Missing mandatory parameter "repo"'}), 400
    if lcov is None:
        return jsonify({'status': f'Missing mandatory parameter "lcov"'}), 400

    process_lcov(repo, lcov)

    # Create a response
    response = {
        'status': 'success',
    }

    return jsonify(response), 200

@app.route('/process_git_history', methods=['POST'])
def process_git_history():

    # Get JSON data from the request
    data = request.get_json()

    # path to local repository
    repo = data.get('repo')
    if repo is None:
        return jsonify({'status': f'Missing mandatory parameter "repo"'}), 400

    ignore_list = data.get('ignore') or []

    build_commit_graph(repo, ignore_list)

    # Create a response
    response = {
        'status': 'success',
    }

    return jsonify(response), 200


@app.route('/switch_commit', methods=['POST'])
def process_switch_commit():
    # Get JSON data from the request
    data = request.get_json()

    # path to local repository
    repo = data.get('repo')
    if repo is None:
        return jsonify({'status': f'Missing mandatory parameter "repo"'}), 400

    commit = data.get('commit')
    if commit is None:
        return jsonify({'status': f'Missing mandatory parameter "commit"'}), 400

    change_set = switch_commit(repo, commit)

    # Create a response
    response = {
        'status': 'success',
        'change_set': change_set
    }

    return jsonify(response), 200

@app.route('/auto_complete', methods=['POST'])
def process_auto_complete():
    # Get JSON data from the request
    data = request.get_json()

    # path to local repository
    repo = data.get('repo')
    if repo is None:
        return jsonify({'status': f'Missing mandatory parameter "repo"'}), 400

    prefix = data.get('prefix')
    if prefix is None:
        return jsonify({'status': f'Missing mandatory parameter "prefix"'}), 400

    completions = auto_complete(repo, prefix)
    # Create a response
    response = {
        'status': 'success',
        'completions': completions
    }

    return jsonify(response), 200


@app.route('/list_repos', methods=['GET'])
def process_list_repos():
    # Get JSON data from the request

    repos = list_repos()

    # Create a response
    response = {
        'status': 'success',
        'repositories': repos
    }

    return jsonify(response), 200


@app.route('/list_commits', methods=['POST'])
def process_list_commits():
    # Get JSON data from the request
    data = request.get_json()

    # name of repository
    repo = data.get('repo')
    if repo is None:
        return jsonify({'status': f'Missing mandatory parameter "repo"'}), 400

    # Get JSON data from the request
    git_graph = GitGraph(GitRepoName(repo))

    commits = git_graph.list_commits()

    # Create a response
    response = {
        'status': 'success',
        'commits': commits
    }

    return jsonify(response), 200


@app.route('/repo_stats', methods=['POST'])
def repo_stats():
    """
    Endpoint to retrieve statistics about a specific repository.

    Expected JSON payload:
        {
            "repo": <repository name>
        }

    Returns:
        JSON: A response containing the status and graph statistics (node and edge counts).
            - 'status': 'success' if successful, or an error message.
            - 'stats': A dictionary with the node and edge counts if the request is successful.
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

    # Create a response
    response = {
        'status': 'success',
        'stats': stats
    }

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

    # Validate 'dest' parameter
    dest = data.get('dest')
    if dest is None:
        return jsonify({'status': f'Missing mandatory parameter "dest"'}), 400

    # Initialize graph with provided repo and credentials
    g = Graph(repo)

    # Find paths between the source and destination nodes
    paths = g.find_paths(src, dest)

    # Create and return a successful response
    response = { 'status': 'success', 'paths': paths }

    return jsonify(response), 200


if __name__ == '__main__':
    app.run(debug=True)

