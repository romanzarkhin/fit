@echo off
echo Creating Python environment and installing dependencies...
pip install -r requirements.txt

echo Starting Docker stack...
docker-compose up -d

echo Parsing FIT files...
python fit_parser.py

echo Uploading to Elasticsearch...
call upload_to_elastic.bat

echo Importing index template...
curl -X PUT "http://localhost:9200/_index_template/cycling_template" -H "Content-Type: application/json" --data-binary "@cycling_template.json"

echo Importing Kibana dashboard...
curl -X POST "http://localhost:5601/api/saved_objects/_import?overwrite=true" -H "kbn-xsrf: true" --form file=@cycling_dashboard.nsjson

echo All done! Visit http://localhost:5601/app/dashboards#
pause
