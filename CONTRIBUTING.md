# Contributing

## Principles

- Keep IoTron board-agnostic at the control-plane level.
- Treat protocol support as pluggable capability, not hardcoded behavior.
- Preserve backward compatibility for `config.json` and `vendor/installed_packages.db`.
- Keep the MVP Python package working even while native `core/` modules evolve.

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
