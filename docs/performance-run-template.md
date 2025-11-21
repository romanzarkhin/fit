# Performance Run Template

Use this template to record reproducible benchmark runs and environment details for the Elasticsearch bulk loader.

## Environment Details

### Hardware
- **CPU**: [e.g., Apple M1, Intel Core i7-9750H, AMD Ryzen 9 5950X]
- **CPU Cores**: [e.g., 8 cores, 16 threads]
- **RAM**: [e.g., 16GB, 32GB]
- **Storage Type**: [e.g., NVMe SSD, SATA SSD, HDD]
- **Storage Available**: [e.g., 500GB free]

### Software
- **OS**: [e.g., macOS 13.4, Ubuntu 22.04, Windows 11]
- **Python Version**: [e.g., Python 3.11.4]
- **Elasticsearch Version**: [e.g., 8.13.4]
- **Docker Version** (if applicable): [e.g., Docker Desktop 4.20.0]

### Elasticsearch Configuration
- **Heap Size**: [e.g., 2GB, 4GB]
- **Index Settings**:
  - `refresh_interval`: [e.g., -1 (disabled), 1s]
  - `number_of_replicas`: [e.g., 0, 1]
  - `number_of_shards`: [e.g., 1, 5]
- **Other Settings**: [e.g., compression enabled, custom mappings]

### Dataset Details
- **Number of FIT Files**: [e.g., 50 files]
- **Total Size**: [e.g., 25MB]
- **Total Records/Documents**: [e.g., ~50,000 records]
- **Data Source**: [e.g., Garmin Edge 530 cycling activities]

## Test Configuration

### Bulk Loader Settings
```bash
ES_HOST=http://localhost:9200 \
python3 scripts/es_bulk_loader.py \
    --data-dir garmin \
    --index fit-bench \
    --chunk-size 500
```

- **Chunk Size**: [e.g., 500]
- **Max Retries**: [default: 3]
- **Initial Backoff**: [default: 2.0s]
- **Max Backoff**: [default: 60.0s]

## Results

### Run #1 - [Date: YYYY-MM-DD]

**Configuration**:
- Chunk size: [e.g., 500]
- Index settings: refresh_interval=-1, replicas=0

**Results**:
- Total documents indexed: [e.g., 48,523]
- Successful: [e.g., 48,523]
- Failed: [e.g., 0]
- Total time: [e.g., 42.5 seconds]
- Throughput: [e.g., ~1,142 docs/sec]
- Peak memory usage: [e.g., 850MB]

**Observations**:
- [e.g., No failures, consistent throughput]
- [e.g., CPU utilization stayed around 60%]
- [e.g., Network I/O was not a bottleneck]

**Log Excerpts** (if relevant):
```
2025-05-15 10:23:45 - INFO - Starting bulk load: index=fit-bench, chunk_size=500
2025-05-15 10:24:27 - INFO - Bulk load completed: 48523 successful, 0 failed
```

---

### Run #2 - [Date: YYYY-MM-DD]

**Configuration**:
- Chunk size: [e.g., 1000]
- Index settings: refresh_interval=-1, replicas=0

**Results**:
- Total documents indexed: [e.g., 48,523]
- Successful: [e.g., 48,520]
- Failed: [e.g., 3]
- Total time: [e.g., 38.2 seconds]
- Throughput: [e.g., ~1,270 docs/sec]
- Peak memory usage: [e.g., 1.2GB]

**Observations**:
- [e.g., 3 failures due to malformed timestamps in 1 file]
- [e.g., Higher chunk size improved throughput by ~11%]
- [e.g., Slightly higher memory usage but still acceptable]

**Log Excerpts** (if relevant):
```
2025-05-15 11:45:12 - ERROR - Failed to index document 2025-05-10-06-20-39-345: ...
```

---

### Run #3 - [Date: YYYY-MM-DD]

**Configuration**:
- [Add additional test configuration]

**Results**:
- [Add results]

**Observations**:
- [Add observations]

---

## Comparative Analysis

### Chunk Size Impact

| Chunk Size | Total Time | Throughput (docs/sec) | Success Rate | Memory Usage |
|------------|------------|----------------------|--------------|--------------|
| 100        | [e.g., 65s] | [e.g., 746] | [e.g., 100%] | [e.g., 450MB] |
| 500        | [e.g., 42s] | [e.g., 1,142] | [e.g., 100%] | [e.g., 850MB] |
| 1000       | [e.g., 38s] | [e.g., 1,270] | [e.g., 99.9%] | [e.g., 1.2GB] |
| 2000       | [e.g., 36s] | [e.g., 1,347] | [e.g., 98.5%] | [e.g., 2.1GB] |

### Key Findings
- **Optimal chunk size**: [e.g., 1000 for this dataset and hardware]
- **Bottlenecks identified**: [e.g., FIT file parsing, network latency, ES indexing]
- **Recommendations**: [e.g., Use chunk size 1000 for datasets < 100MB, monitor memory with larger chunks]

## Failure Analysis

### Common Failure Patterns

1. **Malformed Data**
   - Files affected: [e.g., 2025-05-10-06-20-39.fit]
   - Error type: [e.g., Invalid timestamp format]
   - Resolution: [e.g., Added data validation in parser]

2. **ES Rejections**
   - Cause: [e.g., Queue capacity exceeded]
   - Frequency: [e.g., 0.1% of requests]
   - Resolution: [e.g., Reduced chunk size to 500]

3. **Network Timeouts**
   - Cause: [e.g., Slow network connection to ES]
   - Resolution: [e.g., Increased timeout settings]

## Recommendations

Based on the test runs, here are recommendations for production use:

1. **Chunk Size**: [e.g., Use 1000 for typical datasets, reduce to 500 if failures occur]
2. **Index Settings**: [e.g., Set refresh_interval=-1 and replicas=0 during bulk load, restore afterward]
3. **Hardware**: [e.g., Minimum 8GB RAM, SSD storage recommended]
4. **Monitoring**: [e.g., Monitor es_bulk_failures.log for individual failures]
5. **Error Handling**: [e.g., Review failure logs and reprocess failed files if needed]

## Notes

- Always test with a representative subset of your data first
- Monitor Elasticsearch heap usage during bulk loads
- Consider using multiple loader instances for very large datasets (shard per loader)
- Disable refresh and replicas during bulk load, enable after completion
- Review `es_bulk_failures.log` for any indexing errors

## Reproducibility Checklist

- [ ] Environment details documented
- [ ] Dataset characteristics recorded
- [ ] Elasticsearch settings specified
- [ ] Bulk loader configuration noted
- [ ] Results captured with timing and throughput
- [ ] Failure logs reviewed and documented
- [ ] Comparative analysis performed (if multiple runs)
- [ ] Recommendations based on findings

---

**Template Version**: 1.0  
**Last Updated**: [Date]  
**Maintained By**: [Your Name/Team]
