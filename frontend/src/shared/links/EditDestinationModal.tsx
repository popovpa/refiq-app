import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Info, X } from 'lucide-react';
import { api, type ApiError } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { useToast } from '@/shared/components/Toast';
import { validateDestinationUrl, siteHostname } from '@/shared/links/destinationUrl';
import { displayTrackingUrl } from '@/shared/offers/trackingLink';
import type { BusinessSite } from '@/pages/business/settings/types';

export function EditDestinationModal({
  offerId,
  linkId,
  shortCode,
  currentUrl,
  status,
  onClose,
  onUpdated,
}: {
  offerId: string;
  linkId: string;
  shortCode: string;
  currentUrl: string;
  status?: string | null;
  onClose: () => void;
  onUpdated: (destinationUrl: string) => void;
}) {
  const { addToast } = useToast();
  const navigate = useNavigate();
  const [nextUrl, setNextUrl] = useState(currentUrl);
  const [formError, setFormError] = useState<string | null>(null);
  const isActive = status === 'ACTIVE';
  const host = siteHostname(nextUrl);
  const { data: sites } = useQuery<BusinessSite[]>({
    queryKey: ['business', 'sites'],
    queryFn: () => api.get('/business/sites'),
  });
  const matched = host ? sites?.some((site) => site.domain === host) : false;
  const showMissingSite = Boolean(host && sites && !matched);

  const save = useMutation({
    mutationFn: (destination_url: string) =>
      api.patch<{ destination_url: string; short_code: string; status: string }>(
        `/business/offers/${offerId}/links/${linkId}`,
        { destination_url },
      ),
    onSuccess: (data) => {
      addToast('Целевая страница обновлена', 'success');
      onUpdated(data.destination_url);
      onClose();
    },
    onError: (error: unknown) => {
      const apiError = error as ApiError | undefined;
      const code = apiError?.error?.code;
      if (code === 'INVALID_DESTINATION_URL' || code === 'DESTINATION_DOMAIN_FORBIDDEN') {
        setFormError(apiError?.error?.message || 'Введите корректный URL');
        return;
      }
      setFormError('Не удалось изменить целевую страницу. Попробуйте ещё раз.');
    },
  });

  const submit = () => {
    const checked = validateDestinationUrl(nextUrl);
    if (!checked.ok) {
      setFormError(checked.message);
      return;
    }
    setFormError(null);
    save.mutate(checked.value);
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className="relative ui-card w-full max-w-lg p-5 space-y-4 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <h2 className="ui-section-title">Изменить целевую страницу</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={18} />
          </button>
        </div>

        <div className="space-y-3 text-sm">
          <div>
            <p className="ui-label">Партнёрская ссылка</p>
            <code className="text-sm bg-muted px-2 py-1 rounded-md">{displayTrackingUrl(shortCode)}</code>
          </div>
          <div>
            <p className="ui-label">Текущая страница</p>
            <p className="font-medium break-all">{currentUrl}</p>
          </div>
          <label className="block">
            <span className="ui-label">Новая страница *</span>
            <input
              className="ui-input"
              placeholder="https://"
              value={nextUrl}
              onChange={(e) => {
                setNextUrl(e.target.value);
                if (formError) setFormError(null);
              }}
            />
          </label>
        </div>

        {isActive && (
          <p className="text-sm rounded-lg border border-warning/30 bg-warning/10 px-3 py-2.5">
            Эта ссылка уже принимает трафик. После сохранения все новые переходы будут направляться на новую целевую
            страницу.
          </p>
        )}

        <p className="text-xs text-muted-foreground inline-flex items-start gap-1.5">
          <Info size={12} className="mt-0.5 shrink-0" />
          Изменение повлияет только на новые переходы. Исторические клики и конверсии не изменятся.
        </p>

        {showMissingSite && (
          <div className="rounded-lg border border-border/70 bg-muted/30 px-3 py-2.5 space-y-1">
            <p className="text-sm font-medium">Этот сайт ещё не добавлен в RefIQ</p>
            <p className="text-sm text-muted-foreground break-all">{host}</p>
            <p className="text-xs text-muted-foreground">Ссылку можно сохранить без добавления сайта.</p>
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => {
                onClose();
                navigate('/business/settings?tab=sites');
              }}
            >
              + Добавить сайт
            </Button>
          </div>
        )}

        {formError && <p className="text-sm text-destructive">{formError}</p>}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" disabled={save.isPending} onClick={onClose}>
            Отмена
          </Button>
          <Button type="button" disabled={save.isPending} onClick={submit}>
            {save.isPending ? 'Сохранение...' : 'Сохранить'}
          </Button>
        </div>
      </div>
    </div>
  );
}
