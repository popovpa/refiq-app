export const ROLE_CONTEXT_ORDER = ['business', 'partner'] as const;

export type RoleContext = (typeof ROLE_CONTEXT_ORDER)[number];

export const ROLE_CONTEXT_LABELS: Record<RoleContext, { ru: string; en: string }> = {
  business: { ru: 'Бизнес', en: 'Business' },
  partner: { ru: 'Партнёр', en: 'Partner' },
};

export function roleContextLabel(role: string, lang: 'ru' | 'en'): string {
  const labels = ROLE_CONTEXT_LABELS[role as RoleContext];
  return labels ? labels[lang] : role;
}

export function activeRoleContexts(
  roles: Array<{ role: string; status: string }> | undefined,
): RoleContext[] {
  return ROLE_CONTEXT_ORDER.filter((role) =>
    (roles || []).some((item) => item.role === role && item.status === 'active'),
  );
}

export function hasRoleContext(
  roles: Array<{ role: string; status: string }> | undefined,
  role: RoleContext,
): boolean {
  return activeRoleContexts(roles).includes(role);
}

export function hasMultipleRoleContexts(
  roles: Array<{ role: string; status: string }> | undefined,
): boolean {
  const active = activeRoleContexts(roles);
  return active.includes('business') && active.includes('partner');
}

export function postAuthPath(session: {
  user?: { roles?: Array<{ role: string; status: string }> };
  active_role?: string | null;
} | null): string {
  if (!session?.user) return '/login';
  const roles = activeRoleContexts(session.user.roles);
  if (roles.length === 0) return '/onboarding';
  if (session.active_role && roles.includes(session.active_role as RoleContext)) {
    return `/${session.active_role}`;
  }
  return `/${roles[0]}`;
}
