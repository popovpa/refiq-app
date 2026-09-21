import { clearClientSession, shouldClearSessionOnUnauthorized } from '@/shared/auth/sessionCache';

const API_BASE = '/api/v1';

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

export interface ApiError {
  status: number;
  error: {
    code: string;
    message: string;
    request_id?: string;
    details?: unknown;
  };
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { method = 'GET', body, headers = {} } = options;

    const config: RequestInit = {
      method,
      headers: {
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...headers,
      },
      credentials: 'include',
    };

    if (body !== undefined) {
      config.body = JSON.stringify(body);
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, config);

    if (!response.ok) {
      if (response.status === 401 && shouldClearSessionOnUnauthorized(endpoint)) {
        clearClientSession();
      }
      const payload = await response.json().catch(() => null);
      const rawMessage = payload?.error?.message ?? payload?.detail;
      const message =
        typeof rawMessage === 'string' ? rawMessage : 'An error occurred';

      const err: ApiError = {
        status: response.status,
        error: {
          code: payload?.error?.code || 'HTTP_ERROR',
          message,
          request_id: payload?.error?.request_id,
          details: payload?.error?.details ?? payload?.detail,
        },
      };
      throw err;
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  get<T>(endpoint: string) {
    return this.request<T>(endpoint);
  }

  post<T>(endpoint: string, body?: unknown) {
    return this.request<T>(endpoint, { method: 'POST', body });
  }

  patch<T>(endpoint: string, body?: unknown) {
    return this.request<T>(endpoint, { method: 'PATCH', body });
  }

  put<T>(endpoint: string, body?: unknown) {
    return this.request<T>(endpoint, { method: 'PUT', body });
  }

  delete<T>(endpoint: string) {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }

  async download(endpoint: string, filename: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'GET',
      credentials: 'include',
    });
    if (!response.ok) {
      if (response.status === 401 && shouldClearSessionOnUnauthorized(endpoint)) {
        clearClientSession();
      }
      const payload = await response.json().catch(() => null);
      const rawMessage = payload?.error?.message ?? payload?.detail;
      const message = typeof rawMessage === 'string' ? rawMessage : 'An error occurred';
      const err: ApiError = {
        status: response.status,
        error: {
          code: payload?.error?.code || 'HTTP_ERROR',
          message,
          request_id: payload?.error?.request_id,
          details: payload?.error?.details ?? payload?.detail,
        },
      };
      throw err;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }
}

export const api = new ApiClient(API_BASE);
