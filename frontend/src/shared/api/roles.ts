import { api } from './client';
import type { SessionData } from './auth';

export interface ActivateBusinessPayload {
  name: string;
  website?: string;
  country: string;
  category?: string;
  work_email: string;
  phone: string;
  description?: string;
  subject_type?: string;
  legal_name?: string;
  inn?: string;
  ogrn?: string;
  ogrnip?: string;
  legal_address?: string;
  contact_name?: string;
  job_title?: string;
  candidate_id?: string | null;
}

export interface ActivatePartnerPayload {
  subject_type: string;
  tax_status?: string;
  display_name?: string;
  legal_name?: string;
  first_name?: string;
  last_name?: string;
  middle_name?: string;
  inn?: string;
  ogrn?: string;
  ogrnip?: string;
  legal_address?: string;
  country?: string;
  city?: string;
  phone?: string;
  contact_name?: string;
  candidate_id?: string | null;
}

export const rolesApi = {
  activatePartner: (payload: ActivatePartnerPayload) => api.post<SessionData>('/me/roles/partner', payload),
  activateBusiness: (payload: ActivateBusinessPayload) => api.post<SessionData>('/me/roles/business', payload),
};
