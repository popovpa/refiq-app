import { api } from './client';

export interface LoginData {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
}

export interface User {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  avatar_url: string | null;
  phone: string | null;
  timezone: string;
  language: string;
  email_verified_at: string | null;
  status: string;
  roles: Array<{ role: string; status: string }>;
  created_at?: string | null;
}

export interface SessionData {
  user: User;
  active_role: string | null;
  active_business_id: string | null;
  business_name?: string | null;
  partner_name?: string | null;
}

export interface ForgotPasswordData {
  email: string;
}

export interface ResetPasswordData {
  token: string;
  password: string;
}

export interface PasswordResetResponse {
  status: string;
  message: string;
}

export interface RegisterResponse {
  status: string;
  message: string;
}

export const authApi = {
  login: (data: LoginData) => api.post<SessionData>('/auth/login', data),
  register: (data: RegisterData) => api.post<RegisterResponse>('/auth/register', data),
  logout: () => api.post<void>('/auth/logout'),
  logoutAll: () => api.post<void>('/auth/logout-all'),
  getSession: () => api.get<SessionData>('/auth/session'),
  forgotPassword: (data: ForgotPasswordData) =>
    api.post<PasswordResetResponse>('/auth/forgot-password', data),
  resetPassword: (data: ResetPasswordData) =>
    api.post<PasswordResetResponse>('/auth/reset-password', data),
  confirmEmail: (data: { token: string }) =>
    api.post<PasswordResetResponse>('/auth/confirm-email', data),
  confirmEmailLogin: (data: { token: string }) =>
    api.post<SessionData>('/auth/confirm-email/login', data),
};
