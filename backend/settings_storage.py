import json
import os
from typing import Dict, Any

try:
    import fcntl
except ImportError:
    fcntl = None

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")


def _read_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_SH)
        return json.load(f)


def _write_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_settings() -> Dict[str, Any]:
    """读取系统配置"""
    return _read_json(SETTINGS_FILE)


def save_settings(data: Dict[str, Any]) -> None:
    """保存系统配置（合并写入，不覆盖其他字段）"""
    current = load_settings()
    current.update(data)
    _write_json(SETTINGS_FILE, current)
