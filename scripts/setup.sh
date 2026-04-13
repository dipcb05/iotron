#!/usr/bin/env bash
set -euo pipefail

python scripts/migrate_db.py
pip install -r requirements.txt

echo "IoTron setup completed."
