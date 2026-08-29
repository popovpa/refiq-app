import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { useToast } from '@/shared/components/Toast';
import { TRAFFIC_TYPES } from '@/shared/offers/labels';
import { cn } from '@/shared/utils/cn';

export function RequestAccessModal({
  offerId,
  partnerName,
  onClose,
}: {
  offerId: string | number;
  partnerName: string;
  onClose: () => void;
}) {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [sources, setSources] = useState<string[]>(['telegram']);
  const [topics, setTopics] = useState('');
  const [geo, setGeo] = useState('RU');
  const [comment, setComment] = useState('');

  const request = useMutation({
    mutationFn: () =>
      api.post(`/partner/offers/${offerId}/join`, {
        traffic_sources: sources,
        topics: topics.trim() || null,
        geo,
        comment: comment.trim() || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['partner', 'offers'] });
      addToast('Заявка отправлена', 'success');
      onClose();
    },
    onError: () => addToast('Не удалось отправить заявку', 'error'),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className="relative ui-card w-full max-w-lg p-5 space-y-4 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="ui-section-title">Запросить доступ</h2>
            <p className="text-sm text-muted-foreground mt-1">Данные берутся из партнёрского профиля.</p>
          </div>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X size={18} />
          </button>
        </div>
        <div className="text-sm">
          <span className="text-muted-foreground">Партнёр</span>
          <p className="font-medium">{partnerName}</p>
        </div>
        <div>
          <p className="ui-label">Основные источники трафика</p>
          <div className="flex flex-wrap gap-2">
            {TRAFFIC_TYPES.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() =>
                  setSources((prev) =>
                    prev.includes(item.value) ? prev.filter((value) => value !== item.value) : [...prev, item.value],
                  )
                }
                className={cn(
                  'px-3 py-1.5 rounded-md text-xs font-medium border',
                  sources.includes(item.value)
                    ? 'bg-accent text-primary border-primary/20'
                    : 'bg-card text-muted-foreground border-border',
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        <label className="block">
          <span className="ui-label">Тематики</span>
          <input className="ui-input" value={topics} onChange={(e) => setTopics(e.target.value)} placeholder="SaaS, маркетинг" />
        </label>
        <label className="block">
          <span className="ui-label">GEO</span>
          <input className="ui-input" value={geo} onChange={(e) => setGeo(e.target.value)} />
        </label>
        <label className="block">
          <span className="ui-label">Комментарий для бизнеса</span>
          <textarea className="ui-input min-h-[72px] h-auto py-2" value={comment} onChange={(e) => setComment(e.target.value)} />
        </label>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button disabled={request.isPending} onClick={() => request.mutate()}>
            {request.isPending ? 'Отправка...' : 'Отправить заявку'}
          </Button>
        </div>
      </div>
    </div>
  );
}
