#!/usr/bin/env python3
"""
Elasticsearch Bulk Loader for Garmin FIT Files

A robust bulk loader using elasticsearch.helpers.bulk with configurable chunk_size,
retry/backoff, per-item failure logging, and optional tqdm progress bars.

Usage:
    ES_HOST=http://localhost:9200 python3 scripts/es_bulk_loader.py --data-dir garmin --index fit-bench --chunk-size 500

Requirements:
    - fitparse
    - elasticsearch<9
    - pandas
    - tqdm
"""

import os
import sys
import argparse
import logging
import datetime
from typing import Dict, List, Any, Iterator

from elasticsearch import Elasticsearch, helpers
from elasticsearch.exceptions import ElasticsearchException

# Try to import from load_fit_to_es.py if available
try:
    from load_fit_to_es import parse_fit_file, compute_session_metrics
    PARSER_AVAILABLE = True
except ImportError:
    PARSER_AVAILABLE = False
    # Fallback placeholder functions
    def parse_fit_file(path: str) -> List[Dict[str, Any]]:
        """Placeholder function when load_fit_to_es.py is not available."""
        logging.warning(f"parse_fit_file fallback used for {path} - load_fit_to_es.py not available")
        return []
    
    def compute_session_metrics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Placeholder function when load_fit_to_es.py is not available."""
        return {}

# Try to import tqdm for progress bars
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    # Fallback when tqdm is not available
    def tqdm(iterable, **kwargs):
        return iterable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('es_bulk_loader.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Failure log
FAILURE_LOG_FILE = 'es_bulk_failures.log'
failure_logger = logging.getLogger('failures')
failure_logger.setLevel(logging.ERROR)
failure_handler = logging.FileHandler(FAILURE_LOG_FILE)
failure_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
failure_logger.addHandler(failure_handler)


def generate_actions(data_dir: str, index_name: str) -> Iterator[Dict[str, Any]]:
    """
    Generate bulk indexing actions from FIT files in the data directory.
    
    Args:
        data_dir: Directory containing .fit files
        index_name: Elasticsearch index name
        
    Yields:
        Dictionary containing bulk action for Elasticsearch
    """
    if not os.path.isdir(data_dir):
        logger.error(f"Data directory not found: {data_dir}")
        return
    
    fit_files = [f for f in os.listdir(data_dir) if f.endswith('.fit')]
    logger.info(f"Found {len(fit_files)} .fit files in {data_dir}")
    
    if not PARSER_AVAILABLE:
        logger.warning("load_fit_to_es.py not available - using placeholder parser")
    
    for filename in tqdm(fit_files, desc="Processing FIT files", disable=not TQDM_AVAILABLE):
        filepath = os.path.join(data_dir, filename)
        try:
            # Parse the FIT file
            records = parse_fit_file(filepath)
            
            if not records:
                logger.warning(f"No records found in {filename}")
                continue
            
            # Compute session metrics
            session_metrics = compute_session_metrics(records)
            session_id = os.path.splitext(filename)[0]
            
            # Generate bulk actions for each record
            for i, record in enumerate(records):
                # Prepare document
                doc = record.copy()
                doc["session_id"] = session_id
                doc.update(session_metrics)
                
                # Convert datetime objects to ISO format strings for ES
                for key, value in doc.items():
                    if isinstance(value, datetime.datetime):
                        doc[key] = value.isoformat()
                
                # Generate action
                action = {
                    "_index": index_name,
                    "_id": f"{session_id}-{i}",
                    "_source": doc
                }
                yield action
                
        except Exception as e:
            logger.error(f"Error processing {filename}: {str(e)}", exc_info=True)
            failure_logger.error(f"Failed to process file {filename}: {str(e)}")


def bulk_load(
    es_client: Elasticsearch,
    data_dir: str,
    index_name: str,
    chunk_size: int = 500,
    max_retries: int = 3,
    initial_backoff: float = 2.0,
    max_backoff: float = 60.0
) -> Dict[str, int]:
    """
    Bulk load FIT file data into Elasticsearch with retry and backoff.
    
    Args:
        es_client: Elasticsearch client instance
        data_dir: Directory containing .fit files
        index_name: Elasticsearch index name
        chunk_size: Number of documents per bulk request
        max_retries: Maximum number of retry attempts
        initial_backoff: Initial backoff time in seconds
        max_backoff: Maximum backoff time in seconds
        
    Returns:
        Dictionary with success and failure counts
    """
    logger.info(f"Starting bulk load: index={index_name}, chunk_size={chunk_size}")
    
    success_count = 0
    failure_count = 0
    
    try:
        # Use elasticsearch.helpers.bulk for robust bulk indexing
        for success, info in helpers.streaming_bulk(
            es_client,
            generate_actions(data_dir, index_name),
            chunk_size=chunk_size,
            max_retries=max_retries,
            initial_backoff=initial_backoff,
            max_backoff=max_backoff,
            raise_on_error=False,
            raise_on_exception=False
        ):
            if success:
                success_count += 1
            else:
                failure_count += 1
                # Log individual failure
                action, error_info = info.popitem()
                doc_id = error_info.get('_id', 'unknown')
                error_msg = error_info.get('error', 'unknown error')
                failure_logger.error(f"Failed to index document {doc_id}: {error_msg}")
                logger.warning(f"Failed to index document {doc_id}")
        
        logger.info(f"Bulk load completed: {success_count} successful, {failure_count} failed")
        
    except ElasticsearchException as e:
        logger.error(f"Elasticsearch error during bulk load: {str(e)}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error during bulk load: {str(e)}", exc_info=True)
    
    return {
        "success": success_count,
        "failure": failure_count
    }


def create_index_with_settings(es_client: Elasticsearch, index_name: str, replicas: int = 0):
    """
    Create index with optimized settings for bulk loading.
    
    Args:
        es_client: Elasticsearch client instance
        index_name: Name of the index to create
        replicas: Number of replicas (default 0 for performance)
    """
    settings = {
        "settings": {
            "number_of_replicas": replicas,
            "refresh_interval": "-1"  # Disable refresh during bulk load
        }
    }
    
    try:
        if es_client.indices.exists(index=index_name):
            logger.info(f"Index {index_name} already exists")
        else:
            es_client.indices.create(index=index_name, body=settings)
            logger.info(f"Created index {index_name} with optimized settings")
    except Exception as e:
        logger.error(f"Error creating index: {str(e)}", exc_info=True)
        raise


def restore_index_settings(es_client: Elasticsearch, index_name: str):
    """
    Restore index settings after bulk load (enable refresh, set replicas).
    
    Args:
        es_client: Elasticsearch client instance
        index_name: Name of the index
    """
    try:
        es_client.indices.put_settings(
            index=index_name,
            body={
                "refresh_interval": "1s",  # Default refresh interval
                "number_of_replicas": 1     # Production replica count
            }
        )
        # Force refresh to make all documents searchable
        es_client.indices.refresh(index=index_name)
        logger.info(f"Restored settings and refreshed index {index_name}")
    except Exception as e:
        logger.error(f"Error restoring index settings: {str(e)}", exc_info=True)


def main():
    """Main entry point for the bulk loader."""
    parser = argparse.ArgumentParser(
        description='Bulk load Garmin FIT files into Elasticsearch',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with local ES
  python3 scripts/es_bulk_loader.py --data-dir garmin --index fit-bench

  # With custom chunk size
  ES_HOST=http://localhost:9200 python3 scripts/es_bulk_loader.py \\
      --data-dir garmin --index fit-bench --chunk-size 1000

  # Skip index creation (use existing index)
  python3 scripts/es_bulk_loader.py --data-dir garmin --index fit-bench --skip-create
        """
    )
    
    parser.add_argument(
        '--data-dir',
        required=True,
        help='Directory containing .fit files'
    )
    parser.add_argument(
        '--index',
        required=True,
        help='Elasticsearch index name'
    )
    parser.add_argument(
        '--chunk-size',
        type=int,
        default=500,
        help='Number of documents per bulk request (default: 500)'
    )
    parser.add_argument(
        '--es-host',
        default=os.environ.get('ES_HOST', 'http://localhost:9200'),
        help='Elasticsearch host URL (default: http://localhost:9200 or ES_HOST env var)'
    )
    parser.add_argument(
        '--skip-create',
        action='store_true',
        help='Skip index creation (use existing index)'
    )
    parser.add_argument(
        '--skip-restore',
        action='store_true',
        help='Skip restoring index settings after bulk load'
    )
    
    args = parser.parse_args()
    
    # Initialize Elasticsearch client
    logger.info(f"Connecting to Elasticsearch at {args.es_host}")
    try:
        es = Elasticsearch([args.es_host])
        # Test connection
        if not es.ping():
            logger.error("Failed to connect to Elasticsearch")
            sys.exit(1)
        logger.info("Successfully connected to Elasticsearch")
    except Exception as e:
        logger.error(f"Error connecting to Elasticsearch: {str(e)}")
        sys.exit(1)
    
    # Create index if requested
    if not args.skip_create:
        create_index_with_settings(es, args.index)
    
    # Perform bulk load
    results = bulk_load(
        es_client=es,
        data_dir=args.data_dir,
        index_name=args.index,
        chunk_size=args.chunk_size
    )
    
    # Restore index settings
    if not args.skip_restore:
        restore_index_settings(es, args.index)
    
    # Print summary
    logger.info("=" * 60)
    logger.info(f"BULK LOAD SUMMARY")
    logger.info(f"Successfully indexed: {results['success']}")
    logger.info(f"Failed: {results['failure']}")
    logger.info(f"Check {FAILURE_LOG_FILE} for detailed failure information")
    logger.info("=" * 60)
    
    # Exit with error code if there were failures
    if results['failure'] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
