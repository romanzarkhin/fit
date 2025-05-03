# Cycling FIT Dashboard with Elasticsearch & Kibana

This project processes `.fit` cycling activity files, extracts key metrics, calculates heart rate and power zones, and visualizes the data in Kibana dashboards.

It’s designed to work on **Windows 11** with Docker, Python, and Command Prompt.

---

## Project Structure

|__ fit_files
| |__ sample
| |-- 2024-01-27-20-09-14.fit
| |-- 2024-01-27-20-09-14.json
|-- cycling_dashboard.nsjson
|-- cycling_template.json
|-- docker-compose.yml
|-- fit_parser.py
|-- run_fit_pipeline.bat
|-- upload_to_elastic.bat
|-- zones.py

---

## Prerequisites

- Python 3.x installed and added to PATH  
- Docker Desktop installed and running  
- Elasticsearch + Kibana Docker images  
- `pip` package manager

---

## Setup Instructions

1.Clone the repository
```cmd```
git clone https://github.com/yourusername/cycling-fit-dashboard.git
cd cycling-fit-dashboard

2.Install Python dependencies
```cmd```
pip install -r requirements.txt

3.Start Elasticsearch + Kibana
```cmd```
docker-compose up -d

4.Run the data processing pipeline
```cmd```
run_fit_pipeline.bat

5.Upload data to Elasticsearch
```cmd```
upload_to_elastic.bat

6.Check Elasticsearch index status
```cmd```
curl -X GET "http://localhost:9200/_cat/indices?v"

7.Check index mappings
```cmd```
curl -X GET "http://localhost:9200/cycling-data/_mapping?pretty"

8.Open Kibana Dashboard
Go to -> http://localhost:5601/app/dashboards#
Look for the cycling_dashboard and explore!
