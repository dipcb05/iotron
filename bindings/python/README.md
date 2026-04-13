# Python Binding

The active Python implementation for IoTron lives in the root `iotron/` package.

This binding directory exposes a native bridge helper in `iotron.py` that can load the compiled IoTron shared library when `IOTRON_NATIVE_LIB` is set.

Use:

```bash
python -m iotron.cli status
python -m iotron.cli build-native
uvicorn iotron.api:app --reload
```
