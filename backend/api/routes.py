# backend/api/routes.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid
import os
import shutil
import json

from sops.storage import get_all_sops, get_sop, save_sop, delete_sop, get_all_logs, save_log
from sops.code_parser import ParserCodeToSOP
from sops.code_generator import SOPToExecutableCode
from sops.sandbox import SandboxExecutor
from sops.models import SOP, Step, ExecutionLog

router = APIRouter()

# 安全配置
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# 数据目录
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ==================== 响应模型 ====================

class ExecutionResponse(BaseModel):
    execution_id: str
    status: str


class ExecutionStatusResponse(BaseModel):
    execution_id: str
    sop_id: str
    status: str
    input_files: List[str]
    output_file: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class FileUploadResponse(BaseModel):
    id: str
    filename: str
    path: str
    size: int


class FileInfoResponse(BaseModel):
    id: str
    filename: str
    path: str
    size: int

# ==================== SOP 管理路由 ====================

from fastapi import Body

@router.post("/sops/parse", response_model=dict)
async def parse_code(body: dict = Body(...)):
    """解析 Python 代码为 SOP"""
    code = body.get("code", "")
    sop_dict = ParserCodeToSOP(code)
    return sop_dict


@router.get("/sops", response_model=List[dict])
async def get_sops():
    """获取所有 SOP 列表"""
    sops = get_all_sops()
    return [s.model_dump(mode="json") for s in sops]


@router.get("/sops/{sop_id}", response_model=dict)
async def get_sop_by_id(sop_id: str):
    """获取指定 SOP"""
    sop = get_sop(sop_id)
    if not sop:
        raise HTTPException(status_code=404, detail="SOP not found")
    return sop.model_dump(mode="json")


@router.post("/sops", response_model=dict)
async def create_sop(
    name: str = Form(...),
    description: str = Form(""),
    code: Optional[str] = Form(None),
    steps: Optional[str] = Form(None)
):
    """创建新 SOP

    支持两种方式:
    1. 通过 code (Python 代码) 自动解析生成 SOP
    2. 通过 steps (JSON 格式的步骤数组) 直接创建 SOP
    """
    sop_id = str(uuid.uuid4())
    now = datetime.now()

    if code:
        # 通过代码解析生成 SOP
        sop_dict = ParserCodeToSOP(code)
        sop = SOP(
            id=sop_id,
            name=sop_dict.get("name", name),
            description=sop_dict.get("description", description),
            steps=[Step(**s) for s in sop_dict.get("steps", [])],
            created_at=now,
            updated_at=now
        )
    elif steps:
        # 通过步骤 JSON 创建 SOP
        try:
            steps_list = json.loads(steps)
            sop = SOP(
                id=sop_id,
                name=name,
                description=description,
                steps=[Step(**s) for s in steps_list],
                created_at=now,
                updated_at=now
            )
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid steps JSON format")
    else:
        raise HTTPException(status_code=400, detail="Either 'code' or 'steps' must be provided")

    save_sop(sop)
    return sop.model_dump(mode="json")


@router.put("/sops/{sop_id}", response_model=dict)
async def update_sop(
    sop_id: str,
    name: str = Form(...),
    description: str = Form(""),
    steps: str = Form(...)
):
    """更新 SOP"""
    existing_sop = get_sop(sop_id)
    if not existing_sop:
        raise HTTPException(status_code=404, detail="SOP not found")

    try:
        steps_list = json.loads(steps)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid steps JSON format")

    now = datetime.now()
    sop = SOP(
        id=sop_id,
        name=name,
        description=description,
        steps=[Step(**s) for s in steps_list],
        created_at=existing_sop.created_at,
        updated_at=now
    )
    save_sop(sop)
    return sop.model_dump(mode="json")


@router.delete("/sops/{sop_id}")
async def delete_sop_by_id(sop_id: str):
    """删除 SOP"""
    success = delete_sop(sop_id)
    if not success:
        raise HTTPException(status_code=404, detail="SOP not found")
    return {"message": "SOP deleted successfully"}


# ==================== 执行路由 ====================

@router.post("/execute/{sop_id}", response_model=ExecutionResponse)
async def execute_sop(sop_id: str, files: List[UploadFile] = File(...)):
    """执行 SOP

    接收上传的文件，执行 SOP，返回 execution_id
    """
    # 获取 SOP
    sop = get_sop(sop_id)
    if not sop:
        raise HTTPException(status_code=404, detail="SOP not found")

    # 保存上传的文件（同步执行，非异步）
    input_files = []
    for file in files:
        # 验证文件大小
        file.file.seek(0, 2)  # Seek to end
        size = file.file.tell()
        file.file.seek(0)  # Reset to start
        if size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File size {size} exceeds maximum allowed size {MAX_FILE_SIZE}"
            )

        # 使用 os.path.basename() 防止路径遍历攻击
        safe_filename = os.path.basename(file.filename)
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        input_files.append(file_path)

    # 创建执行记录
    exec_id = str(uuid.uuid4())
    now = datetime.now()
    log = ExecutionLog(
        id=exec_id,
        sop_id=sop_id,
        status="pending",
        input_files=input_files,
        created_at=now
    )
    save_log(log)

    # 生成可执行代码
    sop_dict = sop.model_dump(mode="json")
    code = SOPToExecutableCode(sop_dict)

    # 同步执行代码（当前请求会阻塞等待执行完成）
    try:
        # 更新状态为 running
        log.status = "running"
        save_log(log)

        # 执行代码
        executor = SandboxExecutor(timeout=60)
        result = executor.execute(code)

        if result["success"]:
            log.status = "success"
            log.completed_at = datetime.now()
            # 捕获输出文件路径
            log.output_file = result.get("output_file")
        else:
            log.status = "failed"
            log.error_message = result.get("error", "Unknown error")
            log.completed_at = datetime.now()

        save_log(log)
    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)
        log.completed_at = datetime.now()
        save_log(log)

    return {
        "execution_id": exec_id,
        "status": log.status
    }


@router.get("/execute/{exec_id}/status", response_model=ExecutionStatusResponse)
async def get_execution_status(exec_id: str):
    """获取执行状态"""
    logs = get_all_logs()
    for log in logs:
        if log.id == exec_id:
            return ExecutionStatusResponse(
                execution_id=log.id,
                sop_id=log.sop_id,
                status=log.status,
                input_files=log.input_files,
                output_file=log.output_file,
                error_message=log.error_message,
                created_at=log.created_at.isoformat() if log.created_at else None,
                completed_at=log.completed_at.isoformat() if log.completed_at else None
            )
    raise HTTPException(status_code=404, detail="Execution not found")


@router.get("/execute/{exec_id}/download")
async def download_execution_result(exec_id: str):
    """下载执行结果文件"""
    logs = get_all_logs()
    for log in logs:
        if log.id == exec_id:
            if log.status != "success" or not log.output_file:
                raise HTTPException(status_code=404, detail="Result file not found")
            if not os.path.exists(log.output_file):
                raise HTTPException(status_code=404, detail="Result file not found")
            return FileResponse(
                log.output_file,
                media_type="application/octet-stream",
                filename=os.path.basename(log.output_file)
            )
    raise HTTPException(status_code=404, detail="Execution not found")


# ==================== 文件路由 ====================

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """上传 Excel/CSV 文件"""
    # 验证文件类型
    allowed_extensions = {".xlsx", ".xls", ".csv"}
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()

    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
        )

    # 验证文件大小
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset to start
    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File size {size} exceeds maximum allowed size {MAX_FILE_SIZE}"
        )

    # 保存文件
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return FileUploadResponse(
        id=file_id,
        filename=filename,
        path=file_path,
        size=os.path.getsize(file_path)
    )


@router.get("/files/{file_id}", response_model=FileInfoResponse)
async def get_file_info(file_id: str):
    """获取文件信息"""
    # 查找文件
    for filename in os.listdir(UPLOAD_DIR):
        if filename.startswith(file_id):
            file_path = os.path.join(UPLOAD_DIR, filename)
            return FileInfoResponse(
                id=file_id,
                filename=filename[len(file_id)+1:] if len(filename) > len(file_id)+1 else filename,
                path=file_path,
                size=os.path.getsize(file_path)
            )
    raise HTTPException(status_code=404, detail="File not found")
