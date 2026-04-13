from __future__ import annotations

import json
import unittest
from pathlib import Path

from iotron.ai import build_project_plan
from iotron.api import app, dashboard
from iotron.service import IoTronService
from iotron.storage import CONFIG_PATH, PACKAGE_DB_PATH, RUNTIME_STATE_PATH


class IoTronServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        CONFIG_PATH.write_text(
            json.dumps(
                {
                    "project": "IoTron",
                    "version": "0.2.0",
                    "selected_board": None,
                    "enabled_protocols": [],
                    "enabled_networks": [],
                    "features": {
                        "web_dashboard": False,
                        "fastapi": True,
                        "ai_assistant": True,
                    },
                    "paths": {
                        "packages_db": "vendor/installed_packages.db",
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        PACKAGE_DB_PATH.write_text('{"packages": []}\n', encoding="utf-8")
        RUNTIME_STATE_PATH.write_text('{"devices": [], "telemetry": []}\n', encoding="utf-8")
        self.service = IoTronService()

    def test_install_package_persists(self) -> None:
        package = self.service.install_package("mqtt-broker", version="1.0.0")
        self.assertEqual(package["name"], "mqtt-broker")
        self.assertEqual(len(self.service.list_packages()), 1)

    def test_enable_protocol_and_network(self) -> None:
        self.service.enable_protocol("i2c")
        self.service.enable_network("mqtt")
        status = self.service.status()
        self.assertIn("i2c", status["enabled_protocols"])
        self.assertIn("mqtt", status["enabled_networks"])

    def test_web_install_sets_feature(self) -> None:
        status = self.service.install_web_dashboard()
        self.assertTrue(status["features"]["web_dashboard"])
        package_names = {item["name"] for item in status["installed_packages"]}
        self.assertIn("web-dashboard", package_names)

    def test_ai_plan_has_recommendations(self) -> None:
        plan = build_project_plan("ESP32 telemetry dashboard with anomaly detection")
        self.assertEqual(plan["recommended_board"], "esp32")
        self.assertIn("mqtt", plan["recommended_networks"])
        self.assertIn("ai-assistant", plan["packages_to_install"])

    def test_flash_plan_returns_toolchain_metadata(self) -> None:
        plan = self.service.flash_firmware("esp32", "firmware.bin")
        self.assertEqual(plan["operation"], "flash")
        self.assertEqual(plan["toolchain"], "esptool")
        self.assertIn("command", plan)

    def test_dashboard_data_contains_toolchains(self) -> None:
        payload = self.service.dashboard_data()
        self.assertIn("toolchains", payload)
        self.assertGreaterEqual(len(payload["toolchains"]), 1)

    def test_register_device_and_ingest_telemetry(self) -> None:
        device = self.service.register_device("sensor-1", "esp32", protocol="i2c", network="mqtt")
        event = self.service.ingest_telemetry("sensor-1", "temperature_c", 23.5)
        self.assertEqual(device["device_id"], "sensor-1")
        self.assertEqual(event["metric"], "temperature_c")
        self.assertEqual(len(self.service.list_devices()), 1)
        self.assertEqual(len(self.service.list_telemetry()), 1)

    def test_dashboard_route_points_to_html(self) -> None:
        response = dashboard()
        self.assertTrue(str(response.path).endswith("index.html"))
        self.assertTrue(Path(response.path).exists())

    def test_api_routes_include_dashboard_and_flash(self) -> None:
        routes = {route.path for route in app.routes if hasattr(route, "path")}
        self.assertIn("/dashboard", routes)
        self.assertIn("/project/flash", routes)
        self.assertIn("/devices/register", routes)
        self.assertIn("/telemetry", routes)
        self.assertIn("/native/manifest", routes)


if __name__ == "__main__":
    unittest.main()
