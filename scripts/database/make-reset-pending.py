
import logging
import sys
import os
import argparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.operations import get_database_operations
from database.models import CrawlStatus
from config_manager import load_config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
logger = logging.getLogger(__name__)

def reset_url_status(force=False):
    """
    Resets the crawl_status of URLs in the discovered_urls table.
    - URLs with 'error' status will be set to 'pending'.
    - URLs with a NULL crawl_status will be set to 'pending'.
    """
    if not force:
        print("This script will update the 'discovered_urls' table.")
        print("It will set the 'crawl_status' to 'pending' for all URLs that currently have the 'error' status or have a NULL status.")
        confirm = input("Are you sure you want to continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Operation cancelled.")
            return

    load_config()
    db_ops = get_database_operations()
    if not db_ops:
        logger.error("Failed to connect to the database.")
        return

    try:
        logger.info("Attempting to reset URLs with 'error' status to 'pending'...")
        error_response = db_ops.client.table('discovered_urls').update({
            'crawl_status': CrawlStatus.PENDING.value,
            'error_message': None # Clear previous error message
        }).eq('crawl_status', CrawlStatus.ERROR.value).execute()

        if error_response.data:
            logger.info(f"Successfully reset {len(error_response.data)} URLs from 'error' to 'pending'.")
        else:
            logger.info("No URLs with 'error' status found to reset.")

        logger.info("Attempting to set URLs with NULL status to 'pending'...")
        null_response = db_ops.client.table('discovered_urls').update({
            'crawl_status': CrawlStatus.PENDING.value
        }).is_('crawl_status', None).execute()

        if null_response.data:
            logger.info(f"Successfully set {len(null_response.data)} URLs from NULL to 'pending'.")
        else:
            logger.info("No URLs with NULL status found to update.")

        logger.info("Database update process finished.")

    except Exception as e:
        logger.error(f"An error occurred while updating URL statuses: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset 'error' or NULL URL statuses to 'pending'.")
    parser.add_argument('--force', action='store_true', help='Skip interactive confirmation.')
    args = parser.parse_args()
    
    reset_url_status(args.force)
