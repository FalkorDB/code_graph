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

def test_list_repos(client):
    # Start with an empty DB
    response     = client.get("/list_repos").json
    status       = response["status"] 
    repositories = response["repositories"]

    # Expecting an empty response
    assert status == "success"
    assert repositories == []

    # Process a local repository
    path = Path(__file__).absolute()
    path = path.parent.parent / "git_repo"

    proj = Project.from_local_repository(path)

    proj.analyze_sources()
    proj.process_git_history()

    # Reissue list_repos request
    response     = client.get("/list_repos").json
    status       = response["status"] 
    repositories = response["repositories"]

    # Expecting an empty response
    assert status == "success"
    assert repositories == ['git_repo']
