import os
import redis
import datetime
from code_graph import *
from typing import Optional
from falkordb import FalkorDB
from urllib.parse import urlparse
from flask import Flask, request, jsonify, abort

# Configuration
FALKORDB_HOST     = 'localhost'
FALKORDB_PORT     = 6379
FALKORDB_USERNAME = None
FALKORDB_PASSWORD = None

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

def get_current_head_commit_hash(repo_url: str) -> str:
    import git

    with tempfile.TemporaryDirectory() as temp_dir:
        repo = git.Repo.clone_from(repo_url, temp_dir)
        commit_hash = repo.head.commit.hexsha
    return commit_hash

def save_repository_metadata(repo_url: str, repo_name: str):
    r = redis.Redis(host=FALKORDB_HOST, port=FALKORDB_PORT,
                    username=FALKORDB_USERNAME, password=FALKORDB_PASSWORD,
                    decode_responses=True)

    key = f'{repo_name}_metadata'
    metadata = {
            'repo_url': repo_url,
            'repo_name': repo_name,
            'date_create': str(datetime.datetime.today().replace(microsecond=0)),
            'commit': get_current_head_commit_hash(repo_url)}

    r.hset(key, mapping=metadata)

@app.route('/list_repos', methods=['GET'])
def list_repos():
    r = redis.Redis(host=FALKORDB_HOST, port=FALKORDB_PORT,
                    username=FALKORDB_USERNAME, password=FALKORDB_PASSWORD,
                    decode_responses=True)
    keys = r.keys('*_metadata')[:20]

    repos = []
    for key in keys:
        repos.append(r.hgetall(key))

    return jsonify({'repos': repos}), 200

@app.route('/graph_entities', methods=['GET'])
def graph_entities():
    # Access the 'graph_id' parameter from the GET request
    graph_id = request.args.get('graph_id')

    # Connect to FalkorDB
    db = FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT,
                  username=FALKORDB_USERNAME, password=FALKORDB_PASSWORD)

    # Select graph
    g = db.select_graph(graph_id)

    query = """MATCH (src)
               OPTIONAL MATCH (src)-[e]->(dest)
               RETURN src, e, dest
               LIMIT 100"""

    data = []
    res = g.query(query).result_set
    for row in res:
        src  = row[0]
        e    = row[1]
        dest = row[2]

        data.append({'data': {'id': src.id,
                              'label': src.labels[0]} })

        if e is not None:
            data.append({'data': {'id': dest.id,
                                  'label': dest.labels[0]} })
            data.append({'data': {'source': src.id, 'target': dest.id, 'relation': e.relation} })

    # [
    #   { data: { id: 'e' } },
    #   { data: { source: 'a', target: 'b' } }
    # ]

    return jsonify(data), 200

@app.route('/get_neighbors', methods=['GET'])
def get_neighbors():
    # Access the 'node_id' parameter from the GET request
    node_id  = int(request.args.get('node_id'))
    graph_id = request.args.get('graph_id')

    # Connect to FalkorDB
    db = FalkorDB(host=FALKORDB_HOST, port=FALKORDB_PORT,
                  username=FALKORDB_USERNAME, password=FALKORDB_PASSWORD)

    # Select graph
    g = db.select_graph(graph_id)

    query = """MATCH (n)
               WHERE ID(n) = $node_id
               MATCH (n)-[e]-(neighbor)
               RETURN neighbor, e"""

    data = []
    res = g.query(query, {'node_id': node_id}).result_set
    for row in res:
        neighbor = row[0]
        e        = row[1]

        data.append({'data': {'id': neighbor.id,
                              'label': neighbor.labels[0]} })
        data.append({'data': {'source': node_id, 'target': neighbor.id, 'relation': e.relation} })

    # [
    #   { data: { id: 'e' } },
    #   { data: { source: 'a', target: 'b' } }
    # ]

    return jsonify(data), 200

@app.route('/process_repo', methods=['POST'])
def process_repo():
    # Get JSON data from the request
    data = request.get_json()

    # Process the data
    repo_url = data.get('repo_url')
    if repo_url is None:
        return jsonify({'status': f'Missing mandatory parameter "repo_url"'}), 400
    logger.debug(f'Received repo_url: {repo_url}')

    # Validate URL
    try:
        urlparse(repo_url)
    except ValueError:
        return jsonify({'status': 'Invalid repository URL'}), 400

    # Extract Organization and Repo name from URL
    res = extract_org_name_from_url(repo_url)
    if res is None:
        return jsonify({'status': f'Failed to process repo_url: {repo_url}'}), 400

    org, name = extract_org_name_from_url(repo_url)
    logger.debug(f'Org: {org}, name: {name}')

    # Convert repo_url to git URL
    git_url = repo_url + '.git'
    logger.debug(f'git_url: {git_url}')

    # Create source code analyzer
    analyzer = SourceAnalyzer(host     = FALKORDB_HOST,
                              port     = FALKORDB_PORT,
                              username = FALKORDB_USERNAME,
                              password = FALKORDB_PASSWORD)

    try:
        analyzer.analyze_repository(git_url)
    except Exception as e:
        logger.error(f'An error occurred: {e}')
        return jsonify({'status': f'Failed to process repository: {git_url}'}), 400

    repo_name = f'{org}/{name}'
    save_repository_metadata(git_url, repo_name)

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

    # Create source code analyzer
    analyzer = SourceAnalyzer(host     = FALKORDB_HOST,
                              port     = FALKORDB_PORT,
                              username = FALKORDB_USERNAME,
                              password = FALKORDB_PASSWORD)

    try:
        analyzer.analyze_local_repository(repo)
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
if __name__ == '__main__':
    app.run(debug=True)

