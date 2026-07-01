import { supabase } from './supabase'

const BASE = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000'

async function authHeaders(): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession()
  return session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}
}

// Typed API error — callers can check .status to distinguish 402 from other errors
export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.ok) return res.json() as Promise<T>

  let body: Record<string, unknown> = {}
  try { body = await res.json() } catch { /* ignore parse error */ }

  if (res.status === 401) {
    // Session expired / invalid token — sign out globally and redirect to login
    window.dispatchEvent(new CustomEvent('unauthorized'))
    throw new ApiError('Сессия истекла. Войдите снова.', 401)
  }

  if (res.status === 402) {
    // Dispatch global event so InsufficientTokensModal can pick it up
    window.dispatchEvent(new CustomEvent('insufficient-tokens', {
      detail: { required: body.required ?? 0, balance: body.balance ?? 0 },
    }))
    throw new ApiError('Недостаточно токенов', 402)
  }

  const detail = body?.detail
  const msg: string =
    (typeof detail === 'object' && detail !== null && 'error' in detail
      ? String((detail as Record<string, unknown>).error)
      : typeof detail === 'string'
      ? detail
      : undefined) ?? `HTTP ${res.status}`
  throw new ApiError(msg, res.status)
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
    let body: Record<string, unknown> = {}
    try { body = await res.json() } catch { /* */ }
    if (res.status === 401) {
      window.dispatchEvent(new CustomEvent('unauthorized'))
      throw new ApiError('Сессия истекла. Войдите снова.', 401)
    }
    if (res.status === 402) {
      window.dispatchEvent(new CustomEvent('insufficient-tokens', {
        detail: { required: body.required ?? 0, balance: body.balance ?? 0 },
      }))
      throw new ApiError('Недостаточно токенов', 402)
    }
    const detail = body?.detail
    const msg = (typeof detail === 'object' && detail !== null && 'error' in detail
      ? String((detail as Record<string, unknown>).error)
      : typeof detail === 'string' ? detail : `HTTP ${res.status}`)
    throw new ApiError(msg, res.status)
  }
  const cd = res.headers.get('content-disposition') ?? ''
  const match = cd.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
  const filename = match ? match[1].replace(/['"]/g, '') : 'document.docx'
  return { blob: await res.blob(), filename }
}
