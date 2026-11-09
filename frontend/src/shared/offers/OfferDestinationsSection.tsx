import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { api, type ApiError } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { useToast } from '@/shared/components/Toast';
import {
  destinationTypeLabel,
  legacySkipMessage,
  shortDestinationUrl,
  type DestinationListResponse,
  type DestinationStatus,
  type DestinationType,
  type OfferDestinationItem,
} from '@/shared/offers/destinations';
import { cn } from '@/shared/utils/cn';

const TYPES: DestinationType[] = ['PRODUCT', 'CATEGORY', 'LANDING'];

function errorMessage(error: unknown, fallback: string): string {
  const apiError = error as ApiError | undefined;
  return apiError?.error?.message || fallback;
}

export function OfferDestinationsSection({ offerId }: { offerId: string }) {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState<OfferDestinationItem | 'new' | null>(null);
  const [disableTarget, setDisableTarget] = useState<OfferDestinationItem | null>(null);

  const query = useQuery<DestinationListResponse>({
    queryKey: ['business', 'offers', offerId, 'destinations', page],
    queryFn: () => api.get(`/business/offers/${offerId}/destinations?page=${page}&per_page=20`),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['business', 'offers', offerId, 'destinations'] });
    queryClient.invalidateQueries({ queryKey: ['business', 'offers', offerId] });
  };

  const setPrimary = useMutation({
    mutationFn: (id: number) => api.patch(`/business/offers/${offerId}/destinations/${id}`, { is_primary: true }),
    onSuccess: () => {
      invalidate();
      addToast('Основная страница обновлена', 'success');
    },
    onError: (error) => addToast(errorMessage(error, 'Не удалось назначить основную страницу'), 'error'),
  });

  const setStatus = useMutation({
    mutationFn: ({ id, status, replacement }: { id: number; status: DestinationStatus; replacement?: number }) =>
      api.patch(`/business/offers/${offerId}/destinations/${id}`, {
        status,
        replacement_primary_id: replacement,
      }),
    onSuccess: (_data, variables) => {
      invalidate();
      setDisableTarget(null);
      addToast(variables.status === 'disabled' ? 'Страница отключена' : 'Страница включена', 'success');
    },
    onError: (error) => addToast(errorMessage(error, 'Не удалось изменить страницу'), 'error'),
  });

  const items = query.data?.items || [];
  const total = query.data?.total || 0;
  const pages = Math.max(1, Math.ceil(total / (query.data?.per_page || 20)));
  const legacyMessage = legacySkipMessage(query.data?.legacy_skip_reason);
  const activeReplacements = items.filter((item) => item.status === 'active' && !item.is_primary);

  const requestDisable = (item: OfferDestinationItem) => {
    if (item.is_primary && activeReplacements.length) {
      setDisableTarget(item);
      return;
    }
    setStatus.mutate({ id: item.id, status: 'disabled' });
  };

  return (
    <section className="ui-card overflow-x-auto">
      <div className="px-4 py-3 border-b border-border/70 flex items-center justify-between gap-3">
        <div>
          <h2 className="ui-section-title">Страницы для продвижения</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Партнёры создают ссылки только на опубликованные страницы. Условия оффера общие.
          </p>
        </div>
        <Button size="sm" onClick={() => setEditor('new')}>
          Добавить страницу
        </Button>
      </div>
      {query.isLoading ? (
        <p className="px-4 py-6 text-sm text-muted-foreground">Загрузка страниц…</p>
      ) : items.length === 0 ? (
        <div className="px-4 py-6 text-sm text-muted-foreground space-y-1">
          <p>Дополнительных страниц нет. Оффер продолжает работать с одной посадочной, если она задана.</p>
          {query.data?.legacy_product_url && <p className="break-all">{query.data.legacy_product_url}</p>}
          {legacyMessage && <p>{legacyMessage}</p>}
        </div>
      ) : (
        <table className="ui-table">
          <thead>
            <tr>
              <th>Название</th>
              <th>Тип</th>
              <th>URL</th>
              <th>Статус</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id}>
                <td className="font-medium">
                  <div>{item.title}</div>
                  {item.is_primary && <p className="text-xs text-muted-foreground mt-0.5">Основная</p>}
                </td>
                <td>{destinationTypeLabel(item.type)}</td>
                <td className="max-w-[240px] truncate" title={item.url}>
                  <a href={item.url} target="_blank" rel="noreferrer" className="text-primary hover:underline">
                    {shortDestinationUrl(item.url)}
                  </a>
                </td>
                <td>
                  <span className={cn('ui-badge', item.status === 'active' ? 'bg-accent text-primary' : 'bg-muted text-muted-foreground')}>
                    {item.status === 'active' ? 'Активна' : 'Отключена'}
                  </span>
                </td>
                <td className="text-right whitespace-nowrap">
                  <button type="button" className="text-sm text-primary mr-3" onClick={() => setEditor(item)}>
                    Изменить
                  </button>
                  {item.status === 'active' && !item.is_primary && (
                    <button type="button" className="text-sm text-primary mr-3" onClick={() => setPrimary.mutate(item.id)}>
                      Сделать основной
                    </button>
                  )}
                  {item.status === 'active' ? (
                    <button type="button" className="text-sm text-muted-foreground" onClick={() => requestDisable(item)}>
                      Отключить
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="text-sm text-primary"
                      onClick={() => setStatus.mutate({ id: item.id, status: 'active' })}
                    >
                      Включить
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {pages > 1 && (
        <div className="px-4 py-3 flex items-center justify-end gap-2 text-sm">
          <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>
            Назад
          </Button>
          <span className="text-muted-foreground">
            {page} / {pages}
          </span>
          <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}>
            Дальше
          </Button>
        </div>
      )}
      {editor && (
        <DestinationForm
          offerId={offerId}
          destination={editor === 'new' ? null : editor}
          onClose={() => setEditor(null)}
          onSaved={(warning) => {
            setEditor(null);
            invalidate();
            addToast('Страница сохранена', 'success');
            if (warning) addToast(warning, 'info');
          }}
        />
      )}
      {disableTarget && (
        <ReplacePrimaryDialog
          options={activeReplacements}
          onClose={() => setDisableTarget(null)}
          onConfirm={(replacement) =>
            setStatus.mutate({ id: disableTarget.id, status: 'disabled', replacement })
          }
        />
      )}
    </section>
  );
}

function DestinationForm({
  offerId,
  destination,
  onClose,
  onSaved,
}: {
  offerId: string;
  destination: OfferDestinationItem | null;
  onClose: () => void;
  onSaved: (warning?: string | null) => void;
}) {
  const [title, setTitle] = useState(destination?.title || '');
  const [url, setUrl] = useState(destination?.url || '');
  const [type, setType] = useState<DestinationType>(destination?.type || 'PRODUCT');
  const [imageUrl, setImageUrl] = useState(destination?.image_url || '');
  const [isPrimary, setIsPrimary] = useState(destination?.is_primary || false);
  const [formError, setFormError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => {
      if (destination?.is_primary && !isPrimary) {
        return Promise.reject({ error: { message: 'Сначала назначьте другую основную страницу.' } });
      }
      const body: Record<string, unknown> = {
        title: title.trim(),
        url: url.trim(),
        type,
        image_url: imageUrl.trim() || null,
      };
      if (!destination || isPrimary) body.is_primary = isPrimary;
      return destination
        ? api.patch<OfferDestinationItem>(`/business/offers/${offerId}/destinations/${destination.id}`, body)
        : api.post<OfferDestinationItem>(`/business/offers/${offerId}/destinations`, body);
    },
    onSuccess: (saved) => onSaved(saved.warning),
    onError: (error) => setFormError(errorMessage(error, 'Не удалось сохранить страницу')),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className="relative ui-card w-full max-w-lg p-5 space-y-4 shadow-soft">
        <div className="flex items-center justify-between">
          <h3 className="ui-section-title">{destination ? 'Изменить страницу' : 'Добавить страницу'}</h3>
          <button type="button" onClick={onClose} className="text-muted-foreground" aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>
        <label className="block">
          <span className="ui-label">Название</span>
          <input className="ui-input" value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>
        <label className="block">
          <span className="ui-label">URL</span>
          <input className="ui-input" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="https://" />
        </label>
        <label className="block">
          <span className="ui-label">Тип страницы</span>
          <select className="ui-input" value={type} onChange={(event) => setType(event.target.value as DestinationType)}>
            {TYPES.map((item) => (
              <option key={item} value={item}>
                {destinationTypeLabel(item)}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="ui-label">Изображение</span>
          <input
            className="ui-input"
            value={imageUrl}
            onChange={(event) => setImageUrl(event.target.value)}
            placeholder="Необязательно"
          />
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={isPrimary} onChange={(event) => setIsPrimary(event.target.checked)} />
          Основная страница
        </label>
        {destination && <p className="text-xs text-muted-foreground">Уже созданные ссылки сохраняют свой URL.</p>}
        {formError && <p className="text-sm text-destructive">{formError}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button disabled={!title.trim() || !url.trim() || save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? 'Сохранение...' : 'Сохранить'}
          </Button>
        </div>
      </div>
    </div>
  );
}

function ReplacePrimaryDialog({
  options,
  onClose,
  onConfirm,
}: {
  options: OfferDestinationItem[];
  onClose: () => void;
  onConfirm: (replacementId: number) => void;
}) {
  const [replacement, setReplacement] = useState(String(options[0]?.id || ''));
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className="relative ui-card w-full max-w-md p-5 space-y-4 shadow-soft">
        <h3 className="ui-section-title">Выберите новую основную страницу</h3>
        <p className="text-sm text-muted-foreground">
          Отключение основной страницы не меняет уже созданные ссылки, но новым ссылкам нужен другой адрес по умолчанию.
        </p>
        <select className="ui-input" value={replacement} onChange={(event) => setReplacement(event.target.value)}>
          {options.map((item) => (
            <option key={item.id} value={item.id}>
              {item.title}
            </option>
          ))}
        </select>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button disabled={!replacement} onClick={() => onConfirm(Number(replacement))}>
            Отключить
          </Button>
        </div>
      </div>
    </div>
  );
}
