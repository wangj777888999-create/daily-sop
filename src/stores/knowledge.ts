import { defineStore } from 'pinia'
import type { KnowledgeDocument, Folder, SearchResult, RAGRequest, RAGResponse } from '@/types/knowledge'
import * as kbApi from '@/services/knowledgeApi'

interface KnowledgeState {
  documents: KnowledgeDocument[]
  folders: Folder[]
  allTags: string[]
  selectedDocument: KnowledgeDocument | null
  searchResults: SearchResult[]
  searchQuery: string
  currentFolderId: string | null
  viewMode: 'browser' | 'search'
  gridView: boolean
  loading: boolean
  searchLoading: boolean
}

export const useKnowledgeStore = defineStore('knowledge', {
  state: (): KnowledgeState => ({
    documents: [],
    folders: [],
    allTags: [],
    selectedDocument: null,
    searchResults: [],
    searchQuery: '',
    currentFolderId: null,
    viewMode: 'browser',
    gridView: true,
    loading: false,
    searchLoading: false,
  }),

  getters: {
    documentsInCurrentFolder(state): KnowledgeDocument[] {
      if (!state.currentFolderId) return state.documents
      return state.documents.filter(d => d.folder_id === state.currentFolderId)
    },
    documentCount(state): number {
      return state.documents.length
    },
    filteredByTag(state) {
      return (tag: string) => state.documents.filter(d => d.tags?.includes(tag))
    },
  },

  actions: {
    async loadDocuments() {
      this.loading = true
      try {
        await kbApi.fetchDocuments({ folder_id: this.currentFolderId || undefined })
        this.documents = kbApi.documents.value
      } finally {
        this.loading = false
      }
    },

    async loadFolders() {
      await kbApi.fetchFolders()
      this.folders = kbApi.folders.value
    },

    async loadTags() {
      await kbApi.fetchAllTags()
      this.allTags = kbApi.allTags.value
    },

    async selectDocument(docId: string) {
      this.selectedDocument = this.documents.find(d => d.id === docId) || null
    },

    async uploadDocument(file: File, folderId?: string, tags?: string[]) {
      await kbApi.uploadDocument(file, folderId || this.currentFolderId || undefined, tags)
      this.documents = kbApi.documents.value
      await this.loadTags()
    },

    async deleteDocument(docId: string) {
      await kbApi.deleteDocument(docId)
      this.documents = kbApi.documents.value
      if (this.selectedDocument?.id === docId) {
        this.selectedDocument = null
      }
    },

    async search(query: string) {
      this.searchQuery = query
      this.searchLoading = true
      try {
        await kbApi.searchDocuments(query)
        this.searchResults = kbApi.searchResults.value
      } finally {
        this.searchLoading = false
      }
    },

    async createFolder(name: string) {
      await kbApi.createFolder(name)
      this.folders = kbApi.folders.value
    },

    async deleteFolder(folderId: string) {
      await kbApi.deleteFolder(folderId)
      this.folders = kbApi.folders.value
      if (this.currentFolderId === folderId) {
        this.currentFolderId = null
        await this.loadDocuments()
      }
    },

    async generateContent(prompt: string, docIds?: string[], style: 'policy' | 'report' | 'general' = 'policy'): Promise<RAGResponse> {
      const request: RAGRequest = {
        prompt,
        doc_ids: docIds,
        style,
        top_k: 5,
      }
      return kbApi.generateContent(request)
    },

    setFolder(folderId: string | null) {
      this.currentFolderId = folderId
      this.loadDocuments()
    },
  },
})
