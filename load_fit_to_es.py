#!/usr/bin/env python3
"""
DEPRECATED: This file is kept for backward compatibility.

For loading Garmin FIT files to Elasticsearch, use one of:
  - python3 scripts/es_bulk_loader.py       (recommended for production - robust bulk loader)
  - python3 scripts/load_fit_to_es.py       (lightweight, single-threaded)

Or use the setup script:
  - sh elk_fit_setup.sh                     (complete ELK Stack + data loading setup)
"""

import sys
import subprocess
from pathlib import Path

# Run the lightweight loader from scripts directory for backward compatibility
script_path = Path(__file__).parent / "scripts" / "load_fit_to_es.py"
sys.exit(subprocess.call([sys.executable, str(script_path)] + sys.argv[1:]))
