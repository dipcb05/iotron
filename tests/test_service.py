from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from iotron.ai import build_project_plan
from iotron.api import app, dashboard
from iotron.security import issue_device_token, issue_operator_token, verify_token
from iotron.service import IoTronService
from iotron.storage import CONFIG_PATH, PACKAGE_DB_PATH, RUNTIME_STATE_PATH, SQLITE_DB_PATH
from iotron.toolchains import build_artifact_manifest, validate_artifact, verify_artifact_manifest


class IoTronServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        CONFIG_PATH.write_text(
            json.dumps(
                {
                    "project": "IoTron",
                    "version": "0.3.0",
                    "selected_board": None,
                    "enabled_protocols": [],
                    "enabled_networks": [],
                    "features": {
                        "web_dashboard": False,
                        "fastapi": True,
                        "ai_assistant": True,
                    },
                    "paths": {
                        "packages_db": "vendor/iotron_state.db",
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        PACKAGE_DB_PATH.write_text('{"packages": []}\n', encoding="utf-8")
        RUNTIME_STATE_PATH.write_text('{"devices": [], "telemetry": []}\n', encoding="utf-8")
        if SQLITE_DB_PATH.exists():
            SQLITE_DB_PATH.unlink()
        os.environ["IOTRON_BEARER_SECRET"] = "test-secret"
        self.service = IoTronService()

    def tearDown(self) -> None:
        os.environ.pop("IOTRON_BEARER_SECRET", None)

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

    def test_flash_plan_returns_deployment_metadata(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(b"firmware-binary")
            artifact = handle.name
        try:
            plan = self.service.flash_firmware("esp32", artifact)
        finally:
            Path(artifact).unlink(missing_ok=True)
        self.assertEqual(plan["operation"], "flash")
        self.assertEqual(plan["toolchain"], "esptool")
        self.assertIn("deployment_id", plan)
        self.assertIn("artifact_sha256", plan)

    def test_dashboard_data_contains_toolchains(self) -> None:
        payload = self.service.dashboard_data()
        self.assertIn("toolchains", payload)
        self.assertGreaterEqual(len(payload["toolchains"]), 1)

    def test_register_device_and_ingest_telemetry(self) -> None:
        device = self.service.register_device("sensor-1", "esp32", protocol="i2c", network="mqtt")
        event = self.service.ingest_telemetry("sensor-1", "temperature_c", 23.5)
        self.assertEqual(device["device_id"], "sensor-1")
        self.assertIn("device_token", device)
        self.assertEqual(event["metric"], "temperature_c")
        self.assertEqual(len(self.service.list_devices()), 1)
        self.assertEqual(len(self.service.list_telemetry()), 1)

    def test_tokens_encode_roles(self) -> None:
        operator = verify_token(issue_operator_token("admin@example.com", "admin"))
        device = verify_token(issue_device_token("sensor-1"))
        self.assertEqual(operator["role"], "admin")
        self.assertEqual(device["role"], "device")
        self.assertEqual(device["device_id"], "sensor-1")

    def test_artifact_manifest_is_signed(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False) as handle:
            handle.write(b"signed-artifact")
            artifact = Path(handle.name)
        try:
            manifest = build_artifact_manifest(artifact)
            validation = validate_artifact(artifact, expected_sha256=manifest["sha256"])
        finally:
            artifact.unlink(missing_ok=True)
        self.assertTrue(verify_artifact_manifest(manifest))
        self.assertTrue(validation["verified"])

    def test_backend_overview_and_audit(self) -> None:
        self.service.register_device("sensor-1", "esp32", protocol="i2c", network="mqtt", actor="admin")
        self.service.install_package("telemetry-pipeline", actor="admin")
        overview = self.service.backend_overview()
        audit = self.service.list_audit_events(limit=10)
        self.assertEqual(overview["inventory"]["devices"], 1)
        self.assertGreaterEqual(len(audit), 2)

    def test_metrics_logs_and_alerts(self) -> None:
        self.service.install_package("telemetry-pipeline", actor="admin")
        self.service.register_device("sensor-1", "esp32", protocol="i2c", network="mqtt", actor="admin")
        metrics = self.service.get_metrics()
        logs = self.service.get_logs(limit=10)
        alerts = self.service.get_alerts()
        self.assertIn("packages.installed", metrics)
        self.assertGreaterEqual(len(logs), 1)
        self.assertIsInstance(alerts, list)

    def test_backup_and_restore_cycle(self) -> None:
        self.service.install_package("telemetry-pipeline", actor="admin")
        backup = self.service.create_backup(actor="admin")
        backups = self.service.list_backups()
        restored = self.service.restore_backup(backup["backup_id"], actor="admin")
        self.assertTrue(any(item["backup_id"] == backup["backup_id"] for item in backups))
        self.assertIn("restored_files", restored)

    def test_dashboard_route_points_to_html(self) -> None:
        response = dashboard()
        self.assertTrue(str(response.path).endswith("index.html"))
        self.assertTrue(Path(response.path).exists())

    def test_api_routes_include_runtime_and_security_endpoints(self) -> None:
        routes = {route.path for route in app.routes if hasattr(route, "path")}
        self.assertIn("/dashboard", routes)
        self.assertIn("/project/flash", routes)
        self.assertIn("/devices/register", routes)
        self.assertIn("/telemetry", routes)
        self.assertIn("/native/manifest", routes)
        self.assertIn("/auth/token", routes)
        self.assertIn("/audit", routes)
        self.assertIn("/metrics", routes)
        self.assertIn("/alerts", routes)
        self.assertIn("/backups", routes)
        self.assertIn("/dr/plan", routes)


if __name__ == "__main__":
    unittest.main()
