@echo off
echo Unzipping all_activities.zip...
powershell -Command "Expand-Archive -Force all_activities.zip ./unzipped"

echo Uploading files to Elasticsearch...
for %%f in (unzipped\*.json) do (
    echo Uploading %%f...
    curl -X POST "localhost:9200/cycling-data/_doc" -H "Content-Type: application/json" --data-binary @%%f
    if %errorlevel% neq 0 echo Failed to upload %%f >> upload_errors.log
)
echo Done! Check upload_errors.log if you see problems.
pause
