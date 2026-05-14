"""
yolo_training_routes.py
YOLO 训练数据收集与导出路由

工作流：
  验证工具识别失败 → 用户标注正确框 → 保存样本
  → 积累一批后点「导出数据集」→ 得到 YOLO 格式 zip → 本地运行 yolo train
"""
import io
import json
import zipfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse

router = APIRouter()

TRAINING_DIR = Path("../data/training_samples")
TRAINING_DIR.mkdir(parents=True, exist_ok=True)

# YOLO 类别文件内容（person = class 0）
CLASSES_YAML = """\
path: ./
train: images/train
val: images/val

names:
  0: person
"""


# ──────────────────── 保存训练样本 ────────────────────

@router.post("/tools/yolo-training/save-sample")
async def save_sample(
    photo: UploadFile = File(...),
    boxes_json: str = Form(...),
    img_width: int = Form(...),
    img_height: int = Form(...),
    note: Optional[str] = Form(None),
):
    """
    保存一张图片及其标注框为 YOLO 训练样本。

    boxes_json: [{"x1":..,"y1":..,"x2":..,"y2":..}, ...]
      坐标为像素值（已过滤后的有效框，可由用户在前端增删）

    存储结构：
      data/training_samples/
        images/  ← 原始照片
        labels/  ← YOLO 格式 .txt（每行：0 cx cy w h，均归一化）
        meta.jsonl ← 样本元数据追加日志
    """
    images_dir = TRAINING_DIR / "images"
    labels_dir = TRAINING_DIR / "labels"
    images_dir.mkdir(exist_ok=True)
    labels_dir.mkdir(exist_ok=True)

    try:
        boxes = json.loads(boxes_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="boxes_json 格式错误")

    # 生成唯一文件名（时间戳 + 原始名）
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
    stem = Path(photo.filename or "photo").stem[:40]
    safe_stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)
    filename = f"{ts}_{safe_stem}"

    # 保存图片
    content = await photo.read()
    img_path = images_dir / f"{filename}.jpg"
    img_path.write_bytes(content)

    # 生成 YOLO 标注文件
    label_lines = []
    for b in boxes:
        cx = ((b["x1"] + b["x2"]) / 2) / img_width
        cy = ((b["y1"] + b["y2"]) / 2) / img_height
        w = (b["x2"] - b["x1"]) / img_width
        h = (b["y2"] - b["y1"]) / img_height
        # 裁剪到 [0,1]
        cx = max(0.0, min(1.0, cx))
        cy = max(0.0, min(1.0, cy))
        w = max(0.001, min(1.0, w))
        h = max(0.001, min(1.0, h))
        label_lines.append(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

    label_path = labels_dir / f"{filename}.txt"
    label_path.write_text("\n".join(label_lines), encoding="utf-8")

    # 追加元数据
    meta = {
        "filename": filename,
        "original_name": photo.filename,
        "person_count": len(boxes),
        "img_width": img_width,
        "img_height": img_height,
        "note": note,
        "saved_at": datetime.now().isoformat(),
    }
    with open(TRAINING_DIR / "meta.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(meta, ensure_ascii=False) + "\n")

    return {"success": True, "filename": filename, "person_count": len(boxes)}


# ──────────────────── 从 URL 保存训练样本 ────────────────────

_URL_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_URL_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AI-Analyst-Bot/1.0)"}


@router.post("/tools/yolo-training/save-sample-from-url")
async def save_sample_from_url(body: dict):
    """
    从远程 URL 下载图片，连同标注框一起保存为训练样本。

    body: {
      "url": "https://...",
      "boxes": [{"x1":..,"y1":..,"x2":..,"y2":..}, ...],
      "img_width": int,
      "img_height": int,
      "note": str | null
    }
    """
    url: str = body.get("url", "")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="无效 URL")

    boxes = body.get("boxes", [])
    img_width = int(body.get("img_width") or 640)
    img_height = int(body.get("img_height") or 640)
    note = body.get("note")

    # 下载图片
    try:
        async with httpx.AsyncClient(timeout=_URL_TIMEOUT, headers=_URL_HEADERS, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.content
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"下载失败 HTTP {e.response.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="下载超时（30s）")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"下载失败：{e}")

    images_dir = TRAINING_DIR / "images"
    labels_dir = TRAINING_DIR / "labels"
    images_dir.mkdir(exist_ok=True)
    labels_dir.mkdir(exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
    stem = url.rsplit("/", 1)[-1].split("?")[0]
    stem = Path(stem).stem[:40]
    safe_stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)
    filename = f"{ts}_{safe_stem}"

    (images_dir / f"{filename}.jpg").write_bytes(content)

    label_lines = []
    for b in boxes:
        cx = ((b["x1"] + b["x2"]) / 2) / img_width
        cy = ((b["y1"] + b["y2"]) / 2) / img_height
        w = (b["x2"] - b["x1"]) / img_width
        h = (b["y2"] - b["y1"]) / img_height
        cx = max(0.0, min(1.0, cx))
        cy = max(0.0, min(1.0, cy))
        w = max(0.001, min(1.0, w))
        h = max(0.001, min(1.0, h))
        label_lines.append(f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

    (labels_dir / f"{filename}.txt").write_text("\n".join(label_lines), encoding="utf-8")

    meta = {
        "filename": filename,
        "original_name": url.rsplit("/", 1)[-1],
        "source_url": url,
        "person_count": len(boxes),
        "img_width": img_width,
        "img_height": img_height,
        "note": note,
        "saved_at": datetime.now().isoformat(),
    }
    with open(TRAINING_DIR / "meta.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(meta, ensure_ascii=False) + "\n")

    return {"success": True, "filename": filename, "person_count": len(boxes)}


# ──────────────────── 查询已保存样本 ────────────────────

@router.get("/tools/yolo-training/samples")
async def list_samples():
    """列出所有已保存的训练样本摘要。"""
    meta_file = TRAINING_DIR / "meta.jsonl"
    if not meta_file.exists():
        return {"count": 0, "samples": []}

    samples = []
    with open(meta_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    samples.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    return {"count": len(samples), "samples": samples}


# ──────────────────── 删除样本 ────────────────────

@router.delete("/tools/yolo-training/samples/{filename}")
async def delete_sample(filename: str):
    """删除一条训练样本（图片 + 标注 + 元数据中的记录）。"""
    # 安全校验：不允许路径穿越
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法文件名")

    deleted = []
    for ext in (".jpg", ".jpeg", ".png"):
        p = TRAINING_DIR / "images" / f"{filename}{ext}"
        if p.exists():
            p.unlink()
            deleted.append(str(p))
    lp = TRAINING_DIR / "labels" / f"{filename}.txt"
    if lp.exists():
        lp.unlink()
        deleted.append(str(lp))

    # 重写 meta.jsonl，跳过该条记录
    meta_file = TRAINING_DIR / "meta.jsonl"
    if meta_file.exists():
        lines = meta_file.read_text(encoding="utf-8").splitlines()
        kept = []
        for line in lines:
            try:
                obj = json.loads(line)
                if obj.get("filename") != filename:
                    kept.append(line)
            except json.JSONDecodeError:
                kept.append(line)
        meta_file.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")

    return {"deleted": deleted}


# ──────────────────── 导出 YOLO 格式数据集 ────────────────────

@router.get("/tools/yolo-training/export-dataset")
async def export_dataset(val_ratio: float = Query(0.2, ge=0.0, le=0.5)):
    """
    将所有训练样本打包为标准 YOLO 数据集 zip，可直接传给 `yolo train`。

    zip 结构：
      dataset/
        data.yaml
        images/train/*.jpg
        images/val/*.jpg
        labels/train/*.txt
        labels/val/*.txt
    """
    images_dir = TRAINING_DIR / "images"
    labels_dir = TRAINING_DIR / "labels"

    img_files = sorted(images_dir.glob("*.jpg")) + sorted(images_dir.glob("*.jpeg")) + sorted(images_dir.glob("*.png"))
    if not img_files:
        raise HTTPException(status_code=404, detail="暂无训练样本，请先保存至少一张")

    # 按 val_ratio 切分 train / val（按文件名排序后取尾部）
    n_val = max(1, int(len(img_files) * val_ratio)) if len(img_files) > 1 else 0
    train_imgs = img_files[n_val:]
    val_imgs = img_files[:n_val]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("dataset/data.yaml", CLASSES_YAML)

        for split, imgs in [("train", train_imgs), ("val", val_imgs)]:
            for img_path in imgs:
                zf.write(img_path, f"dataset/images/{split}/{img_path.name}")
                lbl_path = labels_dir / (img_path.stem + ".txt")
                if lbl_path.exists():
                    zf.write(lbl_path, f"dataset/labels/{split}/{lbl_path.name}")
                else:
                    # 没有标注的图片写空文件（YOLO 允许）
                    zf.writestr(f"dataset/labels/{split}/{img_path.stem}.txt", "")

        # 附带训练命令说明
        readme = f"""\
# YOLO 微调数据集

样本总数: {len(img_files)} 张
训练集: {len(train_imgs)} 张 | 验证集: {len(val_imgs)} 张
类别: person (class 0)

## 训练命令

```bash
# 安装依赖
pip install ultralytics

# 从 yolov8n 微调（推荐起点）
yolo train \\
  model=yolov8n.pt \\
  data=dataset/data.yaml \\
  epochs=50 \\
  imgsz=640 \\
  batch=8 \\
  patience=10 \\
  project=runs/person_finetune \\
  name=exp1

# 训练完成后，将最佳权重复制到后端
cp runs/person_finetune/exp1/weights/best.pt backend/yolov8n.pt
```

## 参数说明

| 参数 | 建议值 | 说明 |
|------|--------|------|
| epochs | 30~100 | 样本少时用 30，多时可到 100 |
| imgsz | 640 | 与推理保持一致；低质照片可试 960 |
| batch | 4~16 | 取决于显存，CPU 训练用 4 |
| patience | 10 | 早停轮数，防过拟合 |

> 训练后把 best.pt 替换 backend/yolov8n.pt，重启后端即可生效。
"""
        zf.writestr("dataset/README.md", readme)

    buf.seek(0)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=yolo_dataset_{ts}.zip"},
    )
