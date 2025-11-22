#!/usr/bin/env python3
"""
Apple Health Export Parser

Parses Apple Health export.xml files to extract daily heart rate summaries,
HRV, step count, and active energy metrics for enriching cycling sessions.
"""

import xml.etree.ElementTree as ET
import pandas as pd
from collections import defaultdict
from typing import Dict, Any
from datetime import datetime


def parse_health_export(xml_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Parse Apple Health export.xml into date-keyed summaries.
    
    Args:
        xml_path: Path to apple_health_export/export.xml
        
    Returns:
        Dict keyed by ISO date (YYYY-MM-DD) with health metrics:
        {
            "2025-03-15": {
                "resting_hr": 52,
                "avg_hr": 68.5,
                "min_hr": 42,
                "max_hr": 115,
                "hrv": 45.2,
                "step_count": 8234,
                "active_energy_kcal": 450
            },
            ...
        }
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    # Initialize data structures for each day
    daily_data = defaultdict(lambda: {
        "resting_hr": [],
        "heart_rate": [],
        "hrv": [],
        "step_count": [],
        "active_energy": []
    })
    
    # Loop through Record entries
    for record in root.findall("Record"):
        record_type = record.attrib.get("type")
        start_date = record.attrib.get("startDate")
        value = record.attrib.get("value")
        
        if not all([record_type, start_date, value]):
            continue
        
        try:
            # Extract date in YYYY-MM-DD format
            date_obj = pd.to_datetime(start_date)
            date_str = date_obj.strftime("%Y-%m-%d")
            val = float(value)
            
            # Categorize by type
            if record_type == "HKQuantityTypeIdentifierRestingHeartRate":
                daily_data[date_str]["resting_hr"].append(val)
            elif record_type == "HKQuantityTypeIdentifierHeartRate":
                daily_data[date_str]["heart_rate"].append(val)
            elif record_type == "HKQuantityTypeIdentifierHeartRateVariabilitySDNN":
                daily_data[date_str]["hrv"].append(val)
            elif record_type == "HKQuantityTypeIdentifierStepCount":
                daily_data[date_str]["step_count"].append(val)
            elif record_type == "HKQuantityTypeIdentifierActiveEnergyBurned":
                daily_data[date_str]["active_energy"].append(val)
        except (ValueError, AttributeError):
            continue
    
    # Aggregate daily summaries
    summary = {}
    for date_str, metrics in daily_data.items():
        agg = {}
        
        # Calculate aggregates for each metric
        if metrics["resting_hr"]:
            agg["resting_hr"] = round(pd.Series(metrics["resting_hr"]).mean(), 1)
        
        if metrics["heart_rate"]:
            agg["avg_hr"] = round(pd.Series(metrics["heart_rate"]).mean(), 1)
            agg["min_hr"] = round(pd.Series(metrics["heart_rate"]).min(), 1)
            agg["max_hr"] = round(pd.Series(metrics["heart_rate"]).max(), 1)
        
        if metrics["hrv"]:
            agg["hrv"] = round(pd.Series(metrics["hrv"]).mean(), 1)
        
        if metrics["step_count"]:
            agg["step_count"] = int(pd.Series(metrics["step_count"]).sum())
        
        if metrics["active_energy"]:
            agg["active_energy_kcal"] = round(pd.Series(metrics["active_energy"]).sum(), 1)
        
        if agg:  # Only include dates with at least one metric
            summary[date_str] = agg
    
    return summary


if __name__ == "__main__":
    # CLI: parse and export to CSV
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 parse_apple_hr.py <path_to_export.xml> [output.csv]")
        sys.exit(1)
    
    xml_file = sys.argv[1]
    csv_file = sys.argv[2] if len(sys.argv) > 2 else "daily_hr_summary.csv"
    
    try:
        health_data = parse_health_export(xml_file)
        
        # Convert to DataFrame and save
        df_data = []
        for date, metrics in health_data.items():
            row = {"date": date}
            row.update(metrics)
            df_data.append(row)
        
        df = pd.DataFrame(df_data).sort_values("date")
        df.to_csv(csv_file, index=False)
        print(f"✅ Apple Health data exported to {csv_file} ({len(df)} days)")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)