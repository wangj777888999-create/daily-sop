import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from settings_storage import load_settings, save_settings

router = APIRouter(prefix="/settings", tags=["settings"])


class SaveSettingsRequest(BaseModel):
    anthropic_api_key: str


class SettingsStatusResponse(BaseModel):
    api_key_configured: bool
    api_key_preview: str  # 打码后的预览，如 "sk-ant-****...****cXYZ"


def _mask_key(key: str) -> str:
    """将 API Key 打码，只显示前8位和后4位"""
    if not key:
        return ""
    if len(key) <= 12:
        return "*" * len(key)
    return key[:8] + "****...****" + key[-4:]


@router.get("", response_model=SettingsStatusResponse)
def get_settings():
    """获取当前系统配置状态"""
    settings = load_settings()
    key = settings.get("anthropic_api_key", "")
    return SettingsStatusResponse(
        api_key_configured=bool(key),
        api_key_preview=_mask_key(key),
    )


@router.post("")
def update_settings(body: SaveSettingsRequest):
    """保存系统配置，并同步更新运行时环境变量"""
    key = body.anthropic_api_key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")

    save_settings({"anthropic_api_key": key})
    os.environ["ANTHROPIC_API_KEY"] = key

    return {"success": True, "message": "配置已保存"}


@router.post("/test")
def test_connection():
    """用当前配置的 Key 发送一个最小请求，验证连通性"""
    key = os.environ.get("ANTHROPIC_API_KEY", "")

    # 如果环境变量里没有，尝试从 settings.json 读取
    if not key:
        settings = load_settings()
        key = settings.get("anthropic_api_key", "")

    if not key:
        return {"success": False, "message": "未配置 API Key，请先保存配置"}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        # 发送最小请求验证 Key 有效性
        client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=8,
            messages=[{"role": "user", "content": "hi"}],
        )
        return {"success": True, "message": "连接成功，API Key 有效"}
    except anthropic.AuthenticationError:
        return {"success": False, "message": "API Key 无效，请检查后重试"}
    except anthropic.APIConnectionError:
        return {"success": False, "message": "网络连接失败，请检查网络"}
    except Exception as e:
        return {"success": False, "message": f"连接失败：{str(e)}"}
