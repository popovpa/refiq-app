import { useQuery } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { partnerDisplayName } from '@/shared/partners/displayName';

interface PartnerPublicProfile {
  partner_id: number;
  display_name: string;
  description?: string | null;
  status?: string | null;
  created_at?: string | null;
  offers_count?: number;
}

export function PartnerPublicProfileDialog({
  partnerId,
  onClose,
}: {
  partnerId: number;
  onClose: () => void;
}) {
  const { data, isLoading, isError } = useQuery<PartnerPublicProfile>({
    queryKey: ['business', 'partners', partnerId],
    queryFn: () => api.get(`/business/partners/${partnerId}`),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className="relative ui-card w-full max-w-md p-5 space-y-4 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <h2 className="ui-section-title">Профиль партнёра</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={18} />
          </button>
        </div>
        <div className="text-sm text-muted-foreground space-y-2">
          {isLoading && <p>Загрузка...</p>}
          {isError && <p>Не удалось загрузить профиль партнёра.</p>}
          {data && (
            <>
              <p className="font-medium text-foreground">{partnerDisplayName(data.display_name, data.partner_id)}</p>
              {data.description ? <p>{data.description}</p> : <p>Партнёр не добавил описание профиля.</p>}
              <p>
                {data.offers_count ?? 0} офферов · с{' '}
                {data.created_at ? new Date(data.created_at).toLocaleDateString('ru-RU') : '—'}
              </p>
            </>
          )}
        </div>
        <div className="flex justify-end">
          <Button variant="secondary" onClick={onClose}>
            Закрыть
          </Button>
        </div>
      </div>
    </div>
  );
}
