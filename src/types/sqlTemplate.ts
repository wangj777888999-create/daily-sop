export type VariableType = 'text' | 'date' | 'month' | 'number'

export interface TemplateVariable {
  name: string
  type: VariableType
  defaultValue: string
}

export interface SqlTemplate {
  id: string
  name: string
  sql: string
  variables: TemplateVariable[]
  createdAt: number
}

export type VariableValues = Record<string, string>

const STORAGE_KEY = 'db_sql_templates'

export function loadTemplates(): SqlTemplate[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  } catch {
    return []
  }
}

export function saveTemplates(templates: SqlTemplate[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(templates))
}

export function parseVariables(sql: string): string[] {
  const matches = [...sql.matchAll(/\{\{([^}]+)\}\}/g)]
  return [...new Set(matches.map(m => m[1].trim()))]
}

export function buildFinalSql(sql: string, values: VariableValues): string {
  let result = sql
  for (const [name, value] of Object.entries(values)) {
    result = result.split(`{{${name}}}`).join(value)
  }
  return result
}
