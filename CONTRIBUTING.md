# Contributing

## Principles

- Keep IoTron board-agnostic at the control-plane level.
- Treat protocol support as pluggable capability, not hardcoded behavior.
- Preserve backward compatibility for `config.json` and legacy JSON imports under `vendor/`, while treating `vendor/iotron_state.db` as the active local backend.
- Keep the Python package and native `core/` modules aligned as the framework evolves.

## Local Setup

```bash
pip install -r requirements.txt
python scripts/migrate_db.py
python -m unittest discover -s tests
```

## Areas Open For Contribution

- Native board runners in `core/devices/`
- Protocol adapters in `core/protocols/` and `core/networking/`
- Dashboard frontend
- Storage backends beyond the local JSON registry
- AI provider plugins and analytics pipelines
- CI automation and packaging
