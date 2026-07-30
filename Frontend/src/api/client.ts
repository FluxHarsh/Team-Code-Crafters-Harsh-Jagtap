const BASE = '/api/v1'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const { headers: optHeaders, ...restOptions } = options
  const headers =
    optHeaders === undefined
      ? { 'Content-Type': 'application/json' }
      : { 'Content-Type': 'application/json', ...optHeaders }

  const res = await fetch(`${BASE}${path}`, {
    headers,
    ...restOptions,
  })

  if (!res.ok) {
    let msg = `HTTP ${res.status}`
    try {
      const body = await res.json()
      msg = body.detail || body.message || msg
    } catch {}
    throw new ApiError(res.status, msg)
  }

  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  postForm: <T>(path: string, form: FormData) =>
    request<T>(path, {
      method: 'POST',
      body: form,
      // headers intentionally omitted — browser sets multipart boundary automatically
    }),
}
