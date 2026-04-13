"""Initialize or repair IoTron's local config and package registry."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from iotron.storage import load_config, load_packages, load_runtime_state


def main() -> None:
    load_config()
    load_packages()
    load_runtime_state()
    print("IoTron config, package registry, and runtime state are ready.")


if __name__ == "__main__":
    main()
