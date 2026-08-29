export const ADMIN_READ = 'ADMIN_READ';
export const ADMIN_OPERATIONS = 'ADMIN_OPERATIONS';
export const ADMIN_FINANCE = 'ADMIN_FINANCE';
export const ADMIN_SUPER = 'ADMIN_SUPER';

export function hasPermission(permissions: string[] | undefined, required: string) {
  const granted = new Set(permissions || []);
  if (granted.has(ADMIN_SUPER)) return true;
  return granted.has(required);
}
