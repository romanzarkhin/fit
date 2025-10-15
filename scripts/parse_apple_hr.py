import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime

def parse_apple_health_export(xml_path="apple_health_export/export.xml"):
    """
    Parse Apple Health export XML and extract heart rate records.
    Returns a CSV with daily heart rate summaries.
    """
    print(f"Parsing Apple Health export from {xml_path}...")
    
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except FileNotFoundError:
        print(f"❌ File not found: {xml_path}")
        print("   Skipping Apple Health parsing - this is optional.")
        return None
    
    hr_records = []
    
    for record in root.findall(".//Record[@type='HKQuantityTypeIdentifierHeartRate']"):
        date_str = record.get('startDate')
        value = float(record.get('value'))
        
        # Parse timestamp
        timestamp = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
        date = timestamp.date()
        
        hr_records.append({
            'date': date,
            'heart_rate': value,
            'timestamp': timestamp
        })
    
    if not hr_records:
        print("⚠ No heart rate records found in export")
        return None
    
    df = pd.DataFrame(hr_records)
    
    # Compute daily summaries
    daily_summary = df.groupby('date').agg({
        'heart_rate': ['mean', 'min', 'max', 'std']
    }).reset_index()
    
    daily_summary.columns = ['date', 'avg_hr', 'min_hr', 'max_hr', 'std_hr']
    
    output_file = 'daily_hr_summary.csv'
    daily_summary.to_csv(output_file, index=False)
    
    print(f"✓ Saved {len(daily_summary)} daily summaries to {output_file}")
    return output_file

if __name__ == "__main__":
    parse_apple_health_export()

