"""CLI entry point for IoTron."""

from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any

from .service import IoTronService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="iotron", description="IoTron IoT control plane CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show project status")

    boards = subparsers.add_parser("boards", help="List supported boards")
    boards.add_argument("--family", help="Filter by board family")

    subparsers.add_parser("protocols", help="List supported embedded protocols")
    subparsers.add_parser("networks", help="List supported network transports")
    subparsers.add_parser("toolchains", help="List supported board toolchains")
    subparsers.add_parser("list", help="List installed packages")
    subparsers.add_parser("devices", help="List registered devices")
    subparsers.add_parser("export-config", help="Print config.json")

    telemetry = subparsers.add_parser("telemetry", help="List telemetry events")
    telemetry.add_argument("--device-id")
    telemetry.add_argument("--limit", type=int, default=25)

    install = subparsers.add_parser("install", help="Install a package")
    install.add_argument("package")
    install.add_argument("--version", default="latest")

    uninstall = subparsers.add_parser("uninstall", help="Remove a package")
    uninstall.add_argument("package")

    update = subparsers.add_parser("update", help="Update a package")
    update.add_argument("package")
    update.add_argument("--version", default="latest")

    board = subparsers.add_parser("select-board", help="Select the active board")
    board.add_argument("board")

    protocol = subparsers.add_parser("enable-protocol", help="Enable a protocol")
    protocol.add_argument("protocol")

    network = subparsers.add_parser("enable-network", help="Enable a network")
    network.add_argument("network")

    web = subparsers.add_parser("web", help="Web dashboard commands")
    web_subparsers = web.add_subparsers(dest="web_command", required=True)
    web_subparsers.add_parser("install", help="Install the web dashboard packages")

    flash = subparsers.add_parser("flash", help="Build a flash plan or execute it")
    flash.add_argument("board")
    flash.add_argument("artifact")
    flash.add_argument("--port")
    flash.add_argument("--fqbn")
    flash.add_argument("--execute", action="store_true")

    ota = subparsers.add_parser("ota", help="Build an OTA plan or execute it")
    ota.add_argument("board")
    ota.add_argument("artifact")
    ota.add_argument("--host", required=True)
    ota.add_argument("--username", default="iotron")
    ota.add_argument("--destination", default="/opt/iotron/ota")
    ota.add_argument("--execute", action="store_true")

    native = subparsers.add_parser("build-native", help="Build the native IoTron shared library")
    native.add_argument("--python", default="python")

    ai_plan = subparsers.add_parser("ai-plan", help="Generate an AI-assisted project plan")
    ai_plan.add_argument("--goal", required=True)
    ai_plan.add_argument("--board")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    service = IoTronService()

    try:
        result = dispatch(service, args)
    except ValueError as exc:
        parser.error(str(exc))
        return

    print(json.dumps(result, indent=2))


def dispatch(service: IoTronService, args: argparse.Namespace) -> Any:
    if args.command == "status":
        return service.status()
    if args.command == "boards":
        return service.list_boards(args.family)
    if args.command == "protocols":
        return service.list_protocols()
    if args.command == "networks":
        return service.list_networks()
    if args.command == "toolchains":
        return service.list_toolchains()
    if args.command == "devices":
        return service.list_devices()
    if args.command == "telemetry":
        return service.list_telemetry(device_id=args.device_id, limit=args.limit)
    if args.command == "list":
        return service.list_packages()
    if args.command == "export-config":
        return service.export_config()
    if args.command == "install":
        return service.install_package(args.package, version=args.version)
    if args.command == "uninstall":
        removed = service.uninstall_package(args.package)
        return {"removed": removed, "package": args.package}
    if args.command == "update":
        return service.update_package(args.package, version=args.version)
    if args.command == "select-board":
        return service.select_board(args.board)
    if args.command == "enable-protocol":
        return service.enable_protocol(args.protocol)
    if args.command == "enable-network":
        return service.enable_network(args.network)
    if args.command == "web" and args.web_command == "install":
        return service.install_web_dashboard()
    if args.command == "flash":
        return service.flash_firmware(
            board=args.board,
            artifact=args.artifact,
            port=args.port,
            fqbn=args.fqbn,
            execute=args.execute,
        )
    if args.command == "ota":
        return service.ota_update(
            board=args.board,
            artifact=args.artifact,
            host=args.host,
            username=args.username,
            destination=args.destination,
            execute=args.execute,
        )
    if args.command == "build-native":
        completed = subprocess.run([args.python, "scripts/build_native.py"], check=False)
        return {"returncode": completed.returncode}
    if args.command == "ai-plan":
        return service.ai_plan(goal=args.goal, board=args.board)
    raise ValueError(f"Unsupported command '{args.command}'")


if __name__ == "__main__":
    main()
