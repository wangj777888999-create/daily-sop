import { ref, reactive } from 'vue'
import type { SOP, ParsedCodeResult } from '@/types/sop'
export type { SOP, ParsedCodeResult } from '@/types/sop'
export type { SOPStep, DataSource } from '@/types/sop'

export type ExecutionStatus = 'pending' | 'running' | 'success' | 'failed'

export interface ExecutionResult {
  id: string
  sop_id?: string
  status: ExecutionStatus
  input_files?: string[]
  output_file?: string
  error?: string
  created_at?: string
  completed_at?: string
}

// 后端 → 前端 字段适配
function adaptExecutionResponse(data: any): ExecutionResult {
  return {
    id: data.execution_id ?? data.id,
    sop_id: data.sop_id,
    status: data.status,
    input_files: data.input_files,
    output_file: data.output_file,
    error: data.error_message ?? data.error,
    created_at: data.created_at,
    completed_at: data.completed_at,
  }
}

// SOP List
export const sops = ref<SOP[]>([])
export const sopsLoading = ref(false)

// Execution
// Q2: 使用 reactive 而非 ref<Map>，避免 .set() 不触发更新的陷阱
export const executions = reactive(new Map<string, ExecutionResult>())
export const currentExecution = ref<ExecutionResult | null>(null)

// API Base URL
const API_BASE = '/api'

// Fetch all SOPs
export async function fetchSOPs(): Promise<SOP[]> {
  sopsLoading.value = true
  try {
    const response = await fetch(`${API_BASE}/sops`)
    if (!response.ok) throw new Error('Failed to fetch SOPs')
    const data = await response.json()
    sops.value = data
    return data
  } catch (error) {
    console.error('Error fetching SOPs:', error)
    return []
  } finally {
    sopsLoading.value = false
  }
}

// Get single SOP
export async function getSOP(id: string): Promise<SOP | null> {
  try {
    const response = await fetch(`${API_BASE}/sops/${id}`)
    if (!response.ok) return null
    const data = await response.json()
    // Transform backend format to frontend format
    // Backend: { steps: [{step, action, params}] }
    // Frontend: { steps: [{id, order, action, params, description, code}] }
    if (data.steps) {
      data.steps = data.steps.map((s: any, idx: number) => ({
        id: `step-${idx + 1}`,
        order: s.step || idx + 1,
        action: s.action || '',
        params: s.params || {},
        description: s.description || '',
        code: s.code || ''
      }))
    }
    return data
  } catch (error) {
    console.error('Error fetching SOP:', error)
    return null
  }
}

// Create SOP
export async function createSOP(sop: Partial<SOP>): Promise<SOP | null> {
  try {
    const response = await fetch(`${API_BASE}/sops`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(sop)
    })
    if (!response.ok) throw new Error('Failed to create SOP')
    const data = await response.json()
    sops.value.push(data)
    return data
  } catch (error) {
    console.error('Error creating SOP:', error)
    return null
  }
}

// Update SOP
export async function updateSOP(id: string, sop: Partial<SOP>): Promise<SOP | null> {
  try {
    const response = await fetch(`${API_BASE}/sops/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(sop)
    })
    if (!response.ok) throw new Error('Failed to update SOP')
    const data = await response.json()
    const index = sops.value.findIndex(s => s.id === id)
    if (index !== -1) {
      sops.value[index] = data
    }
    return data
  } catch (error) {
    console.error('Error updating SOP:', error)
    return null
  }
}

// Delete SOP
export async function deleteSOP(id: string): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE}/sops/${id}`, {
      method: 'DELETE'
    })
    if (!response.ok) throw new Error('Failed to delete SOP')
    sops.value = sops.value.filter(s => s.id !== id)
    return true
  } catch (error) {
    console.error('Error deleting SOP:', error)
    return false
  }
}

// Execute SOP
export async function executeSOP(sopId: string, files?: File[]): Promise<ExecutionResult | null> {
  try {
    const formData = new FormData()
    formData.append('sop_id', sopId)
    if (files) {
      files.forEach(file => formData.append('files', file))
    }

    const response = await fetch(`${API_BASE}/execute/${sopId}`, {
      method: 'POST',
      body: formData
    })
    if (!response.ok) throw new Error('Failed to execute SOP')
    const data = await response.json()
    const adapted = adaptExecutionResponse(data)
    currentExecution.value = adapted
    return adapted
  } catch (error) {
    console.error('Error executing SOP:', error)
    return null
  }
}

// Get execution status
export async function getExecutionStatus(execId: string): Promise<ExecutionResult | null> {
  try {
    const response = await fetch(`${API_BASE}/execute/${execId}/status`)
    if (!response.ok) throw new Error('Failed to get execution status')
    const data = await response.json()
    const adapted = adaptExecutionResponse(data)
    executions.set(execId, adapted)
    if (currentExecution.value?.id === execId) {
      currentExecution.value = adapted
    }
    return adapted
  } catch (error) {
    console.error('Error getting execution status:', error)
    return null
  }
}

// Download execution result
export async function downloadExecutionResult(execId: string): Promise<Blob | null> {
  try {
    const response = await fetch(`${API_BASE}/execute/${execId}/download`)
    if (!response.ok) throw new Error('Failed to download result')
    return await response.blob()
  } catch (error) {
    console.error('Error downloading result:', error)
    return null
  }
}

// Parse Python code to SOP steps
export async function parsePythonCode(code: string): Promise<ParsedCodeResult | null> {
  try {
    const response = await fetch(`${API_BASE}/sops/parse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    })
    if (!response.ok) throw new Error('Failed to parse Python code')
    const data = await response.json()
    // 后端返回 { name, description, steps: [{step, action, params}], dataSources: [...] }
    if (data.steps && Array.isArray(data.steps)) {
      const result: ParsedCodeResult = {
        name: data.name || '',
        description: data.description || '',
        steps: data.steps.map((s: any, idx: number) => ({
          id: `step-${idx + 1}`,
          order: s.step || idx + 1,
          action: s.action || '',
          params: s.params || {},
          description: s.action ? `${s.action}: ${JSON.stringify(s.params || {})}` : '',
          inputSources: s.inputSources,
          outputSource: s.outputSource
        })),
        dataSources: data.dataSources || []
      }
      return result
    }
    return null
  } catch (error) {
    console.error('Error parsing Python code:', error)
    return null
  }
}

// Generate SOP from natural language description
export async function generateSOPFromDescription(description: string): Promise<Partial<SOP> | null> {
  try {
    const response = await fetch(`${API_BASE}/sops/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description })
    })
    if (!response.ok) throw new Error('Failed to generate SOP')
    return await response.json()
  } catch (error) {
    console.error('Error generating SOP:', error)
    return null
  }
}
