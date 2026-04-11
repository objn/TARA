from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

JsonDict = Dict[str, Any]


@dataclass(frozen=True)
class Bytes:
    value: int

    def human(self) -> str:
        v = float(max(0, int(self.value)))
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        i = 0
        while v >= 1024.0 and i < len(units) - 1:
            v /= 1024.0
            i += 1
        if i == 0:
            return f"{int(v)} {units[i]}"
        return f"{v:.2f} {units[i]}"


def supported_os_or_error() -> Optional[JsonDict]:
    sysname = platform.system()
    if sysname.lower() not in {"windows", "linux"}:
        return {
            "ok": False,
            "error": f"Unsupported OS: {sysname}. Only Windows and Linux are supported.",
        }
    return None


def read_first_line(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return (f.readline() or "").strip()
    except Exception:
        return None


def invoke_powershell_json(command: str, *, timeout_s: float = 4.0) -> Optional[Any]:
    try:
        cp = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if cp.returncode != 0:
            return None
        out = (cp.stdout or "").strip()
        if not out:
            return None
        return json.loads(out)
    except Exception:
        return None


def basic_runtime_info() -> JsonDict:
    return {
        "python_version": sys.version.split()[0],
        "executable": sys.executable,
    }


def basic_machine_info() -> JsonDict:
    return {
        "hostname": socket.gethostname(),
        "architecture": platform.machine(),
        "platform": platform.platform(),
    }


def boot_time_epoch_seconds() -> Optional[float]:
    sysname_l = platform.system().lower()
    try:
        if sysname_l == "linux":
            line = read_first_line("/proc/uptime")
            if not line:
                return None
            seconds = float(line.split()[0])
            return time.time() - seconds
        if sysname_l == "windows":
            import ctypes

            ms = ctypes.windll.kernel32.GetTickCount64()
            return time.time() - (float(ms) / 1000.0)
    except Exception:
        return None
    return None


def disk_usage_for_path(path: str) -> Optional[JsonDict]:
    try:
        du = shutil.disk_usage(path)
        return {
            "path": path,
            "total_bytes": int(du.total),
            "free_bytes": int(du.free),
            "used_bytes": int(du.used),
            "total_human": Bytes(int(du.total)).human(),
            "free_human": Bytes(int(du.free)).human(),
            "used_human": Bytes(int(du.used)).human(),
        }
    except Exception:
        return None
