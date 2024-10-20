import os
import shutil
import subprocess
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
    def __init__(self) -> None:
        self.host      = os.getenv('FALKORDB_HOST')
        self.port      = os.getenv('FALKORDB_PORT')
        self.username  = os.getenv('FALKORDB_USERNAME')
        self.password  = os.getenv('FALKORDB_PASSWORD')

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

    def analyze_github_repository(
        self,
        url: str,
        repo_path: Path,
        repo_name: str,
        ignore: Optional[List[str]] = []
    ) -> None:
        """
        Analyze a Git repository given its URL.

        Args:
            url: The URL of the Git repository to analyze
            ignore_patterns: List of patterns to ignore during analysis

        Raises:
            subprocess.SubprocessError: If git clone fails
            OSError: If there are filesystem operation errors
        """

        # Extract repository name more reliably
        # Delete local repository if exists
        if repo_path.exists():
            shutil.rmtree(repo_path)

        # Create directory
        repo_path.mkdir(parents=True, exist_ok=True)

        # Clone repository
        # Prepare the git clone command
        command = ["git", "clone", url, repo_path]

        # Run the git clone command and wait for it to finish
        result = subprocess.run(command, check=True, capture_output=True, text=True)

        # Store original working directory
        original_dir = Path.cwd()

        # change working directory to local repository
        os.chdir(repo_path)

        try:
            # Initialize the graph and analyzer
            self.graph = Graph(repo_name, self.host, self.port, self.username,
                               self.password)

            # Analyze repository
            self.analyze_sources(ignore)

            logging.info(f"Successfully processed repository: {repo_name}")

        finally:
            # Ensure we always return to the original directory
            os.chdir(original_dir)

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

