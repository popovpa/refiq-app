const API_BASE = '/api/admin/v1';

export interface ApiError {
  status: number;
  error: { code: string; message: string; details?: unknown };
}

export function isApiError(value: unknown): value is ApiError {
  return Boolean(value && typeof value === 'object' && 'status' in value && 'error' in value);
}

export function errorMessage(err: unknown, fallback = 'Ошибка запроса') {
  if (isApiError(err)) return err.error.message || fallback;
  if (err instanceof Error) return err.message;
  return fallback;
}

export function qs(params: Record<string, string | number | boolean | undefined | null>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    search.set(key, String(value));
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : '';
}

class ApiClient {
  async request<T>(endpoint: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
    const { method = 'GET', body } = options;
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method,
      credentials: 'include',
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      const rawMessage = payload?.error?.message ?? payload?.detail;
      const err: ApiError = {
        status: response.status,
        error: {
          code: payload?.error?.code || (response.status === 403 ? 'FORBIDDEN' : 'HTTP_ERROR'),
          message: typeof rawMessage === 'string' ? rawMessage : fallbackStatus(response.status),
          details: payload?.error?.details,
        },
      };
      throw err;
    }
    if (response.status === 204) return undefined as T;
    return response.json();
  }

  get<T>(endpoint: string) {
    return this.request<T>(endpoint);
  }

  post<T>(endpoint: string, body?: unknown) {
    return this.request<T>(endpoint, { method: 'POST', body });
  }
}

function fallbackStatus(status: number) {
  if (status === 401) return 'Требуется авторизация';
  if (status === 403) return 'Недостаточно прав';
  if (status === 404) return 'Сущность не найдена';
  if (status === 409) return 'Действие конфликтует с текущим состоянием домена';
  if (status === 422) return 'Ошибка валидации';
  if (status >= 500) return 'Временная ошибка сервера';
  return 'Ошибка запроса';
}

export const api = new ApiClient();
