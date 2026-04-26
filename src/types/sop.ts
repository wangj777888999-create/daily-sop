export interface DataSource {
  id: string
  name: string
  type: 'primary' | 'reference' | 'output'
  description?: string
  variableName: string
  operation: 'read' | 'write'
  codeSnippet: string
  lineNumber: number
}

export interface SOPStep {
  id: string
  order: number
  action: string
  params: Record<string, any>
  description: string
  inputSources?: string[]
  outputSource?: string
  code?: string
}

export interface SOP {
  id: string
  name: string
  description: string
  steps: SOPStep[]
  dataSources: DataSource[]
  tags: string[]
  created_at: string
  updated_at: string
}

export interface ParsedCodeResult {
  name: string
  description: string
  steps: SOPStep[]
  dataSources: DataSource[]
}