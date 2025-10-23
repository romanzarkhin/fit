# Performance run template

Use this template to capture all data for a reproducible bulk-load benchmark.

## Metadata
- Repository commit: (git commit SHA)
- Branch: 
- PR (if applicable): https://github.com/romanzarkhin/fit/pull/1
- Author: 
- Date (UTC): 

## Environment
- Machine / host name:
- OS + version:
- Python version:
- Elasticsearch version:
- Elasticsearch distribution (OSS/Elastic/Cloud):
- Number of ES nodes:
- Node hardware: CPU, RAM
- Disk type (SSD/HDD) and filesystem:
- Network (local, same host, remote IP, cloud zone):
- Elasticsearch config used (provide exact server config or link to export):
  - cluster.name:
  - node.data:
  - network.host:
  - indices.fielddata.cache.size:
  - Other tuned params:

## Index settings for test
- Index name used: 
- Number of shards:
- Number of replicas:
- refresh_interval before run:
- any special mappings (attach mapping JSON):
- any additional index templates in use:

## Dataset
- Source dataset path (local path or S3):
- Number of files: 
- File format: .fit
- Total dataset size: (MB)
- Total expected records: 
- Sample file(s) used: 
- Method used to count records (brief):

## Command(s) run
- Python command (include args / env vars):
  - Example:
    ES_HOST=http://localhost:9200 python3 scripts/es_bulk_loader.py --data-dir /data/fit --index fit-bench --chunk-size 500 --max-retries 5
- Notes about config changes applied before the run:
  - Example: set refresh_interval=-1, replicas=0

## Chunking & tuning matrix (record multiple runs)
- Run 1:
  - chunk_size: 100
  - max_retries: 3
  - elapsed_seconds:
  - indexed:
  - failed:
  - throughput (docs/sec):
  - notes (CPU, ES logs):
- Run 2:
  - chunk_size: 500
  - ...
- Run N:
  - ...

## Observed results and logs
- Attach or link to raw logs (loader stdout, es_bulk_failures.log).
- Attach or link to ES slowlogs if applicable.
- Summarize anomalies or failed items.

## Validation
- Count documents in index: (curl or es client command)
- Sampling checks (list a few doc ids and their fields).
- Any mapping surprises?

## Clean up & restore
- Commands used to revert index settings (refresh_interval, replicas).
- Any other cleanup steps.

## Conclusion & recommendations
- Best chunk size observed:
- Recommended default settings (index name, mapping, refresh_interval, replicas).
- Notes about dataset characteristics and how they affect throughput.
