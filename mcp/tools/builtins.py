from __future__ import annotations

import ast
import os
import platform
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from mcp.tools._sysinfo_common import (
    Bytes,
    basic_machine_info,
    basic_runtime_info,
    boot_time_epoch_seconds,
    invoke_powershell_json,
    supported_os_or_error,
)
from mcp.tools.registry import RegisteredTool

JsonDict = Dict[str, Any]


class CalculatorError(ValueError):
    pass


@dataclass(frozen=True)
class _EvalConfig:
    max_nodes: int = 10_000


def _eval_expr(expr: str, *, cfg: _EvalConfig = _EvalConfig()) -> float:
    expr = (expr or "").strip()
    if not expr:
        raise CalculatorError("Expression is required.")

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise CalculatorError("Invalid expression syntax.") from e

    node_count = 0

    def walk(node: ast.AST) -> float:
        nonlocal node_count
        node_count += 1
        if node_count > cfg.max_nodes:
            raise CalculatorError("Expression is too complex.")

        if isinstance(node, ast.Expression):
            return walk(node.body)

        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)

        if hasattr(ast, "Num") and isinstance(node, ast.Num):  # type: ignore[attr-defined]
            return float(node.n)  # type: ignore[attr-defined]

        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = walk(node.operand)
            return v if isinstance(node.op, ast.UAdd) else -v

        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left = walk(node.left)
            right = walk(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if right == 0:
                raise CalculatorError("Division by zero.")
            return left / right

        raise CalculatorError("Only basic arithmetic is supported: + - * / and parentheses.")

    return walk(tree)


def calculator_run(args: JsonDict) -> JsonDict:
    expr = str(args.get("expression", "")).strip()
    try:
        value = _eval_expr(expr)
        if value.is_integer():
            return {"ok": True, "expression": expr, "result": int(value)}
        return {"ok": True, "expression": expr, "result": value}
    except CalculatorError as e:
        return {"ok": False, "expression": expr, "error": str(e)}


def os_info_run(_: JsonDict) -> JsonDict:
    err = supported_os_or_error()
    if err:
        return err

    uname = platform.uname()
    bt = boot_time_epoch_seconds()

    return {
        "ok": True,
        "os": {
            "system": uname.system,
            "release": uname.release,
            "version": uname.version,
        },
        "kernel": {
            "name": uname.system,
            "release": uname.release,
            "version": uname.version,
        },
        "machine": basic_machine_info(),
        "uptime": (
            {
                "boot_time_epoch_seconds": float(bt),
                "uptime_seconds": float(time.time() - bt),
            }
            if bt is not None
            else {"boot_time_epoch_seconds": None, "uptime_seconds": None}
        ),
        "runtime": basic_runtime_info(),
    }


def _cpu_model() -> Optional[str]:
    sysname_l = platform.system().lower()
    try:
        if sysname_l == "linux":
            with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        _, v = line.split(":", 1)
                        return v.strip() or None
        if sysname_l == "windows":
            v = (platform.processor() or "").strip()
            if v:
                return v
            v = (os.environ.get("PROCESSOR_IDENTIFIER") or "").strip()
            return v or None
    except Exception:
        return None
    v = (platform.processor() or "").strip()
    return v or None


def _physical_cores_linux() -> Optional[int]:
    try:
        physical_id = None
        core_id = None
        pairs: set[tuple[str, str]] = set()
        with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    if physical_id is not None and core_id is not None:
                        pairs.add((physical_id, core_id))
                    physical_id = None
                    core_id = None
                    continue
                if line.lower().startswith("physical id"):
                    _, v = line.split(":", 1)
                    physical_id = v.strip()
                elif line.lower().startswith("core id"):
                    _, v = line.split(":", 1)
                    core_id = v.strip()
        if pairs:
            return len(pairs)
    except Exception:
        return None
    return None


def cpu_info_run(_: JsonDict) -> JsonDict:
    err = supported_os_or_error()
    if err:
        return err

    sysname_l = platform.system().lower()
    logical = os.cpu_count()
    physical: Optional[int] = None
    if sysname_l == "linux":
        physical = _physical_cores_linux()

    return {
        "ok": True,
        "cpu": {
            "model": _cpu_model(),
            "cores_logical": int(logical) if logical is not None else None,
            "cores_physical": int(physical) if physical is not None else None,
            "architecture": platform.machine(),
        },
    }


def _linux_meminfo() -> Dict[str, int]:
    out: Dict[str, int] = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if ":" not in line:
                    continue
                k, rest = line.split(":", 1)
                parts = rest.strip().split()
                if not parts:
                    continue
                if parts[0].isdigit():
                    v = int(parts[0])
                    if len(parts) >= 2 and parts[1].lower() == "kb":
                        v *= 1024
                    out[k.strip()] = v
    except Exception:
        return {}
    return out


def _windows_mem_total_avail_bytes() -> tuple[Optional[int], Optional[int]]:
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)) == 0:
            return None, None
        return int(stat.ullTotalPhys), int(stat.ullAvailPhys)
    except Exception:
        return None, None


def ram_info_run(_: JsonDict) -> JsonDict:
    err = supported_os_or_error()
    if err:
        return err

    sysname_l = platform.system().lower()

    total: Optional[int] = None
    avail: Optional[int] = None

    if sysname_l == "windows":
        total, avail = _windows_mem_total_avail_bytes()
    else:
        mi = _linux_meminfo()
        total = mi.get("MemTotal")
        avail = mi.get("MemAvailable") or mi.get("MemFree")

        if total is None:
            try:
                if hasattr(os, "sysconf"):
                    pages = int(os.sysconf("SC_PHYS_PAGES"))  # type: ignore[arg-type]
                    page_size = int(os.sysconf("SC_PAGE_SIZE"))  # type: ignore[arg-type]
                    total = pages * page_size
            except Exception:
                total = None

    used = (total - avail) if (total is not None and avail is not None) else None

    return {
        "ok": True,
        "ram": {
            "total_bytes": int(total) if total is not None else None,
            "available_bytes": int(avail) if avail is not None else None,
            "used_bytes": int(used) if used is not None else None,
            "total_human": Bytes(int(total)).human() if total is not None else None,
            "available_human": Bytes(int(avail)).human() if avail is not None else None,
            "used_human": Bytes(int(used)).human() if used is not None else None,
        },
    }


def _windows_gpu_list() -> Optional[List[JsonDict]]:
    data = invoke_powershell_json(
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterCompatibility,DriverVersion,DriverDate,VideoProcessor,AdapterRAM,PNPDeviceID | "
        "ConvertTo-Json -Depth 3"
    )
    if data is None:
        return None
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return None

    out: List[JsonDict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "name": item.get("Name"),
                "vendor": item.get("AdapterCompatibility"),
                "driver_version": item.get("DriverVersion"),
                "driver_date": item.get("DriverDate"),
                "video_processor": item.get("VideoProcessor"),
                "vram_bytes": item.get("AdapterRAM"),
                "pnp_device_id": item.get("PNPDeviceID"),
            }
        )
    return out


def _linux_gpu_list() -> Optional[List[JsonDict]]:
    gpus: List[JsonDict] = []

    try:
        nvidia_root = "/proc/driver/nvidia/gpus"
        if os.path.isdir(nvidia_root):
            for gpu_dir in os.listdir(nvidia_root):
                info_path = os.path.join(nvidia_root, gpu_dir, "information")
                if not os.path.isfile(info_path):
                    continue
                info: Dict[str, str] = {}
                with open(info_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if ":" in line:
                            k, v = line.split(":", 1)
                            info[k.strip()] = v.strip()
                gpus.append(
                    {
                        "name": info.get("Model"),
                        "vendor": "NVIDIA",
                        "uuid": info.get("GPU UUID"),
                        "bus": info.get("Bus Location"),
                        "driver": "nvidia",
                    }
                )
    except Exception:
        pass

    if gpus:
        return gpus

    try:
        cp = subprocess.run(
            ["lspci", "-mm"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if cp.returncode == 0:
            for line in (cp.stdout or "").splitlines():
                low = line.lower()
                if ("vga compatible controller" in low) or ("3d controller" in low) or ("display controller" in low):
                    gpus.append({"raw": line.strip()})
    except Exception:
        pass

    return gpus or None


def gpu_info_run(_: JsonDict) -> JsonDict:
    err = supported_os_or_error()
    if err:
        return err

    sysname_l = platform.system().lower()
    adapters = _windows_gpu_list() if sysname_l == "windows" else _linux_gpu_list()

    return {"ok": True, "gpu": {"adapters": adapters or []}}


def _windows_logical_drives() -> List[str]:
    try:
        import ctypes
        import string

        mask = ctypes.windll.kernel32.GetLogicalDrives()
        drives: List[str] = []
        for i, letter in enumerate(string.ascii_uppercase):
            if mask & (1 << i):
                drives.append(f"{letter}:\\")
        return drives
    except Exception:
        return ["C:\\"]


def _disk_usage(path: str) -> Optional[JsonDict]:
    try:
        st = os.statvfs(path) if hasattr(os, "statvfs") else None
        if st is not None:
            total = int(st.f_frsize) * int(st.f_blocks)
            free = int(st.f_frsize) * int(st.f_bavail)
            used = total - free
            return {
                "mount": path,
                "total_bytes": total,
                "free_bytes": free,
                "used_bytes": used,
                "total_human": Bytes(total).human(),
                "free_human": Bytes(free).human(),
                "used_human": Bytes(used).human(),
            }
    except Exception:
        return None
    try:
        import shutil

        du = shutil.disk_usage(path)
        return {
            "mount": path,
            "total_bytes": int(du.total),
            "free_bytes": int(du.free),
            "used_bytes": int(du.used),
            "total_human": Bytes(int(du.total)).human(),
            "free_human": Bytes(int(du.free)).human(),
            "used_human": Bytes(int(du.used)).human(),
        }
    except Exception:
        return None


def _linux_partitions() -> List[JsonDict]:
    parts: List[JsonDict] = []
    seen: set[str] = set()
    try:
        with open("/proc/mounts", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                cols = line.split()
                if len(cols) < 3:
                    continue
                device, mount, fstype = cols[0], cols[1], cols[2]
                if mount in seen:
                    continue
                seen.add(mount)
                du = _disk_usage(mount)
                parts.append(
                    {
                        "device": device,
                        "mount": mount,
                        "fstype": fstype,
                        "usage": du,
                    }
                )
    except Exception:
        pass
    return parts


def _windows_partitions() -> List[JsonDict]:
    parts: List[JsonDict] = []
    for d in _windows_logical_drives():
        parts.append({"mount": d, "usage": _disk_usage(d)})
    return parts


def disk_info_run(args: JsonDict) -> JsonDict:
    err = supported_os_or_error()
    if err:
        return err

    include_partitions = bool(args.get("include_partitions", True))
    sysname_l = platform.system().lower()

    root = "C:\\" if sysname_l == "windows" else "/"
    root_usage = _disk_usage(root)

    partitions: List[JsonDict] = []
    if include_partitions:
        partitions = _windows_partitions() if sysname_l == "windows" else _linux_partitions()

    return {
        "ok": True,
        "disk": {
            "root": root,
            "root_usage": root_usage,
            "partitions": partitions,
        },
    }


def system_info_run(args: JsonDict) -> JsonDict:
    sysname = platform.system()
    sysname_l = sysname.lower()
    if sysname_l not in {"windows", "linux"}:
        return {
            "ok": False,
            "error": f"Unsupported OS: {sysname}. Only Windows and Linux are supported.",
        }

    include_partitions = bool(args.get("include_partitions", True))

    osi = os_info_run({})
    cpui = cpu_info_run({})
    rami = ram_info_run({})
    gpui = gpu_info_run({})
    diski = disk_info_run({"include_partitions": include_partitions})

    if not all(x.get("ok") for x in [osi, cpui, rami, gpui, diski] if isinstance(x, dict)):
        return {"ok": False, "error": "Failed to collect full system info."}

    return {
        "ok": True,
        "os_family": sysname,
        **{k: v for k, v in osi.items() if k not in {"ok"}},
        **{k: v for k, v in cpui.items() if k not in {"ok"}},
        **{k: v for k, v in rami.items() if k not in {"ok"}},
        **{k: v for k, v in gpui.items() if k not in {"ok"}},
        **{k: v for k, v in diski.items() if k not in {"ok"}},
    }


def register_all(register: Callable[[RegisteredTool], None]) -> None:
    tools = [
        RegisteredTool(
            name="calculator",
            description="Evaluate a basic arithmetic expression (+ - * /, parentheses).",
            args_schema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Arithmetic expression, e.g. '1 + 2 * (3 - 4)'.",
                    }
                },
                "required": ["expression"],
            },
            handler=calculator_run,
        ),
        RegisteredTool(
            name="os_info",
            description="Get OS/kernel/runtime info (Windows/Linux only).",
            args_schema={"type": "object", "properties": {}, "required": []},
            handler=os_info_run,
        ),
        RegisteredTool(
            name="cpu_info",
            description="Get CPU model and core counts (Windows/Linux only).",
            args_schema={"type": "object", "properties": {}, "required": []},
            handler=cpu_info_run,
        ),
        RegisteredTool(
            name="ram_info",
            description="Get RAM totals (and available when possible) (Windows/Linux only).",
            args_schema={"type": "object", "properties": {}, "required": []},
            handler=ram_info_run,
        ),
        RegisteredTool(
            name="gpu_info",
            description="Get GPU adapter information (best-effort) (Windows/Linux only).",
            args_schema={"type": "object", "properties": {}, "required": []},
            handler=gpu_info_run,
        ),
        RegisteredTool(
            name="disk_info",
            description="Get disk usage and partitions/mounts (Windows/Linux only).",
            args_schema={
                "type": "object",
                "properties": {
                    "include_partitions": {
                        "type": "boolean",
                        "description": "Include partitions/mounts list (default: true).",
                        "default": True,
                    }
                },
                "required": [],
            },
            handler=disk_info_run,
        ),
        RegisteredTool(
            name="system_info",
            description="Get OS/CPU/RAM/GPU/Disk info (Windows/Linux only).",
            args_schema={
                "type": "object",
                "properties": {
                    "include_partitions": {
                        "type": "boolean",
                        "description": "Include partitions/mounts list (default: true).",
                        "default": True,
                    }
                },
                "required": [],
            },
            handler=system_info_run,
        ),
    ]
    for t in tools:
        register(t)
