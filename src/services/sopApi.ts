import { ref } from 'vue'

export interface SOP {
  id: string
  name: string
  description: string
  steps: SOPStep[]
  tags: string[]
  created_at: string
  updated_at: string
}

export interface SOPStep {
  id: string
  order: number
  description: string
  code?: string
}

export interface ExecutionResult {
  id: string
  sop_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  result?: any
  error?: string
  created_at: string
  completed_at?: string
}

// SOP List
export const sops = ref<SOP[]>([])
export const sopsLoading = ref(false)

// Execution
export const executions = ref<Map<string, ExecutionResult>>(new Map())
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
    currentExecution.value = data
    return data
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
    executions.value.set(execId, data)
    if (currentExecution.value?.id === execId) {
      currentExecution.value = data
    }
    return data
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
export async function parsePythonCode(code: string): Promise<SOPStep[] | null> {
  try {
    const response = await fetch(`${API_BASE}/sops/parse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code })
    })
    if (!response.ok) throw new Error('Failed to parse Python code')
    return await response.json()
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
