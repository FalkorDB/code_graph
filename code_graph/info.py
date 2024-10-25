import os
import redis
import logging
from typing import Optional, Dict

# Configure logging
logging.basicConfig(level=logging.INFO)

def get_redis_connection() -> redis.Redis:
    """
    Establishes a connection to Redis using environment variables.

    Returns:
        redis.Redis: A Redis connection object.
    """
    try:
        return redis.Redis(
            host             = os.getenv('FALKORDB_HOST'),
            port             = os.getenv('FALKORDB_PORT'),
            username         = os.getenv('FALKORDB_USERNAME'),
            password         = os.getenv('FALKORDB_PASSWORD'),
            decode_responses = True  # To ensure string responses
        )
    except Exception as e:
        logging.error(f"Error connecting to Redis: {e}")
        raise


def save_repo_info(repo_name: str, repo_url: str) -> None:
    """
    Saves repository information (URL) to Redis under a hash named {repo_name}_info.

    Args:
        repo_name (str): The name of the repository.
        repo_url (str): The URL of the repository.
    """

    try:
        r = get_redis_connection()
        key = f"{{{repo_name}}}_info"  # Safely format the key

        # Save the repository URL
        r.hset(key, 'repo_url', repo_url)
        logging.info(f"Repository info saved for {repo_name}")

    except Exception as e:
        logging.error(f"Error saving repo info for '{repo_name}': {e}")
        raise

def get_repo_info(repo_name: str) -> Optional[Dict[str, str]]:
    """
    Retrieves repository information from Redis.

    Args:
        repo_name (str): The name of the repository.

    Returns:
        Optional[Dict[str, str]]: A dictionary of repository information, or None if not found.
    """
    try:
        r = get_redis_connection()
        key = f"{{{repo_name}}}_info"
        
        # Retrieve all information about the repository
        repo_info = r.hgetall(key)
        if not repo_info:
            logging.warning(f"No repository info found for {repo_name}")
            return None
        
        logging.info(f"Repository info retrieved for {repo_name}")
        return repo_info

    except Exception as e:
        logging.error(f"Error retrieving repo info for '{repo_name}': {e}")
        raise

