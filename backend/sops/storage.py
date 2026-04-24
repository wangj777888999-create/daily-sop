import json
import os
from typing import List, Optional
from .models import SOP, ExecutionLog

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data")
SOPS_FILE = os.path.join(DATA_DIR, "sops.json")
LOGS_FILE = os.path.join(DATA_DIR, "execution_logs.json")


def _read_json(path: str):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_all_sops() -> List[SOP]:
    records = _read_json(SOPS_FILE)
    return [SOP(**r) for r in records]


def get_sop(sop_id: str) -> Optional[SOP]:
    sops = get_all_sops()
    for s in sops:
        if s.id == sop_id:
            return s
    return None


def save_sop(sop: SOP) -> SOP:
    sops = get_all_sops()
    for i, existing in enumerate(sops):
        if existing.id == sop.id:
            sops[i] = sop
            _write_json(SOPS_FILE, [s.model_dump(mode="json") for s in sops])
            return sop
    sops.append(sop)
    _write_json(SOPS_FILE, [s.model_dump(mode="json") for s in sops])
    return sop


def delete_sop(sop_id: str) -> bool:
    sops = get_all_sops()
    new_sops = [s for s in sops if s.id != sop_id]
    if len(new_sops) == len(sops):
        return False
    _write_json(SOPS_FILE, [s.model_dump(mode="json") for s in new_sops])
    return True


def get_all_logs() -> List[ExecutionLog]:
    records = _read_json(LOGS_FILE)
    return [ExecutionLog(**r) for r in records]


def save_log(log: ExecutionLog) -> ExecutionLog:
    logs = get_all_logs()
    for i, existing in enumerate(logs):
        if existing.id == log.id:
            logs[i] = log
            _write_json(LOGS_FILE, [l.model_dump(mode="json") for l in logs])
            return log
    logs.append(log)
    _write_json(LOGS_FILE, [l.model_dump(mode="json") for l in logs])
    return log
