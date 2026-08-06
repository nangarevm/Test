"""Background daemon management for automated Telegram + scanning."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from rich.console import Console

console = Console()


def pid_file_path(config: dict, data_dir: Path) -> Path:
    automation = config.get("automation", {})
    rel = automation.get("pid_file", "qa-leadgen.pid")
    path = Path(rel)
    if not path.is_absolute():
        path = data_dir / path.name if path.parent == Path(".") else data_dir / path
    return path


def log_file_path(config: dict, data_dir: Path) -> Path:
    automation = config.get("automation", {})
    rel = automation.get("log_file", "automation.log")
    path = Path(rel)
    if not path.is_absolute():
        path = data_dir / path.name if path.parent == Path(".") else data_dir / path
    return path


def read_pid(pid_file: Path) -> int | None:
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except ValueError:
        return None


def is_process_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def write_pid(pid_file: Path, pid: int) -> None:
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(pid))


def remove_pid(pid_file: Path) -> None:
    if pid_file.exists():
        pid_file.unlink()


def start_daemon(project_root: Path, config_path: str, all_qa: bool = False) -> int:
    """Start automation worker in background. Returns PID."""
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Load config for pid path — import here to avoid circular imports
    sys.path.insert(0, str(project_root))
    from src.config import load_config

    config = load_config(project_root / config_path)
    pid_file = pid_file_path(config, data_dir)
    log_file = log_file_path(config, data_dir)

    existing = read_pid(pid_file)
    if existing and is_process_running(existing):
        console.print(f"[yellow]Automation already running (PID {existing})[/yellow]")
        return existing

    if existing:
        remove_pid(pid_file)

    main_py = project_root / "main.py"
    cmd = [
        sys.executable,
        str(main_py),
        "-c",
        config_path,
        "automate",
        "worker",
    ]
    if all_qa:
        cmd.append("--all-qa")

    log_handle = open(log_file, "a", encoding="utf-8")
    log_handle.write(f"\n--- Started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    log_handle.flush()

    proc = subprocess.Popen(
        cmd,
        cwd=str(project_root),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    write_pid(pid_file, proc.pid)
    console.print(f"[green]Automation started (PID {proc.pid})[/green]")
    console.print(f"  Log: {log_file}")
    return proc.pid


def stop_daemon(config: dict, data_dir: Path) -> bool:
    pid_file = pid_file_path(config, data_dir)
    pid = read_pid(pid_file)
    if not pid:
        console.print("[yellow]Automation is not running (no PID file).[/yellow]")
        return False
    if not is_process_running(pid):
        console.print("[yellow]Stale PID file found; cleaning up.[/yellow]")
        remove_pid(pid_file)
        return False

    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            if not is_process_running(pid):
                break
            time.sleep(0.25)
        if is_process_running(pid):
            os.kill(pid, signal.SIGKILL)
        remove_pid(pid_file)
        console.print(f"[green]Automation stopped (PID {pid})[/green]")
        return True
    except OSError as exc:
        console.print(f"[red]Failed to stop automation: {exc}[/red]")
        return False


def daemon_status(config: dict, data_dir: Path) -> dict:
    pid_file = pid_file_path(config, data_dir)
    log_file = log_file_path(config, data_dir)
    pid = read_pid(pid_file)
    running = bool(pid and is_process_running(pid))
    state_file = data_dir / "telegram_state.json"
    scanning = False
    if state_file.exists():
        import json

        scanning = json.loads(state_file.read_text()).get("scanning_enabled", False)

    return {
        "running": running,
        "pid": pid if running else None,
        "scanning_enabled": scanning,
        "pid_file": str(pid_file),
        "log_file": str(log_file),
    }
