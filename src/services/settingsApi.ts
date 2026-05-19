const API_BASE = '/api/settings'

export interface SettingsStatus {
  api_key_configured: boolean
  api_key_preview: string // e.g. "sk-ant-****...****cXYZ"
}

export interface TestResult {
  success: boolean
  message: string
}

/** 获取当前系统配置状态 */
export async function getSettings(): Promise<SettingsStatus> {
  const res = await fetch(API_BASE)
  if (!res.ok) throw new Error('获取配置失败')
  return res.json()
}

/** 保存 API Key */
export async function saveSettings(apiKey: string): Promise<void> {
  const res = await fetch(API_BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ anthropic_api_key: apiKey }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '保存失败')
  }
}

/** 测试当前 Key 的连通性 */
export async function testConnection(): Promise<TestResult> {
  const res = await fetch(`${API_BASE}/test`, { method: 'POST' })
  if (!res.ok) throw new Error('请求失败')
  return res.json()
}
