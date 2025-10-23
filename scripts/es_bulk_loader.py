#!/usr/bin/env python3
"""
Minimal, robust Elasticsearch bulk loader.

Place under scripts/es_bulk_loader.py.

Usage:
  python scripts/es_bulk_loader.py --data-dir /path/to/fit_files --index fit-index --chunk-size 500

Environment variables (optional):
  ES_HOST (default: http://localhost:9200)
  ES_TIMEOUT (default: 60)
  ES_USER / ES_PASSWORD (if basic auth)

Dependencies:
  pip install fitparse elasticsearch tqdm

This script is intentionally conservative:
- Uses helpers.bulk with configurable chunk_size
- Implements simple retry/backoff for bulk failures
- Writes a failure log with per-document error details
- Uses tqdm for progress feedback (can be disabled)
- Keeps changes local to scripts/
"""
import os
import sys
import json
import time
import logging
import argparse
from typing import Iterable, Dict, Any, Optional
from pathlib import Path

try:
    from elasticsearch import Elasticsearch, helpers
except Exception as e:
    raise RuntimeError("Install 'elasticsearch' Python client. pip install elasticsearch") from e

try:
    from tqdm import tqdm
except Exception:
    tqdm = None  # type: ignore

LOG = logging.getLogger("es_bulk_loader")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def parse_args():
    p = argparse.ArgumentParser(description="Bulk load .fit data into Elasticsearch")
    p.add_argument("--data-dir", required=True, help="Directory with .fit files (or files list)")
    p.add_argument("--index", required=True, help="Target Elasticsearch index name")
    p.add_argument("--chunk-size", type=int, default=int(os.getenv("CHUNK_SIZE", "500")), help="Bulk chunk size")
    p.add_argument("--max-retries", type=int, default=int(os.getenv("MAX_RETRIES", "5")), help="Max bulk retries")
    p.add_argument("--concurrency", type=int, default=1, help="Number of parallel worker threads (not implemented; reserved)")
    p.add_argument("--es-host", default=os.getenv("ES_HOST", "http://localhost:9200"))
    p.add_argument("--es-timeout", type=int, default=int(os.getenv("ES_TIMEOUT", "60")))
    p.add_argument("--dry-run", action="store_true", help="Don't send to ES, just simulate")
    p.add_argument("--id-field", default=None, help="Field name to use as _id (optional)")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()

def get_es_client(host: str, timeout: int = 60) -> Elasticsearch:
    es_kwargs = {"timeout": timeout}
    user = os.getenv("ES_USER")
    pwd = os.getenv("ES_PASSWORD")
    if user and pwd:
        es_kwargs["http_auth"] = (user, pwd)
    return Elasticsearch(hosts=[host], **es_kwargs)

# Try to reuse the repository's parser if available (load_fit_to_es.py)
try:
    # load_fit_to_es.py defines parse_fit_file(path) and compute_session_metrics(records)
    from load_fit_to_es import parse_fit_file, compute_session_metrics  # type: ignore
    LOG.info("Using parse_fit_file and compute_session_metrics from load_fit_to_es.py")
except Exception:
    # Fallback placeholder implementation (will be used if import fails)
    def parse_fit_file(path: Path) -> Iterable[Dict[str, Any]]:
        """
        Replace this with the repository's real .fit parsing function if import not available.
        This fallback yields a single doc per file with basic metadata.
        """
        yield {
            "id": str(path),
            "filename": path.name,
            "size_bytes": path.stat().st_size,
        }

    def compute_session_metrics(records: Iterable[Dict[str, Any]):
        return {}

def actions_from_files(files: Iterable[Path], index: str, id_field: Optional[str] = None):
    """
    For each .fit file, parse records, compute session metrics and yield bulk actions.
    This mirrors the behavior of the existing load_to_es() function in the repo.
    """
    for fp in files:
        # parse_fit_file in repository expects a path string; adapt if it accepts Path
        try:
            records = parse_fit_file(str(fp))
        except TypeError:
            # some implementations may accept Path
            records = parse_fit_file(fp)

        # compute aggregate session metrics if available
        try:
            session_metrics = compute_session_metrics(records)
        except Exception:
            session_metrics = {}

        session_id = fp.stem
        # If parse_fit_file returned a list-like object, ensure we can iterate twice by materializing
        recs = list(records)
        for i, record in enumerate(recs):
            # enrich record like existing loader
            record = dict(record)  # copy to avoid mutating originals
            record["session_id"] = session_id
            if session_metrics:
                record.update(session_metrics)
            action = {"_index": index, "_source": record}
            if id_field and id_field in record:
                action["_id"] = record[id_field]
            else:
                # keep deterministic id using session and index
                action["_id"] = f"{session_id}-{i}"
            yield action

def run_bulk_with_retries(es: Elasticsearch, actions_iter: Iterable[Dict[str, Any]], chunk_size: int = 500,
                          max_retries: int = 5, dry_run: bool = False, failure_log_path: Optional[Path] = None):
    attempts = 0
    total_indexed = 0
    total_failed = 0
    failure_log = open(failure_log_path, "w") if failure_log_path else None

    def chunked(actions, size):
        chunk = []
        for a in actions:
            chunk.append(a)
            if len(chunk) >= size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk

    # Materialize actions as list to allow chunk-by-chunk retries. For very large datasets this could be memory-heavy.
    all_actions = list(actions_iter)

    LOG.info("Total actions prepared: %d", len(all_actions))

    for chunk_idx, chunk in enumerate(chunked(all_actions, chunk_size)):
        success = False
        attempt = 0
        while not success and attempt <= max_retries:
            try:
                if dry_run:
                    LOG.info("Dry-run: would send chunk %d (size=%d)", chunk_idx, len(chunk))
                    success = True
                    total_indexed += len(chunk)
                    break
                resp = helpers.bulk(client=es, actions=chunk, chunk_size=len(chunk), request_timeout=60)
                successes = resp[0] if isinstance(resp, tuple) else len(chunk)
                errors = resp[1] if isinstance(resp, tuple) and len(resp) > 1 else []
                LOG.info("Chunk %d indexed: successes=%s errors=%s", chunk_idx, successes, len(errors) if errors else 0)
                total_indexed += successes
                if errors:
                    total_failed += len(errors)
                    for err in errors:
                        if failure_log:
                            failure_log.write(json.dumps(err) + "\n")
                success = True
            except Exception as exc:
                attempt += 1
                wait = min(60, 2 ** attempt)
                LOG.warning("Bulk chunk %d failed attempt %d/%d: %s. Retrying in %s sec...", chunk_idx, attempt, max_retries, exc, wait)
                time.sleep(wait)
        if not success:
            LOG.error("Chunk %d failed after %d attempts; skipping chunk", chunk_idx, attempt)
            total_failed += len(chunk)
    if failure_log:
        failure_log.close()
    return total_indexed, total_failed

def main():
    args = parse_args()
    if args.verbose:
        LOG.setLevel(logging.DEBUG)
    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        LOG.error("Data directory not found: %s", data_dir)
        sys.exit(2)

    files = sorted([p for p in data_dir.iterdir() if p.is_file() and p.suffix.lower() == ".fit"])
    if not files:
        LOG.error("No .fit files found in %s", data_dir)
        sys.exit(2)

    LOG.info("Files found: %d", len(files))
    es = get_es_client(args.es_host, timeout=args.es_timeout)

    actions = actions_from_files(files, index=args.index, id_field=args.id_field)

    start = time.time()
    failure_log_path = Path("es_bulk_failures.log")
    indexed, failed = run_bulk_with_retries(es=es, actions_iter=actions, chunk_size=args.chunk_size,
                                            max_retries=args.max_retries, dry_run=args.dry_run,
                                            failure_log_path=failure_log_path)
    elapsed = time.time() - start

    LOG.info("Bulk load finished. Indexed=%d Failed=%d Elapsed=%.2f sec Throughput=%.2f docs/sec",
             indexed, failed, elapsed, (indexed / elapsed) if elapsed > 0 else 0.0)
    print(json.dumps({
        "indexed": indexed,
        "failed": failed,
        "elapsed_seconds": elapsed,
        "throughput_docs_per_sec": (indexed / elapsed) if elapsed > 0 else None
    }, indent=2))

if __name__ == "__main__":
    main()
