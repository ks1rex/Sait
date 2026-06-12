import { supabase } from './supabase'

const BASE = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000'

async function authHeaders(): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.ok) return res.json() as Promise<T>
  let msg = `HTTP ${res.status}`
  try {
    const body = await res.json()
    msg = body?.detail?.error ?? body?.detail ?? msg
  } catch { /* ignore parse error */ }
  throw new Error(msg)
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: await authHeaders() })
  return handleResponse<T>(res)
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const hdrs = await authHeaders()
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: body !== undefined ? { ...hdrs, 'Content-Type': 'application/json' } : hdrs,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  return handleResponse<T>(res)
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const hdrs = await authHeaders()
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { ...hdrs, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return handleResponse<T>(res)
}

export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: await authHeaders(),
    body: form,
  })
  return handleResponse<T>(res)
}

export async function apiPostFormBlob(path: string, form: FormData): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: await authHeaders(),
    body: form,
  })
  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try { const b = await res.json(); msg = b?.detail?.error ?? b?.detail ?? msg } catch { /* */ }
    throw new Error(msg)
  }
  const cd = res.headers.get('content-disposition') ?? ''
  const match = cd.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
  const filename = match ? match[1].replace(/['"]/g, '') : 'document.docx'
  return { blob: await res.blob(), filename }
}
