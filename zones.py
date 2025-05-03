# -*- coding: utf-8 -*-
import math
import json

def clean_nan(data):
    """Replace NaN values with None in a nested dictionary."""
    cleaned = {}
    for key, value in data.items():
        if isinstance(value, float) and math.isnan(value):
            cleaned[key] = None
        else:
            cleaned[key] = value
    return cleaned

def get_heart_rate_zone(heart_rate):
    """Return heart rate zone name based on value."""
    if heart_rate is None:
        return None
    if heart_rate < 120:
        return 'Zone 1'
    elif heart_rate < 140:
        return 'Zone 2'
    elif heart_rate < 160:
        return 'Zone 3'
    elif heart_rate < 180:
        return 'Zone 4'
    else:
        return 'Zone 5'

def get_power_zone(power):
    """Return power zone name based on value."""
    if power is None:
        return None
    if power < 120:
        return 'Zone 1'
    elif power < 134:
        return 'Zone 2'
    elif power < 168:
        return 'Zone 3'
    elif power < 193:
        return 'Zone 4'
    elif power < 210:
        return 'Zone 5'
    elif power < 238:
        return 'Zone 6'
    else:
        return 'Zone 7'

# Example input - replace with your loop over real data
sample_data_list = [
    {"altitude": 274.2, "cadence": 0, "accumulated_power": float('nan'), "left_pedal_smoothness": float('nan'), "heart_rate": 135, "power": 180, "timestamp": "2024-01-27T19:09:18"},
    {"altitude": 280.5, "cadence": 80, "accumulated_power": 500, "left_pedal_smoothness": 23, "heart_rate": 155, "power": 200, "timestamp": "2024-01-27T19:19:18"}
]

for data in sample_data_list:
    cleaned_data = clean_nan(data)
    cleaned_data["heart_rate_zone"] = get_heart_rate_zone(cleaned_data.get("heart_rate"))
    cleaned_data["power_zone"] = get_power_zone(cleaned_data.get("power"))
    
    json_str = json.dumps(cleaned_data, ensure_ascii=False)
    print(json_str)
