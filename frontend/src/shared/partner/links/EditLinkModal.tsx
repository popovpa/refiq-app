import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { api, type ApiError } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { useToast } from '@/shared/components/Toast';
import { TRAFFIC_TYPES } from '@/shared/offers/labels';
import type { PartnerLinkItem } from '@/shared/partner/links/types';

function trafficOptionsForLink(link: PartnerLinkItem) {
  const forbidden = new Set(link.offer_forbidden_traffic || []);
  const allowed = link.offer_allowed_traffic || [];
  const base = allowed.length
    ? TRAFFIC_TYPES.filter((item) => allowed.includes(item.value))
    : TRAFFIC_TYPES;
  return base.filter((item) => !forbidden.has(item.value));
}

export function EditLinkModal({
  link,
  onClose,
}: {
  link: PartnerLinkItem;
  onClose: () => void;
}) {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [name, setName] = useState(link.name?.trim() || '');
  const [source, setSource] = useState(link.traffic_source || '');
  const [notes, setNotes] = useState(link.notes || '');
  const [formError, setFormError] = useState<string | null>(null);

  const trafficOptions = useMemo(() => trafficOptionsForLink(link), [link]);

  useEffect(() => {
    if (!source && trafficOptions.length) {
      setSource(trafficOptions[0].value);
    }
  }, [source, trafficOptions]);

  const save = useMutation({
    mutationFn: () =>
      api.patch(`/partner/links/${link.id}`, {
        name: name.trim(),
        traffic_source: source,
        notes: notes.trim() || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['partner', 'links'] });
      addToast('Ссылка обновлена', 'success');
      onClose();
    },
    onError: (error: unknown) => {
      const apiError = error as ApiError | undefined;
      if (apiError?.error?.code === 'TRAFFIC_SOURCE_FORBIDDEN') {
        setFormError(apiError.error.message);
        return;
      }
      setFormError('Не удалось сохранить изменения. Попробуйте ещё раз.');
    },
  });

  const canSubmit = Boolean(name.trim() && source && !save.isPending);

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className="relative ui-card w-full max-w-lg p-5 space-y-4 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <h2 className="ui-section-title">Редактировать ссылку</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={18} />
          </button>
        </div>

        <label className="block">
          <span className="ui-label">Название ссылки *</span>
          <input className="ui-input" value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="block">
          <span className="ui-label">Источник трафика *</span>
          <select className="ui-input" value={source} onChange={(e) => setSource(e.target.value)}>
            {trafficOptions.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="ui-label">Заметка</span>
          <textarea
            className="ui-input min-h-[72px] h-auto py-2"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </label>
        {formError && <p className="text-sm text-destructive">{formError}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button disabled={!canSubmit} onClick={() => save.mutate()}>
            {save.isPending ? 'Сохранение...' : 'Сохранить'}
          </Button>
        </div>
      </div>
    </div>
  );
}
