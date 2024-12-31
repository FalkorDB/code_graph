import redis
import pytest
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

def test_auto_complete(client):
    # Start with an empty DB
    response = client.post("/auto_complete", json={ "repo": "GraphRAG-SDK", "prefix": "set" })
    status   = response.json["status"] 

    # Expecting an empty response
    assert status == "Missing project GraphRAG-SDK"

    # Process Git repository
    proj = Project.from_git_repository("https://github.com/FalkorDB/GraphRAG-SDK")
    proj.analyze_sources()
    proj.process_git_history()

    # Re-issue auto complete request
    response    = client.post("/auto_complete", json={ "repo": "GraphRAG-SDK", "prefix": "set" })
    status      = response.json["status"] 
    completions = response.json["completions"]

    # Expecting an empty response
    assert status == "success"
    assert len(completions) > 0
    for completion in completions:
        assert completion["properties"]["name"].startswith("set")

