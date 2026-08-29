import { api } from './client';
import type { SessionData } from './auth';

export interface ActivateBusinessPayload {
  name: string;
  website: string;
  country: string;
  category: string;
  work_email: string;
  phone: string;
  description?: string;
}

export const rolesApi = {
  activatePartner: (displayName?: string) =>
    api.post<SessionData>('/me/roles/partner', displayName ? { display_name: displayName } : {}),
  activateBusiness: (payload: ActivateBusinessPayload) =>
    api.post<SessionData>('/me/roles/business', payload),
};
