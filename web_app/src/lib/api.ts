export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function readResponseBody(resp: Response): Promise<unknown> {
  const text = await resp.text()
  if (!text) return undefined

  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

function getErrorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === 'object') {
    const data = body as Record<string, unknown>
    const detail = data.detail || data.message || data.error
    if (typeof detail === 'string' && detail.trim()) return detail
  }

  if (typeof body === 'string' && body.trim()) return body
  return fallback
}

export async function apiFetch<T = unknown>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const resp = await fetch(input, init)
  const body = await readResponseBody(resp)

  if (!resp.ok) {
    throw new ApiError(getErrorMessage(body, `请求失败 (${resp.status})`), resp.status)
  }

  return body as T
}

export function normalizeApiError(error: unknown): string {
  if (error instanceof Error) {
    return error.message === 'Failed to fetch' ? '无法连接服务，请检查服务是否运行' : error.message
  }

  return '请求失败'
}
