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
from pathlib import Path

from fitparse import FitFile
from elasticsearch import Elasticsearch, helpers
try:
    from elasticsearch.exceptions import ElasticsearchException
except ImportError:
    from elasticsearch import TransportError as ElasticsearchException

# Ensure scripts directory is in path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(script_dir)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# Try to import parse_apple_hr for enrichment support
try:
    from scripts.parse_apple_hr import parse_health_export
    ENRICHMENT_AVAILABLE = True
except ImportError:
    ENRICHMENT_AVAILABLE = False
    parse_health_export = None

# Configuration
FTP = 210  # Update with your current FTP value

HR_ZONES = {
    "hrz1": (98, 117),
    "hrz2": (118, 137),
    "hrz3": (138, 156),
    "hrz4": (157, 176),
    "hrz5": (177, 195),
}

POWER_ZONES = {
    "pwz1": (0, 109),
    "pwz2": (110, 149),
    "pwz3": (150, 179),
    "pwz4": (180, 210),
    "pwz5": (211, 239),
    "pwz6": (240, 298),
    "pwz7": (299, float("inf")),
}

def classify_zone(value, zones):
    if value is None:
        return None
    for name, (low, high) in zones.items():
        if low <= value <= high:
            return name
    return None

def parse_fit_file(path: str) -> List[Dict[str, Any]]:
    """Parse a Garmin .fit file and return list of records."""
    fitfile = FitFile(path)
    data = []
    for record in fitfile.get_messages("record"):
        fields = {f.name: f.value for f in record}
        fields["heart_rate_zone"] = classify_zone(fields.get("heart_rate"), HR_ZONES)
        fields["power_zone"] = classify_zone(fields.get("power"), POWER_ZONES)
        data.append(fields)
    return data

def compute_session_metrics(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregate metrics for a cycling session."""
    powers = [r.get("power") for r in records if isinstance(r.get("power"), (int, float))]
    hrs = [r.get("heart_rate") for r in records if isinstance(r.get("heart_rate"), (int, float))]
    timestamps = [r.get("timestamp") for r in records if isinstance(r.get("timestamp"), datetime.datetime)]
    elevations = [r.get("altitude") for r in records if isinstance(r.get("altitude"), (int, float))]
    distances = [r.get("distance") for r in records if isinstance(r.get("distance"), (int, float))]

    moving_time = len(powers)
    pause_time = sum([max((timestamps[i+1] - timestamps[i]).total_seconds() - 1, 0) for i in range(len(timestamps)-1)])

    avg_power = sum(powers)/len(powers) if powers else 0
    avg_hr = sum(hrs)/len(hrs) if hrs else 0
    normalized_power = (sum([p**4 for p in powers]) / len(powers))**0.25 if powers else 0
    intensity_factor = normalized_power / FTP if FTP > 0 else 0
    tss = (moving_time * normalized_power * intensity_factor) / (FTP * 3600) * 100 if FTP > 0 else 0

    midpoint = len(records) // 2
    drift = None
    if midpoint > 0:
        p1 = [r.get("power") for r in records[:midpoint] if isinstance(r.get("power"), (int, float))]
        h1 = [r.get("heart_rate") for r in records[:midpoint] if isinstance(r.get("heart_rate"), (int, float))]
        p2 = [r.get("power") for r in records[midpoint:] if isinstance(r.get("power"), (int, float))]
        h2 = [r.get("heart_rate") for r in records[midpoint:] if isinstance(r.get("heart_rate"), (int, float))]
        if p1 and p2 and h1 and h2:
            hr_1 = sum(h1) / len(h1)
            pw_1 = sum(p1) / len(p1)
            hr_2 = sum(h2) / len(h2)
            pw_2 = sum(p2) / len(p2)
            if pw_1 > 0:
                drift = ((hr_2 / pw_2) - (hr_1 / pw_1)) / (hr_1 / pw_1) * 100

    return {
        "avg_power": avg_power,
        "avg_hr": avg_hr,
        "moving_time_sec": moving_time,
        "pause_time_sec": pause_time,
        "distance_m": max(distances) if distances else None,
        "elevation_gain_m": max(elevations) - min(elevations) if elevations else None,
        "normalized_power": normalized_power,
        "intensity_factor": intensity_factor,
        "training_stress_score": tss,
        "hr_drift_pct": drift,
    }

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


def enrich_with_watch(record: Dict[str, Any], health_summary: Dict[str, Dict], session_date: str) -> Dict[str, Any]:
    """
    Enrich a FIT record with Apple Watch health data.
    
    Args:
        record: FIT record to enrich
        health_summary: Date-keyed health summary from Apple Health
        session_date: Date of the session (ISO format YYYY-MM-DD)
        
    Returns:
        Enriched record with watch.* and computed.* fields
    """
    daily_health = health_summary.get(session_date, {})
    
    # Add watch-derived fields
    record["watch"] = {
        "resting_hr": daily_health.get("resting_hr"),
        "daily_avg_hr": daily_health.get("avg_hr"),
        "daily_min_hr": daily_health.get("min_hr"),
        "daily_max_hr": daily_health.get("max_hr"),
        "hrv": daily_health.get("hrv"),
        "step_count": daily_health.get("step_count"),
        "active_energy_kcal": daily_health.get("active_energy_kcal"),
    }
    
    # Compute derived metrics from watch data
    avg_hr = record.get("avg_hr") or record.get("avg_heart_rate")
    resting_hr = daily_health.get("resting_hr")
    normalized_power = record.get("normalized_power")
    hrv = daily_health.get("hrv")
    
    computed = {}
    
    # Fatigue index: (session_avg_hr / resting_hr) - 1
    if avg_hr is not None and resting_hr is not None and resting_hr > 0:
        computed["fatigue_index"] = (avg_hr / resting_hr) - 1
    
    # Session intensity index: (normalized_power / FTP) * (session_avg_hr / daily_max_hr)
    daily_max_hr = daily_health.get("max_hr")
    if normalized_power is not None and avg_hr is not None and daily_max_hr is not None and daily_max_hr > 0:
        computed["session_intensity_index"] = (normalized_power / FTP) * (avg_hr / daily_max_hr)
    
    # Recovery ready: HRV > threshold AND resting_hr < baseline
    baseline_resting_hr = record.get("_baseline_resting_hr", 50)
    hrv_threshold = record.get("_hrv_threshold", 30)
    if hrv is not None and resting_hr is not None:
        computed["recovery_ready"] = (hrv > hrv_threshold) and (resting_hr < baseline_resting_hr)
    
    record["computed"] = computed
    return record


def extract_session_date(records: List[Dict[str, Any]]) -> str:
    """
    Extract ISO date from first timestamp in records.
    
    Args:
        records: List of FIT records
        
    Returns:
        Date in YYYY-MM-DD format, or None if no timestamp found
    """
    for record in records:
        ts = record.get("timestamp")
        if isinstance(ts, datetime.datetime):
            return ts.strftime("%Y-%m-%d")
    return None


def generate_actions(data_dir: str, index_name: str, enrichment_mode: str = None, health_summary: Dict[str, Dict] = None) -> Iterator[Dict[str, Any]]:
    """
    Generate bulk indexing actions from FIT files in the data directory.
    
    Args:
        data_dir: Directory containing .fit files
        index_name: Elasticsearch index name
        enrichment_mode: 'watch' to enrich with Apple Health data, None for no enrichment
        health_summary: Date-keyed health summary from Apple Health
        
    Yields:
        Dictionary containing bulk action for Elasticsearch
    """
    if not os.path.isdir(data_dir):
        logger.error(f"Data directory not found: {data_dir}")
        return
    
    fit_files = [f for f in os.listdir(data_dir) if f.endswith('.fit')]
    logger.info(f"Found {len(fit_files)} .fit files in {data_dir}")
    if enrichment_mode == 'watch':
        logger.info(f"Enrichment mode: watch (with {len(health_summary) if health_summary else 0} days of health data)")
    
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
            session_date = extract_session_date(records)
            
            # Generate bulk actions for each record
            for i, record in enumerate(records):
                # Prepare document
                doc = record.copy()
                doc["session_id"] = session_id
                doc.update(session_metrics)
                
                # Enrich with watch data if enabled
                if enrichment_mode == 'watch' and health_summary and session_date:
                    doc = enrich_with_watch(doc, health_summary, session_date)
                
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
    max_backoff: float = 60.0,
    enrichment_mode: str = None,
    health_summary: Dict[str, Dict] = None
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
        enrichment_mode: 'watch' to enrich with Apple Health, None for no enrichment
        health_summary: Date-keyed health summary from Apple Health
        
    Returns:
        Dictionary with success and failure counts
    """
    logger.info(f"Starting bulk load: index={index_name}, chunk_size={chunk_size}")
    if enrichment_mode:
        logger.info(f"Enrichment mode: {enrichment_mode}")
    
    success_count = 0
    failure_count = 0
    
    try:
        # Use elasticsearch.helpers.bulk for robust bulk indexing
        for success, info in helpers.streaming_bulk(
            es_client,
            generate_actions(data_dir, index_name, enrichment_mode, health_summary),
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
    parser.add_argument(
        '--enrichment-mode',
        choices=['none', 'watch'],
        default='none',
        help='Enrichment mode: none (default) or watch (requires --health-export)'
    )
    parser.add_argument(
        '--health-export',
        help='Path to apple_health_export/export.xml for watch enrichment'
    )
    parser.add_argument(
        '--dump-health-csv',
        help='(Optional) Write parsed health summary to CSV for debugging'
    )
    parser.add_argument(
        '--baseline-resting-hr',
        type=int,
        default=50,
        help='Baseline resting HR for fatigue computation (default: 50 bpm)'
    )
    parser.add_argument(
        '--hrv-recovery-threshold',
        type=int,
        default=30,
        help='HRV threshold for recovery status (default: 30 ms)'
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
    
    # Handle enrichment mode
    enrichment_mode = args.enrichment_mode if args.enrichment_mode != 'none' else None
    health_summary = None
    
    if enrichment_mode == 'watch':
        if not ENRICHMENT_AVAILABLE:
            logger.error("Enrichment mode 'watch' requires parse_apple_hr module")
            sys.exit(1)
        if not args.health_export:
            logger.error("--enrichment-mode watch requires --health-export <path>")
            sys.exit(1)
        if not os.path.isfile(args.health_export):
            logger.error(f"Health export file not found: {args.health_export}")
            sys.exit(1)
        
        try:
            logger.info(f"Parsing Apple Health export: {args.health_export}")
            health_summary = parse_health_export(args.health_export)
            logger.info(f"Loaded health data for {len(health_summary)} days")
            
            # Optionally dump to CSV
            if args.dump_health_csv:
                import pandas as pd
                df_data = []
                for date, health in health_summary.items():
                    row = {"date": date}
                    row.update(health)
                    df_data.append(row)
                df = pd.DataFrame(df_data).sort_values("date")
                df.to_csv(args.dump_health_csv, index=False)
                logger.info(f"Health data written to: {args.dump_health_csv}")
        except Exception as e:
            logger.error(f"Error parsing health export: {str(e)}", exc_info=True)
            sys.exit(1)
    
    # Perform bulk load
    results = bulk_load(
        es_client=es,
        data_dir=args.data_dir,
        index_name=args.index,
        chunk_size=args.chunk_size,
        enrichment_mode=enrichment_mode,
        health_summary=health_summary
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
