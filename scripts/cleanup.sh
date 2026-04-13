#!/usr/bin/env bash
set -euo pipefail

rm -rf __pycache__ .pytest_cache build dist .venv venv

echo "IoTron local artifacts cleaned."
