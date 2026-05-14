"""
photo_checkin.py
照片人数识别核心模块：YOLO 推理 + 过滤 + 标注图生成 + 月度核对表解析
"""
import io
import base64
import logging
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# ──────────────────── 默认过滤参数 ────────────────────

DEFAULT_FILTER_CONFIG = {
    "conf_threshold": 0.45,
    "min_bbox_ratio": 0.008,
    "edge_margin_pct": 0.05,
    # NMS IoU 阈值：越低越能保留相邻/堆叠的人（ultralytics 默认 0.7）
    # 人群密集场景建议 0.3～0.4；稀疏场景可用 0.6～0.7
    "iou_threshold": 0.45,
    # 推理分辨率（像素）：越高对模糊/远景越准，但速度变慢
    # 默认 640；低质照片可尝试 960 或 1280
    "imgsz": 640,
}

# ──────────────────── 模型懒加载 ────────────────────

_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from ultralytics import YOLO
            _model = YOLO("yolov8n.pt")
            logger.info("YOLOv8n model loaded successfully")
        except ImportError:
            raise RuntimeError(
                "ultralytics 未安装，请运行: pip install ultralytics"
            )
    return _model


# ──────────────────── 核心推理函数 ────────────────────

def detect_persons(
    image_bytes: bytes,
    filename: str,
    filter_config: Optional[Dict] = None,
    include_rejected: bool = False,
) -> Dict[str, Any]:
    """
    对单张图片进行人体检测。

    Returns:
        {
            "detected_count": int,
            "raw_count": int,
            "confidence_avg": float,
            "annotated_image_b64": str,
            "boxes": [...],
            "rejected_boxes": [...],   # 仅 include_rejected=True 时返回
            "filter_config": dict,
        }
    """
    from PIL import Image, ImageDraw

    cfg = {**DEFAULT_FILTER_CONFIG, **(filter_config or {})}

    # 1. 解码图片
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_w, img_h = img.size
    img_area = img_w * img_h

    # 2. YOLO 推理（仅 person 类）
    model = _get_model()
    results = model(
        img,
        classes=[0],
        verbose=False,
        iou=float(cfg.get("iou_threshold", 0.45)),
        imgsz=int(cfg.get("imgsz", 640)),
    )
    detections = results[0].boxes

    # 3. 解析检测框
    raw_boxes = []
    if detections is not None and len(detections) > 0:
        for box in detections:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            raw_boxes.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "conf": conf})

    raw_count = len(raw_boxes)

    # 4. 应用过滤规则
    valid_boxes = []
    rejected_boxes = []
    for b in raw_boxes:
        if b["conf"] < cfg["conf_threshold"]:
            if include_rejected:
                rejected_boxes.append({
                    **b,
                    "rejected_reason": f"置信度 {b['conf']:.3f} < 阈值 {cfg['conf_threshold']}",
                })
            continue
        bbox_area = (b["x2"] - b["x1"]) * (b["y2"] - b["y1"])
        area_ratio = bbox_area / img_area
        if area_ratio < cfg["min_bbox_ratio"]:
            if include_rejected:
                rejected_boxes.append({
                    **b,
                    "rejected_reason": f"框太小 (面积比 {area_ratio:.4f} < {cfg['min_bbox_ratio']})",
                })
            continue
        cx = (b["x1"] + b["x2"]) / 2
        cy = (b["y1"] + b["y2"]) / 2
        edge_y = img_h * cfg["edge_margin_pct"]
        b["edge_flag"] = cy < edge_y or cy > (img_h - edge_y)
        valid_boxes.append(b)

    detected_count = len(valid_boxes)
    confidence_avg = (
        sum(b["conf"] for b in valid_boxes) / detected_count
        if detected_count > 0 else 0.0
    )

    # 5. 生成标注图（有效框橙/黄，被拒绝框灰色）
    annotated_img = img.copy()
    draw = ImageDraw.Draw(annotated_img)

    if include_rejected:
        for b in rejected_boxes:
            draw.rectangle([b["x1"], b["y1"], b["x2"], b["y2"]], outline="#AAAAAA", width=2)

    for b in valid_boxes:
        color = "#FF6B35" if not b.get("edge_flag") else "#FFC300"
        draw.rectangle([b["x1"], b["y1"], b["x2"], b["y2"]], outline=color, width=3)

    # 左上角叠加计数文字
    draw.rectangle([0, 0, 160, 40], fill=(0, 0, 0))
    draw.text((10, 10), f"识别人数: {detected_count}", fill="white")

    # 转 Base64
    buf = io.BytesIO()
    annotated_img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    result: Dict[str, Any] = {
        "detected_count": detected_count,
        "raw_count": raw_count,
        "confidence_avg": round(confidence_avg, 3),
        "annotated_image_b64": b64,
        "boxes": [
            {
                "conf": round(b["conf"], 3),
                "edge_flag": b.get("edge_flag", False),
                "x1": round(b["x1"], 1), "y1": round(b["y1"], 1),
                "x2": round(b["x2"], 1), "y2": round(b["y2"], 1),
            }
            for b in valid_boxes
        ],
        "filter_config": cfg,
    }
    if include_rejected:
        result["rejected_boxes"] = [
            {
                "conf": round(b["conf"], 3),
                "rejected_reason": b["rejected_reason"],
                "x1": round(b["x1"], 1), "y1": round(b["y1"], 1),
                "x2": round(b["x2"], 1), "y2": round(b["y2"], 1),
            }
            for b in rejected_boxes
        ]
    return result


def detect_multiple(
    images: List[Tuple[str, bytes]],
    filter_config: Optional[Dict] = None,
    include_rejected: bool = False,
) -> List[Dict[str, Any]]:
    """批量处理多张图片，返回列表。"""
    results = []
    for filename, image_bytes in images:
        try:
            result = detect_persons(image_bytes, filename, filter_config, include_rejected=include_rejected)
            result["filename"] = filename
            result["error"] = None
        except Exception as e:
            logger.error(f"detect_persons failed for {filename}: {e}")
            result = {
                "filename": filename,
                "detected_count": 0,
                "raw_count": 0,
                "confidence_avg": 0.0,
                "annotated_image_b64": None,
                "boxes": [],
                "filter_config": filter_config or DEFAULT_FILTER_CONFIG,
                "error": str(e),
            }
        results.append(result)
    return results


# ──────────────────── 月度核对表解析 ────────────────────

# 列名模糊匹配表：字段名 → 可能的中文列名列表（按优先级排序）
_COLUMN_ALIASES: Dict[str, List[str]] = {
    "date":           ["课程日期", "上课日期", "日期", "date"],
    "campus":         ["校区", "学校", "学校名称", "campus"],
    "coach":          ["教练", "教练员", "教练姓名", "coach"],
    "course_name":    ["课程名称", "课程", "course_name"],
    "attended_count": ["实到人数", "到课人数", "已到人数", "实际人数",
                       "上课人次", "实际上课人次", "已到", "actual_count"],
    "expected_count": ["应到人数", "总应到人数", "应到", "expected_count"],
}


def _match_column(df_columns: List[str], aliases: List[str]) -> Optional[str]:
    """在 df 列名中找到第一个匹配 alias 的列名（忽略大小写和前后空格）。"""
    normalized = {c.strip().lower(): c for c in df_columns}
    for alias in aliases:
        if alias.strip().lower() in normalized:
            return normalized[alias.strip().lower()]
    return None


def parse_sessions_from_excel(excel_bytes: bytes) -> List[Dict[str, Any]]:
    """
    解析月度核对表 Excel，返回结构化课程行列表。

    支持任意列名，通过 _COLUMN_ALIASES 模糊匹配。
    必须包含 attended_count；其余字段缺失时填 None。

    Returns:
        [
          {
            "row_index": int,        # 原始行号（从 0 开始），用于前端关联
            "date": str | None,
            "campus": str | None,
            "coach": str | None,
            "course_name": str | None,
            "attended_count": int,
            "expected_count": int | None,
          }, ...
        ]
    """
    try:
        xls = pd.ExcelFile(io.BytesIO(excel_bytes))
        df = pd.read_excel(io.BytesIO(excel_bytes), sheet_name=xls.sheet_names[0])
    except Exception as e:
        raise ValueError(f"Excel 读取失败：{e}")

    df.columns = [str(c).strip() for c in df.columns]
    col_map = {
        field: _match_column(list(df.columns), aliases)
        for field, aliases in _COLUMN_ALIASES.items()
    }

    if col_map["attended_count"] is None:
        raise ValueError(
            f"核对表中未找到「实到人数」列，请确保表头包含以下任一列名：{_COLUMN_ALIASES['attended_count']}"
        )

    sessions = []
    for i, row in df.iterrows():
        def _get(field: str):
            col = col_map.get(field)
            if col is None:
                return None
            val = row.get(col)
            if pd.isna(val):
                return None
            return val

        attended_raw = _get("attended_count")
        if attended_raw is None:
            continue  # 跳过空行

        try:
            attended = int(attended_raw)
        except (ValueError, TypeError):
            continue

        expected_raw = _get("expected_count")
        expected = None
        if expected_raw is not None:
            try:
                expected = int(expected_raw)
            except (ValueError, TypeError):
                pass

        date_val = _get("date")
        sessions.append({
            "row_index": int(i),
            "date":           str(date_val)[:10] if date_val is not None else None,
            "campus":         str(_get("campus")) if _get("campus") is not None else None,
            "coach":          str(_get("coach")) if _get("coach") is not None else None,
            "course_name":    str(_get("course_name")) if _get("course_name") is not None else None,
            "attended_count": attended,
            "expected_count": expected,
        })

    return sessions
