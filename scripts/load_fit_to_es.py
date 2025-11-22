#!/usr/bin/env python3
"""
Simple Garmin FIT to Elasticsearch Loader

Lightweight single-threaded loader for small datasets.
For larger datasets, use es_bulk_loader.py instead.

Usage:
    python3 scripts/load_fit_to_es.py --folder garmin
    FIT_FOLDER=/path/to/fits python3 scripts/load_fit_to_es.py
"""

import os
import datetime
import argparse
from pathlib import Path
from elasticsearch import Elasticsearch

from es_bulk_loader import parse_fit_file, compute_session_metrics

# Configuration with precedence: CLI arg > ENV var > default
def get_folder_path():
    """Get folder path with precedence: CLI arg > ENV var > default relative path"""
    parser = argparse.ArgumentParser(description='Load Garmin FIT files to Elasticsearch')
    parser.add_argument('--folder', type=str, help='Folder containing .fit files')
    args = parser.parse_args()
    
    if args.folder:
        return Path(args.folder)
    
    env_folder = os.getenv('FIT_FOLDER')
    if env_folder:
        return Path(env_folder)
    
    # Default to garmin folder relative to repo root (parent of scripts dir)
    script_dir = Path(__file__).parent.parent
    return script_dir / 'garmin'

FOLDER = get_folder_path()
INDEX = "fit-data"

def load_to_es():
    """Load all .fit files from FOLDER into Elasticsearch."""
    es = Elasticsearch("http://localhost:9200")
    
    # Clear and recreate index
    es.indices.delete(index=INDEX, ignore_unavailable=True)
    es.indices.create(index=INDEX, ignore=400)
    
    count = 0
    for file_path in FOLDER.glob("*.fit"):
        records = parse_fit_file(str(file_path))
        session_metrics = compute_session_metrics(records)
        session_id = file_path.stem
        
        for i, record in enumerate(records):
            record["session_id"] = session_id
            record.update(session_metrics)
            
            # Convert datetime objects to ISO format strings
            for key, value in record.items():
                if isinstance(value, datetime.datetime):
                    record[key] = value.isoformat()
            
            es.index(index=INDEX, id=f"{file_path.name}-{i}", document=record)
            count += 1
    
    print(f"Indexed {count} records from {FOLDER}")

if __name__ == "__main__":
    load_to_es()
