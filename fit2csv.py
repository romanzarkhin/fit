import os
import pandas as pd
import fitdecode

def parse_all_fit_files(directory):
    all_data = []

    for filename in os.listdir(directory):
        if filename.endswith(".fit"):
            file_path = os.path.join(directory, filename)
            print(f"Parsing {filename}...")
            try:
                with fitdecode.FitReader(file_path) as fit:
                    for frame in fit:
                        if frame.frame_type == fitdecode.FIT_FRAME_DATA and frame.name == 'record':
                            record = {field.name: field.value for field in frame.fields}
                            record['source_file'] = filename
                            all_data.append(record)
            except Exception as e:
                print(f"Error parsing {filename}: {e}")

    return pd.DataFrame(all_data)

# Set your input folder and output file name
input_folder = "garmin/temp"
output_csv = "garmin/combined_fit_data.csv"

# Parse files and export
df = parse_all_fit_files(input_folder)
df.to_csv(output_csv, index=False)

print(f"Saved combined data to {output_csv}")
