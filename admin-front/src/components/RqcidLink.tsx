import { Link } from 'react-router-dom';
import { tracePath } from '@/lib/navigation';

export function RqcidLink({ rqcid }: { rqcid?: string | null }) {
  if (!rqcid) return <span className="text-muted-foreground">—</span>;
  return (
    <Link to={tracePath(rqcid)} className="font-mono text-xs text-primary hover:underline">
      {rqcid}
    </Link>
  );
}
