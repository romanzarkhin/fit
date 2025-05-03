# ?? Cycling FIT Dashboard with Elasticsearch & Kibana

This project processes `.fit` cycling activity files, extracts key metrics, calculates heart rate and power zones, and visualizes the data in Kibana dashboards.

It’s designed to work on **Windows 11** with Docker, Python, and Command Prompt.

---

## ?? Project Structure

C:\Users\Roman\Desktop\local\fit
|__ pycache__
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

## ?? Prerequisites

- Python 3.x installed and added to PATH  
- Docker Desktop installed and running  
- Elasticsearch + Kibana Docker images  
- `pip` package manager

---

## ?? Setup Instructions

1. **Clone the repository**

```cmd
git clone https://github.com/yourusername/cycling-fit-dashboard.git
cd cycling-fit-dashboard
Install Python dependencies

2.Install Python dependencies
cmd
Copy
Edit
pip install -r requirements.txt
Start Elasticsearch + Kibana

3.Start Elasticsearch + Kibana
cmd
Copy
Edit
docker-compose up -d
Run the data processing pipeline

4.Run the data processing pipeline
cmd
Copy
Edit
run_fit_pipeline.bat
Upload data to Elasticsearch

5.Upload data to Elasticsearch
cmd
Copy
Edit
upload_to_elastic.bat
Check Elasticsearch index status

6.Check Elasticsearch index status
cmd
Copy
Edit
curl -X GET "http://localhost:9200/_cat/indices?v"
Check index mappings

7.Check index mappings
cmd
Copy
Edit
curl -X GET "http://localhost:9200/cycling-data/_mapping?pretty"
Open Kibana Dashboard

8.Open Kibana Dashboard
Go to ? http://localhost:5601/app/dashboards#
Look for the cycling_dashboard and explore!