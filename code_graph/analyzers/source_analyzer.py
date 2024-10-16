import os
import tempfile
import concurrent.futures

from git import Repo
from pathlib import Path
from typing import Optional, List

from ..graph import Graph
from .c.analyzer import CAnalyzer
from .python.analyzer import PythonAnalyzer

import logging
logger = logging.getLogger('code_graph')

# List of available analyzers
analyzers = {'.c': CAnalyzer(),
             '.h': CAnalyzer(),
             '.py': PythonAnalyzer()}

class SourceAnalyzer():
    def __init__(self, host: str = 'localhost', port: int = 6379,
                 username: Optional[str] = None, password: Optional[str] = None) -> None:

        self.host      = host
        self.port      = port
        self.username  = username
        self.password  = password

    def first_pass(self, ignore: List[str], executor: concurrent.futures.Executor) -> None:
        """
        Perform the first pass analysis on source files in the given directory tree.

        Args:
            ignore (list(str)): List of paths to ignore
            executor (concurrent.futures.Executor): The executor to run tasks concurrently.
        """

        tasks = []
        for dirpath, dirnames, filenames in os.walk("."):

            # skip current directory if it is within the ignore list
            if dirpath in ignore:
                # in-place clear dirnames to prevent os.walk from recursing into
                # any of the nested directories
                logger.info(f'ignoring directory: {dirpath}')
                dirnames[:] = []
                continue

            logger.info(f'Processing directory: {dirpath}')

            # Process each file in the current directory
            for filename in filenames:
                file_path = Path(os.path.join(dirpath, filename))

                # Skip none supported files
                ext = file_path.suffix
                if ext not in analyzers:
                    logger.info(f"Skipping none supported file {file_path}")
                    continue

                logger.info(f'Processing file: {file_path}')

                def process_file(path: Path) -> None:
                    with open(path, 'rb') as f:
                        ext = path.suffix
                        analyzers[ext].first_pass(path, f, self.graph)

                process_file(file_path)
                #task = executor.submit(process_file, file_path)
                #tasks.append(task)

        # Wait for all tasks to complete
        #concurrent.futures.wait(tasks)

    def second_pass(self, ignore: List[str], executor: concurrent.futures.Executor) -> None:
        """
        Recursively analyze the contents of a directory.

        Args:
            base (str): The base directory for analysis.
            root (str): The current directory being analyzed.
            executor (concurrent.futures.Executor): The executor to run tasks concurrently.
        """

        tasks = []
        for dirpath, dirnames, filenames in os.walk("."):

            # skip current directory if it is within the ignore list
            if dirpath in ignore:
                # in-place clear dirnames to prevent os.walk from recursing into
                # any of the nested directories
                logger.info(f'ignoring directory: {dirpath}')
                dirnames[:] = []
                continue

            logger.info(f'Processing directory: {dirpath}')

            # Process each file in the current directory
            for filename in filenames:
                file_path = Path(os.path.join(dirpath, filename))

                # Skip none supported files
                ext = file_path.suffix
                if ext not in analyzers:
                    continue

                logger.info(f'Processing file: {file_path}')

                def process_file(path: Path) -> None:
                    with open(path, 'rb') as f:
                        ext = path.suffix
                        analyzers[ext].second_pass(path, f, self.graph)

                task = executor.submit(process_file, file_path)
                tasks.append(task)

        # Wait for all tasks to complete
        concurrent.futures.wait(tasks)

    def analyze_sources(self, ignore: List[str]) -> None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            # First pass analysis of the source code
            self.first_pass(ignore, executor)

            # Second pass analysis of the source code
            self.second_pass(ignore, executor)

    def analyze_github_repository(self, url: str) -> None:
        """
        Analyze a Git repository given its URL.

        Args:
            url (str): The URL of the Git repository to analyze.
        """

        # Extract repository name from the URL
        components = url[:url.rfind('.')].split('/')
        n = len(components)
        repo_name = f'{components[n-2]}/{components[-1]}'
        logger.debug(f'repo_name: {repo_name}')
        #repo_name = url[url.rfind('/')+1:url.rfind('.')]

        # Initialize the graph and analyzer
        self.graph = Graph(repo_name, self.host, self.port, self.username,
                           self.password)

        # Create a temporary directory for cloning the repository
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Cloning repository {url} to {temp_dir}")
            repo = Repo.clone_from(url, temp_dir)

            # Analyze source files
            self.analyze_sources(temp_dir)

        logger.info("Done processing repository")

    def analyze_local_folder(self, path: str, ignore: Optional[List[str]] = []) -> Graph:
        """
        Analyze a local folder.

        Args:
            path (str): Path to a local folder containing source files to process
            ignore (List(str)): List of paths to skip
        """

        # change working directory to path
        os.chdir(path)

        proj_name = os.path.split(os.path.normpath(path))[-1]
        logger.debug(f'proj_name: {proj_name}')

        # Initialize the graph and analyzer
        self.graph = Graph(proj_name, self.host, self.port, self.username,
                           self.password)

        # Analyze source files
        self.analyze_sources(ignore)

        logger.info("Done processing folder")

        return self.graph

    def analyze_local_repository(self, path: str, ignore: Optional[List[str]] = []) -> Graph:
        """
        Analyze a local Git repository.

        Args:
            path (str): Path to a local git repository
            ignore (List(str)): List of paths to skip
        """

        self.analyze_local_folder(path, ignore)

        # Save processed commit hash to the DB
        repo = Repo(path)
        head = repo.commit("HEAD")
        self.graph.set_graph_commit(head.hexsha)

        return self.graph

