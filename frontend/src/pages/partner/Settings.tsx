import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { Skeleton } from '@/shared/components/Skeleton';
import { Button } from '@/shared/components/Button';
import { useToast } from '@/shared/components/Toast';
import { useState, useEffect } from 'react';

interface PartnerSettingsData {
  display_name: string;
  website: string;
  description: string;
  payout_method: string;
  payout_details: string;
  min_payout: number;
}

export function PartnerSettings() {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState<PartnerSettingsData>({
    display_name: '',
    website: '',
    description: '',
    payout_method: 'bank_transfer',
    payout_details: '',
    min_payout: 1000,
  });

  const { data, isLoading } = useQuery<PartnerSettingsData>({
    queryKey: ['partner', 'settings'],
    queryFn: () => api.get('/partner/settings'),
  });

  useEffect(() => {
    if (data) setFormData(data);
  }, [data]);

  const updateSettings = useMutation({
    mutationFn: (settings: PartnerSettingsData) => api.patch('/partner/settings', settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['partner', 'settings'] });
      addToast('Настройки сохранены', 'success');
    },
    onError: () => addToast('Ошибка сохранения настроек', 'error'),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateSettings.mutate(formData);
  };

  if (isLoading) {
    return (
      <div className="space-y-5">
        <h1 className="ui-page-title">Настройки</h1>
        <Skeleton className="h-96 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <h1 className="ui-page-title">Настройки</h1>

      <form onSubmit={handleSubmit} className="space-y-5 max-w-2xl">
        <div className="ui-card p-6 space-y-5">
          <h2 className="ui-section-title">Профиль партнёра</h2>

          <div>
            <label className="ui-label">Отображаемое имя</label>
            <input
              type="text"
              value={formData.display_name}
              onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
              className="ui-input"
            />
          </div>

          <div>
            <label className="ui-label">Сайт / канал</label>
            <input
              type="url"
              value={formData.website}
              onChange={(e) => setFormData({ ...formData, website: e.target.value })}
              className="ui-input"
              placeholder="https://"
            />
          </div>

          <div>
            <label className="ui-label">О себе</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="ui-input min-h-[80px] h-auto py-2"
              placeholder="Расскажите о своём опыте и каналах продвижения"
            />
          </div>
        </div>

        <div className="ui-card p-6 space-y-5">
          <h2 className="ui-section-title">Выплаты</h2>
          <p className="text-sm text-muted-foreground">Механизм выплат скоро появится.</p>

          <div>
            <label className="ui-label">Способ выплат</label>
            <select
              value={formData.payout_method}
              onChange={(e) => setFormData({ ...formData, payout_method: e.target.value })}
              className="ui-input"
            >
              <option value="bank_transfer">Банковский перевод</option>
              <option value="card">На карту</option>
              <option value="sbp">СБП</option>
            </select>
          </div>

          <div>
            <label className="ui-label">Реквизиты</label>
            <textarea
              value={formData.payout_details}
              onChange={(e) => setFormData({ ...formData, payout_details: e.target.value })}
              className="ui-input min-h-[60px] h-auto py-2"
              placeholder="Укажите реквизиты для получения выплат"
            />
          </div>

          <div>
            <label className="ui-label">Минимальная сумма выплаты (₽)</label>
            <input
              type="number"
              value={formData.min_payout}
              onChange={(e) => setFormData({ ...formData, min_payout: Number(e.target.value) })}
              className="ui-input"
              min="100"
            />
          </div>
        </div>

        <Button type="submit" disabled={updateSettings.isPending}>
          {updateSettings.isPending ? 'Сохранение...' : 'Сохранить'}
        </Button>
      </form>
    </div>
  );
}
