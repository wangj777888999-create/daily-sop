import fcntl
import json
import os
from typing import Dict, List, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
ARTIFACTS_DIR = os.path.join(DATA_DIR, "artifacts")


def _ensure_dir():
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)


def _artifact_path(artifact_id: str) -> str:
    return os.path.join(ARTIFACTS_DIR, f"{artifact_id}.json")


def _read_json(path: str) -> Optional[Dict]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        return json.load(f)


def _write_json(path: str, data: Dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def list_artifacts(type: Optional[str] = None) -> List[Dict]:
    _ensure_dir()
    artifacts = []
    for filename in os.listdir(ARTIFACTS_DIR):
        if not filename.endswith(".json"):
            continue
        artifact = _read_json(os.path.join(ARTIFACTS_DIR, filename))
        if artifact is None:
            continue
        if type and artifact.get("type") != type:
            continue
        artifacts.append(artifact)
    artifacts.sort(key=lambda a: a.get("created_at", ""), reverse=True)
    return artifacts


def get_artifact(artifact_id: str) -> Optional[Dict]:
    path = _artifact_path(artifact_id)
    return _read_json(path)


def save_artifact(artifact: Dict) -> Dict:
    _ensure_dir()
    path = _artifact_path(artifact["id"])
    _write_json(path, artifact)
    return artifact


def delete_artifact(artifact_id: str) -> bool:
    path = _artifact_path(artifact_id)
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True
