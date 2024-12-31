import redis
import pytest
from pathlib import Path
from api import app as create_app

@pytest.fixture()
def app():
    create_app.config.update({"TESTING": True})

    # other setup can go here
    redis.Redis().flushall()

    yield create_app

    # clean up / reset resources here

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture()
def runner(app):
    return app.test_cli_runner()

def test_graph_entities(client):
    # Start with an empty DB
    response = client.get("/graph_entities?repo=GraphRAG-SDK").json
    status   = response["status"] 

    # Expecting an error
    assert status == "Missing project GraphRAG-SDK"

    # Process Git repository
    proj = Project.from_git_repository("https://github.com/FalkorDB/GraphRAG-SDK")
    proj.analyze_sources()

    # Re-issue graph_entities request
    response = client.get("/graph_entities?repo=GraphRAG-SDK").json
    status   = response["status"] 
    entities = response["entities"]
    nodes    = entities["nodes"]
    edges    = entities["edges"]

    assert status == "success"
    assert len(nodes) > 10 and len(nodes) < 1000
    assert len(edges) > 10 and len(edges) < 1000
