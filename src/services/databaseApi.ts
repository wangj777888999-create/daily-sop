const BASE = '/api/database'

export interface ConnStatus {
  db_type?: string
  display_name?: string
  connection_type?: string
}

export interface TableColumn {
  name: string
  type: string
  notnull: boolean
  pk: boolean
}

export interface QueryResult {
  columns: string[]
  rows: (string | null)[][]
  row_count: number
  truncated: boolean
  affected?: number
}

async function req<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || '请求失败')
  }
  return res.json()
}

function post<T>(url: string, body: unknown): Promise<T> {
  return req<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export const databaseApi = {
  connectLocal: (body: {
    db_type: string
    path?: string
    host?: string
    port?: number
    database?: string
    user?: string
    password?: string
  }) => post<ConnStatus & { ok: boolean }>(`${BASE}/connect/local`, body),

  connectSSH: (body: {
    ssh_host: string
    ssh_port: number
    ssh_user: string
    ssh_password?: string
    ssh_key?: string
    db_type: string
    db_host: string
    db_port?: number
    database: string
    db_user: string
    db_password: string
  }) => post<ConnStatus & { ok: boolean }>(`${BASE}/connect/ssh`, body),

  getStatus: () => req<ConnStatus>(`${BASE}/status`),
  getTables: () => req<string[]>(`${BASE}/tables`),
  getColumns: (table: string) => req<TableColumn[]>(`${BASE}/columns/${encodeURIComponent(table)}`),
  query: (sql: string, limit = 500) => post<QueryResult>(`${BASE}/query`, { sql, limit }),
  listDatabases: () => req<string[]>(`${BASE}/databases`),
  switchDatabase: (database: string) => post<ConnStatus>(`${BASE}/switch`, { database }),
  disconnect: () => post<{ ok: boolean }>(`${BASE}/disconnect`, {}),

  /** 查询一张表的行数 */
  getRowCount: (table: string) =>
    post<QueryResult>(`${BASE}/query`, { sql: `SELECT COUNT(*) AS cnt FROM \`${table}\``, limit: 1 }),

  /** 查询样本数据（前5行） */
  getSampleRows: (table: string) =>
    post<QueryResult>(`${BASE}/query`, { sql: `SELECT * FROM \`${table}\` LIMIT 5`, limit: 5 }),

  /** AI 解读表用途 */
  describeTable: (table_name: string, columns: TableColumn[]) =>
    post<{ description: string }>(`${BASE}/describe-table`, { table_name, columns }),

  /** 获取所有表的数据库原生备注 {tableName: comment} */
  getTableComments: () => req<Record<string, string>>(`${BASE}/table-comments`),

  /** 获取字段（含 comment 字段） */
  getColumnsWithComments: (table: string) =>
    req<(TableColumn & { comment: string })[]>(`${BASE}/columns-full/${encodeURIComponent(table)}`),
}
