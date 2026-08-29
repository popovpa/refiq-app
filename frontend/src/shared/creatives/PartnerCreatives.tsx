import { useQuery } from '@tanstack/react-query';
import { Copy } from 'lucide-react';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { useToast } from '@/shared/components/Toast';
import { CHANNEL_LABELS, FORMAT_LABELS, formatCreativeText } from './labels';
import type { Creative } from './types';

interface Props {
  offerId: string;
  canCreate?: boolean;
  trackingShortCode?: string | null;
}

export function PartnerCreatives({ offerId }: Props) {
  const { addToast } = useToast();

  const { data, isLoading } = useQuery<{ items: Creative[] }>({
    queryKey: ['partner', 'offers', offerId, 'creatives'],
    queryFn: () => api.get(`/partner/offers/${offerId}/creatives`),
    enabled: !!offerId,
  });

  const items = (data?.items || []).filter((item) => !item.partner_id);

  const copy = async (value: string) => {
    await navigator.clipboard.writeText(value);
    addToast('Текст скопирован', 'success');
  };

  const downloadImage = async (item: Creative) => {
    try {
      await api.download(`/partner/offers/${offerId}/promo-materials/${item.id}/image`, `promo-${item.id}.png`);
    } catch {
      addToast('Не удалось скачать изображение', 'error');
    }
  };

  if (isLoading) {
    return (
      <div className="ui-card p-4">
        <h2 className="ui-section-title">Материалы для продвижения</h2>
        <p className="text-sm text-muted-foreground mt-2">Загрузка…</p>
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="ui-card p-4">
        <h2 className="ui-section-title">Материалы для продвижения</h2>
        <p className="text-sm text-muted-foreground mt-2">Пока нет опубликованных материалов.</p>
      </div>
    );
  }

  const texts = items.filter((item) => item.type !== 'banner');
  const images = items.filter((item) => item.type === 'banner');

  return (
    <div className="ui-card p-4 flex flex-col min-h-0">
      <div className="mb-3">
        <h2 className="ui-section-title">Материалы для продвижения</h2>
        <p className="text-sm text-muted-foreground mt-1">Готовые материалы от бизнеса</p>
      </div>

      <div className="space-y-4 overflow-auto">
        {!!texts.length && (
          <section className="space-y-3">
            <h3 className="text-sm font-medium">Тексты</h3>
            {texts.map((item) => {
              const text = formatCreativeText(item);
              return (
                <div key={item.id} className="rounded-lg border border-border/70 p-3 space-y-2">
                  <p className="text-sm font-medium">{item.title || 'Текст'}</p>
                  <p className="text-xs text-muted-foreground">
                    {CHANNEL_LABELS[item.channel || ''] || item.channel || 'Общий'}
                  </p>
                  <pre className="text-sm whitespace-pre-wrap font-sans text-muted-foreground">{text}</pre>
                  <Button size="sm" variant="secondary" onClick={() => copy(text)}>
                    <Copy size={14} />
                    Скопировать
                  </Button>
                </div>
              );
            })}
          </section>
        )}

        {!!images.length && (
          <section className="space-y-3">
            <h3 className="text-sm font-medium">Изображения</h3>
            {images.map((item) => (
              <div key={item.id} className="rounded-lg border border-border/70 p-3 space-y-2">
                <p className="text-sm font-medium">{item.title || 'Промо-изображение'}</p>
                <p className="text-xs text-muted-foreground">
                  {FORMAT_LABELS[item.format || ''] || item.format || '1:1'}
                </p>
                {item.asset?.url && (
                  <img src={item.asset.url} alt="" className="max-h-40 rounded-md border border-border/70" />
                )}
                <Button size="sm" variant="secondary" onClick={() => downloadImage(item)}>
                  Скачать
                </Button>
              </div>
            ))}
          </section>
        )}
      </div>
    </div>
  );
}
