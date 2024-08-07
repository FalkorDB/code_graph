import os
import tempfile
import concurrent.futures

from git import Repo
from pathlib import Path
from typing import Optional

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

    def first_pass(self, base: str, root: str,
                   executor: concurrent.futures.Executor) -> None:
        """
        Perform the first pass analysis on source files in the given directory tree.

        Args:
            base (str): The base directory path to be used for relative paths.
            root (str): The root directory path to start the analysis from.
            executor (concurrent.futures.Executor): The executor to run tasks concurrently.
        """

        print(f'root: {root}')
        tasks = []
        for dirpath, dirnames, filenames in os.walk(root):
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
                        relative_path = str(path).replace(base, '')
                        ext = path.suffix
                        analyzers[ext].first_pass(Path(relative_path), f, self.graph)

                process_file(file_path)
                #task = executor.submit(process_file, file_path)
                #tasks.append(task)

        # Wait for all tasks to complete
        #concurrent.futures.wait(tasks)

    def second_pass(self, base: str, root: str,
                    executor: concurrent.futures.Executor) -> None:
        """
        Recursively analyze the contents of a directory.

        Args:
            base (str): The base directory for analysis.
            root (str): The current directory being analyzed.
            executor (concurrent.futures.Executor): The executor to run tasks concurrently.
        """

        tasks = []
        for dirpath, dirnames, filenames in os.walk(root):
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
                        relative_path = str(path).replace(base, '')
                        ext = path.suffix
                        analyzers[ext].second_pass(Path(relative_path), f, self.graph)

                task = executor.submit(process_file, file_path)
                tasks.append(task)

        # Wait for all tasks to complete
        concurrent.futures.wait(tasks)

    def analyze_sources(self, path: Path) -> None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            # First pass analysis of the source code
            self.first_pass(path, path, executor)

            # Second pass analysis of the source code
            self.second_pass(path, path, executor)

    def analyze_repository(self, url: str) -> None:
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
