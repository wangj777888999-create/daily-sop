// Knowledge base TypeScript types

export type DocType = 'PDF' | 'DOCX' | 'XLSX' | 'TXT' | 'MD'

export interface Folder {
  id: string
  name: string
  parent_id: string | null
  created_at: string
}

export interface KnowledgeDocument {
  id: string
  name: string
  type: DocType
  size_bytes: number
  folder_id: string | null
  tags: string[]
  content_hash: string
  chunk_count: number
  parsed_at: string | null
  created_at: string
  updated_at: string
}

export interface ParsedChunk {
  chunk_type: 'heading' | 'paragraph' | 'table' | 'list_item'
  level: number
  text: string
  page: number
  heading_path: string
}

export interface ParsedDocument {
  doc_id: string
  full_text: string
  chunks: ParsedChunk[]
}

export interface SearchResult {
  doc_id: string
  doc_name: string
  doc_type: DocType
  chunk_text: string
  chunk_type: string
  heading_path: string
  score: number
  page: number
}

export interface RAGRequest {
  prompt: string
  doc_ids?: string[]
  style: 'policy' | 'report' | 'general'
  top_k: number
}

export interface RAGResponse {
  generated_text: string
  sources: Array<{
    index?: number
    doc_name: string
    location?: string
    content?: string
  }>
}
