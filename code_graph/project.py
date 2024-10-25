import shutil
import validators
import subprocess
from git import Repo
from pathlib import Path
from .graph import Graph
from .info import save_repo_info
from typing import Optional, List
from urllib.parse import urlparse
from .analyzers import SourceAnalyzer
from .git_utils import build_commit_graph

def _clone_source(url: str, name: str) -> Path:
    # path to local repositories
    path = Path.cwd() / "repositories" / name
    print(f"Cloning repository to: {path}")

    # Delete local repository if exists
    if path.exists():
        shutil.rmtree(path)

    # Create directory
    path.mkdir(parents=True, exist_ok=True)

    # Clone repository
    # Prepare the Git clone command
    cmd = ["git", "clone", url, path]

    # Run the git clone command and wait for it to finish
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    
    return path

class Project():
    def __init__(self, name: str, path: Path, url: Optional[str]):
        self.url  = url
        self.name = name
        self.path = path

        if url is not None:
            save_repo_info(name, url)

    @classmethod
    def from_git_repository(cls, url: str):
        # Validate url
        if not validators.url(url):
            raise Exception(f"invalid url: {url}")

        # Extract project name from URL
        parsed_url = urlparse(url)
        name = parsed_url.path.split('/')[-1]
        path = _clone_source(url, name)

        return cls(name, path, url)

    @classmethod
    def from_local_repository(cls, path: Path):
        # Validate path exists
        if not path.exists():
            raise Exception(f"missing path: {path}")

        # adjust url
        # 'git@github.com:FalkorDB/code_graph.git'
        url  = Repo(path).remotes[0].url
        url = url.replace("git@", "https://").replace(":", "/").replace(".git", "")

        name = path.name

        return cls(name, path, url)

    def analyze_sources(self, ignore: Optional[List[str]] = []):
        g = Graph(self.name)
        analyzer = SourceAnalyzer()
        analyzer.analyze(self.path, g, ignore)

    def process_git_history(self, ignore: Optional[List[str]] = []):
        build_commit_graph(self.path, self.name, ignore)

