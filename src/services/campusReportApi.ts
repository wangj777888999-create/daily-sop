const BASE = '/api/campus-reports'

export interface School {
  id: string
  name: string
  created_at: string
}

export interface Section {
  id: string
  title: string
  content: string
  images: string[]       // filenames, relative to the school's images/ dir
  order: number
  created_at: string
  updated_at: string
}

export interface UploadedImage {
  filename: string
  url: string
}

async function req<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || '请求失败')
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

function post<T>(url: string, body: unknown): Promise<T> {
  return req<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

function put<T>(url: string, body: unknown): Promise<T> {
  return req<T>(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

function del(url: string): Promise<void> {
  return req<void>(url, { method: 'DELETE' })
}

export const campusReportApi = {
  // Schools
  listSchools: (): Promise<School[]> =>
    req(`${BASE}/schools`),

  createSchool: (name: string): Promise<School> =>
    post(`${BASE}/schools`, { name }),

  deleteSchool: (schoolId: string): Promise<void> =>
    del(`${BASE}/schools/${schoolId}`),

  // Sections
  listSections: (schoolId: string): Promise<Section[]> =>
    req(`${BASE}/schools/${schoolId}/sections`),

  createSection: (schoolId: string, title = '新板块'): Promise<Section> =>
    post(`${BASE}/schools/${schoolId}/sections`, { title }),

  updateSection: (
    schoolId: string,
    sectionId: string,
    patch: Partial<Pick<Section, 'title' | 'content' | 'order' | 'images'>>
  ): Promise<Section> =>
    put(`${BASE}/schools/${schoolId}/sections/${sectionId}`, patch),

  deleteSection: (schoolId: string, sectionId: string): Promise<void> =>
    del(`${BASE}/schools/${schoolId}/sections/${sectionId}`),

  // Images
  uploadImage: (schoolId: string, file: File): Promise<UploadedImage> => {
    const fd = new FormData()
    fd.append('file', file)
    return req(`${BASE}/schools/${schoolId}/images`, { method: 'POST', body: fd })
  },

  deleteImage: (schoolId: string, filename: string): Promise<void> =>
    del(`${BASE}/schools/${schoolId}/images/${filename}`),

  imageUrl: (schoolId: string, filename: string): string =>
    `${BASE}/schools/${schoolId}/images/${filename}`,
}
