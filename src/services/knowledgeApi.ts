import { ref } from 'vue'
import type { KnowledgeDocument, ParsedDocument, SearchResult, Folder, RAGRequest, RAGResponse } from '@/types/knowledge'

const API_BASE = '/api/knowledge'

export const documents = ref<KnowledgeDocument[]>([])
export const folders = ref<Folder[]>([])
export const allTags = ref<string[]>([])
export const searchResults = ref<SearchResult[]>([])
export const docsLoading = ref(false)
export const searchLoading = ref(false)

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function fetchDocuments(params?: {
  folder_id?: string
  type?: string
  tag?: string
  sort_by?: string
  order?: string
}): Promise<KnowledgeDocument[]> {
  docsLoading.value = true
  try {
    const qs = new URLSearchParams()
    if (params?.folder_id) qs.set('folder_id', params.folder_id)
    if (params?.type) qs.set('type', params.type)
    if (params?.tag) qs.set('tag', params.tag)
    if (params?.sort_by) qs.set('sort_by', params.sort_by)
    if (params?.order) qs.set('order', params.order)
    const url = `${API_BASE}/documents${qs.toString() ? '?' + qs.toString() : ''}`
    const data = await request<KnowledgeDocument[]>(url)
    documents.value = data
    return data
  } finally {
    docsLoading.value = false
  }
}

export async function uploadDocument(
  file: File,
  folder_id?: string,
  tags?: string[]
): Promise<KnowledgeDocument | null> {
  docsLoading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    if (folder_id) formData.append('folder_id', folder_id)
    if (tags && tags.length > 0) formData.append('tags', tags.join(','))
    const data = await request<KnowledgeDocument>(`${API_BASE}/documents`, {
      method: 'POST',
      body: formData,
    })
    documents.value.push(data)
    return data
  } finally {
    docsLoading.value = false
  }
}

export async function deleteDocument(id: string): Promise<boolean> {
  await request(`${API_BASE}/documents/${id}`, { method: 'DELETE' })
  documents.value = documents.value.filter(d => d.id !== id)
  return true
}

export async function searchDocuments(query: string, doc_ids?: string[], top_k: number = 10): Promise<SearchResult[]> {
  searchLoading.value = true
  try {
    const body: any = { query, top_k }
    if (doc_ids && doc_ids.length > 0) {
      body.doc_ids = doc_ids
    }
    const data = await request<SearchResult[]>(`${API_BASE}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    searchResults.value = data
    return data
  } finally {
    searchLoading.value = false
  }
}

export async function getDocumentContent(docId: string): Promise<ParsedDocument | null> {
  return request<ParsedDocument>(`${API_BASE}/documents/${docId}/content`)
}

export function getDocumentDownloadUrl(docId: string): string {
  return `${API_BASE}/documents/${docId}/download`
}

export async function generateContent(request_: RAGRequest): Promise<RAGResponse> {
  return request<RAGResponse>(`${API_BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request_),
  })
}

export async function fetchFolders(): Promise<Folder[]> {
  const data = await request<Folder[]>(`${API_BASE}/folders`)
  folders.value = data
  return data
}

export async function createFolder(name: string, parentId?: string): Promise<Folder | null> {
  const data = await request<Folder>(`${API_BASE}/folders`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, parent_id: parentId || null }),
  })
  folders.value.push(data)
  return data
}

export async function deleteFolder(id: string): Promise<boolean> {
  await request(`${API_BASE}/folders/${id}`, { method: 'DELETE' })
  folders.value = folders.value.filter(f => f.id !== id)
  return true
}

export async function fetchAllTags(): Promise<string[]> {
  const data = await request<string[]>(`${API_BASE}/tags`)
  allTags.value = data
  return data
}

export async function reparseDocument(docId: string): Promise<{ message: string; chunk_count: number }> {
  return request(`${API_BASE}/reparse/${docId}`, { method: 'POST' })
}
