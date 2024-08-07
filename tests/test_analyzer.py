import unittest
from code_graph import *

# logging_config.py
import logging

class TestAnalyzer(unittest.TestCase):
    def setUp(self):
        # Create a custom logger
        logger = logging.getLogger('code_graph')

        # Set the minimum level of messages to handle
        logger.setLevel(logging.DEBUG)

        # Create handlers
        console_handler = logging.StreamHandler()

        # Set the level for handlers
        console_handler.setLevel(logging.DEBUG)

        # Create formatters and add them to the handlers
        console_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')

        console_handler.setFormatter(console_format)

        # Add handlers to the logger
        logger.addHandler(console_handler)

    def test_analyzer(self):
        analyzer = SourceAnalyzer()
        analyzer.analyze_repository('https://github.com/FalkorDB/falkordb-py.git')
        analyzer.analyze_repository('https://github.com/psf/requests.git')
        analyzer.analyze_repository('https://github.com/antirez/sds.git')
        analyzer.analyze_repository('https://github.com/FalkorDB/FalkorDB.git')
