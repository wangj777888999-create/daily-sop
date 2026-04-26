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
from sops.code_parser import ParserCodeToSOP, parse_code_with_sources
from sops.code_generator import SOPToExecutableCode
from sops.sandbox import SandboxExecutor
from sops.models import SOP, Step, ExecutionLog, DataSource

router = APIRouter()

# 安全配置
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# 数据目录
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ==================== 辅助函数 ====================

def _convert_steps_format(steps_data: list) -> List[Step]:
    """转换步骤格式：前端格式 -> 后端格式

    前端格式: {id, order, action, params, description, code}
    后端格式: {step, action, params, description}
    """
    converted_steps = []
    for s in steps_data:
        if 'step' in s and 'action' in s and 'params' in s:
            # 已经是后端格式
            converted_steps.append(Step(**s))
        elif 'order' in s:
            # 前端格式，需要转换
            action = s.get('action', '')
            params = s.get('params', {})

            # 如果 action 为空，尝试从 description 解析（旧格式兼容）
            if not action:
                desc = s.get('description', '')
                if ':' in desc:
                    action = desc.split(':', 1)[0].strip()
                    try:
                        params = json.loads(desc.split(':', 1)[1].strip())
                    except:
                        params = {}

            converted_steps.append(Step(
                step=s.get('order', 1),
                action=action,
                params=params,
                description=s.get('description', '')
            ))
    return converted_steps


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

@router.post("/sops/generate", response_model=dict)
async def generate_sop_from_description(body: dict = Body(...)):
    """B3: 从自然语言描述生成 SOP（按行拆分为步骤）"""
    description = body.get("description", "")
    lines = [l.strip() for l in description.split('\n') if l.strip()]
    steps = [
        {
            "id": f"step-{i+1}",
            "order": i + 1,
            "action": "",
            "params": {},
            "description": line,
            "code": ""
        }
        for i, line in enumerate(lines)
    ]
    return {
        "name": lines[0][:50] if lines else "新 SOP",
        "description": description,
        "steps": steps
    }


@router.post("/sops/parse", response_model=dict)
async def parse_code(body: dict = Body(...)):
    """解析 Python 代码为 SOP（包含数据源信息）"""
    code = body.get("code", "")
    result = parse_code_with_sources(code)  # 使用新函数
    return result


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
async def create_sop(body: dict = Body(...)):
    """创建新 SOP (统一 JSON 格式)

    兼容两种模式:
    1. 通过 code (Python 代码) 自动解析生成 SOP
    2. 通过 steps (步骤数组) 直接创建 SOP
    """
    sop_id = str(uuid.uuid4())
    now = datetime.now()

    name = body.get("name", "未命名 SOP")
    description = body.get("description", "")
    code = body.get("code")
    steps_data = body.get("steps")
    tags = body.get("tags", [])

    if code:
        # 通过代码解析生成 SOP
        sop_dict = parse_code_with_sources(code)  # 使用新函数获取 dataSources
        data_sources = sop_dict.get("dataSources", [])
        if data_sources:
            sop = SOP(
                id=sop_id,
                name=sop_dict.get("name", name),
                description=sop_dict.get("description", description),
                steps=[Step(**s) for s in sop_dict.get("steps", [])],
                dataSources=[DataSource(**ds) for ds in data_sources],
                tags=tags,
                created_at=now,
                updated_at=now
            )
        else:
            sop = SOP(
                id=sop_id,
                name=sop_dict.get("name", name),
                description=sop_dict.get("description", description),
                steps=[Step(**s) for s in sop_dict.get("steps", [])],
                tags=tags,
                created_at=now,
                updated_at=now
            )
    elif steps_data:
        # 通过步骤 JSON 创建 SOP (支持前端格式转换)
        converted_steps = _convert_steps_format(steps_data)

        # 处理 dataSources
        data_sources_data = body.get("dataSources", [])
        if data_sources_data:
            data_sources = [DataSource(**ds) for ds in data_sources_data]
        else:
            data_sources = []

        sop = SOP(
            id=sop_id,
            name=name,
            description=description,
            steps=converted_steps,
            dataSources=data_sources,
            tags=tags,
            created_at=now,
            updated_at=now
        )
    else:
        raise HTTPException(status_code=400, detail="Either 'code' or 'steps' must be provided")

    save_sop(sop)
    return sop.model_dump(mode="json")


@router.put("/sops/{sop_id}", response_model=dict)
async def update_sop(sop_id: str, body: dict = Body(...)):
    """更新 SOP"""
    existing_sop = get_sop(sop_id)
    if not existing_sop:
        raise HTTPException(status_code=404, detail="SOP not found")

    name = body.get("name", existing_sop.name)
    description = body.get("description", existing_sop.description)
    steps_data = body.get("steps")
    tags = body.get("tags", existing_sop.tags)

    if steps_data is None:
        raise HTTPException(status_code=400, detail="steps is required")

    converted_steps = _convert_steps_format(steps_data)

    now = datetime.now()
    sop = SOP(
        id=sop_id,
        name=name,
        description=description,
        steps=converted_steps,
        tags=tags,
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
    sop = get_sop(sop_id)
    if not sop:
        raise HTTPException(status_code=404, detail="SOP not found")

    # B4: 先生成 exec_id，为每次执行创建独立目录，避免同名文件覆盖
    exec_id = str(uuid.uuid4())
    exec_dir = os.path.join(UPLOAD_DIR, exec_id)
    os.makedirs(exec_dir, exist_ok=True)

    input_files = []
    filename_mapping = {}
    for file in files:
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)
        if size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File size {size} exceeds maximum allowed size {MAX_FILE_SIZE}"
            )

        safe_filename = os.path.basename(file.filename)
        file_path = os.path.join(exec_dir, safe_filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        input_files.append(file_path)
        filename_mapping[safe_filename] = file_path

    now = datetime.now()
    log = ExecutionLog(
        id=exec_id,
        sop_id=sop_id,
        status="pending",
        input_files=input_files,
        created_at=now
    )
    save_log(log)

    sop_dict = sop.model_dump(mode="json")
    code = SOPToExecutableCode(sop_dict)

    # B6: 用 __INPUT_PATHS__ 字典注入路径，避免文件名含引号/空格/中文时字符串替换出错
    input_paths_preamble = f"__INPUT_PATHS__ = {json.dumps(filename_mapping, ensure_ascii=False)}\n"
    for safe_filename in filename_mapping:
        escaped_key = json.dumps(safe_filename)
        code = code.replace(f"'{safe_filename}'", f"__INPUT_PATHS__[{escaped_key}]")
        code = code.replace(f'"{safe_filename}"', f"__INPUT_PATHS__[{escaped_key}]")
    code = input_paths_preamble + code

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
