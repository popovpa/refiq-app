import { useSearchParams } from 'react-router-dom';

export function useQueryState() {
  const [params, setParams] = useSearchParams();
  const get = (key: string) => params.get(key) || '';
  const set = (patch: Record<string, string | undefined>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!('page' in patch) && !('cursor' in patch)) {
      next.delete('page');
      next.delete('cursor');
    }
    setParams(next);
  };
  return { params, get, set };
}
