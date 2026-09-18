import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { Skeleton } from '@/shared/components/Skeleton';
import { Button } from '@/shared/components/Button';
import { useToast } from '@/shared/components/Toast';
import { useState, useEffect } from 'react';
import { LegalEntityForm, type LegalEntityFormValue } from '@/shared/finance/LegalEntityForm';
import { TestModeBanner } from '@/shared/finance/banners';
import { financeApiErrorText, financeReasonText } from '@/shared/finance/messages';
import type { LegalEntityWriteValue } from '@/shared/finance/legalEntity';

interface PartnerSettingsData {
  display_name: string;
  website: string;
  description: string;
  payout_method: string;
  payout_details: string;
  min_payout: number;
  payout_profile?: {
    payout_method: string;
    bank_account_masked?: string | null;
    bank_bik_masked?: string | null;
    bank_name?: string | null;
    status?: string;
  } | null;
  payout_eligibility?: { eligible: boolean; reason_code?: string | null; reason_message?: string | null };
}

export function PartnerSettings() {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    display_name: '',
    website: '',
    description: '',
    payout_method: 'bank_transfer',
    bank_account: '',
    bank_bik: '',
    bank_name: '',
  });

  const { data, isLoading } = useQuery<PartnerSettingsData>({
    queryKey: ['partner', 'settings'],
    queryFn: () => api.get('/partner/settings'),
  });
  const { data: legal } = useQuery<{
    legal_entity: LegalEntityFormValue | null;
    financial_mode?: string;
    payout_eligibility?: PartnerSettingsData['payout_eligibility'];
  }>({
    queryKey: ['partner', 'legal-entity'],
    queryFn: () => api.get('/partner/legal-entity'),
  });

  useEffect(() => {
    if (data) {
      setFormData((current) => ({
        ...current,
        display_name: data.display_name || '',
        website: data.website || '',
        description: data.description || '',
        payout_method: data.payout_method || data.payout_profile?.payout_method || 'bank_transfer',
        bank_name: data.payout_profile?.bank_name || '',
      }));
    }
  }, [data]);

  const updateSettings = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.patch('/partner/settings', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['partner', 'settings'] });
      addToast('Настройки сохранены', 'success');
    },
    onError: () => addToast('Ошибка сохранения настроек', 'error'),
  });
  const updateLegal = useMutation({
    mutationFn: (payload: LegalEntityWriteValue) => api.patch('/partner/legal-entity', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['partner', 'legal-entity'] });
      addToast('Юридические данные сохранены', 'success');
    },
    onError: (err) => addToast(financeApiErrorText(err, 'Не удалось сохранить юридические данные'), 'error'),
  });
  const updatePayout = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.patch('/partner/payout-profile', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['partner', 'payout-profile'] });
      queryClient.invalidateQueries({ queryKey: ['partner', 'settings'] });
      addToast('Реквизиты сохранены', 'success');
    },
    onError: () => addToast('Не удалось сохранить реквизиты', 'error'),
  });

  if (isLoading) {
    return (
      <div className="space-y-5 max-w-[1280px]">
        <h1 className="ui-page-title">Настройки</h1>
        <div className="grid grid-cols-1 gap-6 min-[900px]:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
          <Skeleton className="h-72 rounded-xl" />
          <Skeleton className="h-72 rounded-xl" />
        </div>
      </div>
    );
  }

  const eligibility = data?.payout_eligibility || legal?.payout_eligibility;

  return (
    <div className="space-y-5 max-w-[1280px]">
      <h1 className="ui-page-title">Настройки</h1>
      <TestModeBanner visible={legal?.financial_mode === 'TEST'} />

      <div className="grid grid-cols-1 gap-6 min-[900px]:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] min-[900px]:items-start">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            updateSettings.mutate({
              display_name: formData.display_name,
              website: formData.website,
              description: formData.description,
            });
          }}
          className="ui-card p-5 space-y-4 min-w-0"
        >
          <h2 className="ui-section-title">Профиль партнёра</h2>
          <div>
            <label className="ui-label" htmlFor="partner-display-name">Отображаемое имя</label>
            <input
              id="partner-display-name"
              type="text"
              value={formData.display_name}
              onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
              className="ui-input"
            />
          </div>
          <div>
            <label className="ui-label" htmlFor="partner-website">Сайт / канал</label>
            <input
              id="partner-website"
              type="url"
              value={formData.website}
              onChange={(e) => setFormData({ ...formData, website: e.target.value })}
              className="ui-input"
              placeholder="https://"
            />
          </div>
          <div>
            <label className="ui-label" htmlFor="partner-description">О себе</label>
            <textarea
              id="partner-description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="ui-input min-h-[80px] h-24 py-2"
            />
          </div>
          <Button type="submit" disabled={updateSettings.isPending}>
            {updateSettings.isPending ? 'Сохранение...' : 'Сохранить профиль'}
          </Button>
        </form>

        <LegalEntityForm
          context="partner"
          value={{ subject_type: 'INDIVIDUAL', ...(legal?.legal_entity || {}) }}
          pending={updateLegal.isPending}
          onSave={(payload) => updateLegal.mutate(payload)}
          onLookupApplied={() => queryClient.invalidateQueries({ queryKey: ['partner', 'legal-entity'] })}
        />
      </div>

      <div className="ui-card p-5 space-y-4">
        <h2 className="ui-section-title">Реквизиты для выплат</h2>
        <p className="text-sm text-muted-foreground">
          Минимальная выплата — {data?.min_payout?.toLocaleString('ru-RU') || 500} ₽. RefIQ не хранит ваши деньги.
        </p>
        {eligibility && !eligibility.eligible && (
          <p className="text-sm text-warning">{financeReasonText(eligibility.reason_code, eligibility.reason_message)}</p>
        )}
        {data?.payout_profile?.bank_account_masked && (
          <p className="text-sm text-muted-foreground">Текущий счёт: {data.payout_profile.bank_account_masked}</p>
        )}
        <div className="grid grid-cols-1 min-[900px]:grid-cols-2 gap-x-4 gap-y-4">
          <div className="min-w-0">
            <label className="ui-label" htmlFor="partner-payout-method">Способ выплат</label>
            <select
              id="partner-payout-method"
              value={formData.payout_method}
              onChange={(e) => setFormData({ ...formData, payout_method: e.target.value })}
              className="ui-input"
            >
              <option value="bank_transfer">Банковский перевод</option>
              <option value="sbp">СБП</option>
            </select>
          </div>
          <div className="min-w-0">
            <label className="ui-label" htmlFor="partner-bank-account">Расчётный счёт</label>
            <input
              id="partner-bank-account"
              className="ui-input"
              value={formData.bank_account}
              onChange={(e) => setFormData({ ...formData, bank_account: e.target.value })}
              placeholder="20 цифр"
            />
          </div>
          <div className="min-w-0">
            <label className="ui-label" htmlFor="partner-bank-bik">БИК</label>
            <input
              id="partner-bank-bik"
              className="ui-input"
              value={formData.bank_bik}
              onChange={(e) => setFormData({ ...formData, bank_bik: e.target.value })}
              placeholder="9 цифр"
            />
          </div>
          <div className="min-w-0">
            <label className="ui-label" htmlFor="partner-bank-name">Банк</label>
            <input
              id="partner-bank-name"
              className="ui-input"
              value={formData.bank_name}
              onChange={(e) => setFormData({ ...formData, bank_name: e.target.value })}
            />
          </div>
        </div>
        <Button
          type="button"
          disabled={updatePayout.isPending}
          onClick={() =>
            updatePayout.mutate({
              payout_method: formData.payout_method,
              bank_account: formData.bank_account,
              bank_bik: formData.bank_bik,
              bank_name: formData.bank_name,
            })
          }
        >
          Сохранить реквизиты
        </Button>
      </div>
    </div>
  );
}
