import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { Skeleton } from '@/shared/components/Skeleton';
import { useToast } from '@/shared/components/Toast';
import { tabClass } from '@/shared/offers/labels';
import { cn } from '@/shared/utils/cn';
import { CompanyTab } from './settings/CompanyTab';
import { SitesTab } from './settings/SitesTab';
import { DefaultsTab } from './settings/DefaultsTab';
import { IntegrationDrawer } from './settings/IntegrationDrawer';
import { IntegrationsTab } from './settings/IntegrationsTab';
import type {
  BusinessWorkspaceSettings,
  CompanyForm,
  DefaultsForm,
  IntegrationKind,
  SettingsTab,
} from './settings/types';

const TABS: Array<{ key: SettingsTab; label: string }> = [
  { key: 'company', label: 'Компания' },
  { key: 'sites', label: 'Сайты' },
  { key: 'integrations', label: 'Интеграции' },
  { key: 'defaults', label: 'По умолчанию' },
];

export function BusinessSettings() {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const initialTab = searchParams.get('tab');
  const [tab, setTab] = useState<SettingsTab>(
    initialTab === 'sites' || initialTab === 'integrations' || initialTab === 'defaults' || initialTab === 'company'
      ? initialTab
      : 'company',
  );
  const [integration, setIntegration] = useState<IntegrationKind | null>(null);

  const { data, isLoading } = useQuery<BusinessWorkspaceSettings>({
    queryKey: ['business', 'settings'],
    queryFn: () => api.get('/business/settings'),
  });

  const updateSettings = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.patch('/business/settings', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['business', 'settings'] });
      addToast('Настройки сохранены', 'success');
    },
    onError: () => addToast('Ошибка сохранения настроек', 'error'),
  });

  const saveCompany = (form: CompanyForm) => {
    updateSettings.mutate({
      name: form.name,
      website: form.website,
      country: form.country || null,
      category: form.category || null,
      work_email: form.work_email || null,
      phone: form.phone || null,
      description: form.description || null,
      logo_url: form.logo_url,
    });
  };

  const saveDefaults = (form: DefaultsForm) => {
    updateSettings.mutate({
      currency: form.currency,
      default_attribution_window_days: Number(form.default_attribution_window_days) || 30,
      default_access_policy: form.default_access_policy,
      default_confirmation_days: Number(form.default_confirmation_days),
    });
  };

  const selectTab = (key: SettingsTab, focus = false) => {
    setTab(key);
    if (focus) {
      requestAnimationFrame(() => document.getElementById(`settings-tab-${key}`)?.focus());
    }
  };

  const onTabKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const index = TABS.findIndex((item) => item.key === tab);
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      selectTab(TABS[(index + 1) % TABS.length].key, true);
    }
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      selectTab(TABS[(index - 1 + TABS.length) % TABS.length].key, true);
    }
  };

  if (isLoading || !data) {
    return (
      <div className="space-y-5 max-w-[1280px]">
        <h1 className="ui-page-title">Настройки</h1>
        <Skeleton className="h-10 w-72 rounded-md" />
        <Skeleton className="h-96 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-5 max-w-[1280px]">
      <h1 className="ui-page-title">Настройки</h1>

      <div
        className="flex gap-1 bg-muted rounded-md p-0.5 w-fit"
        role="tablist"
        aria-label="Разделы настроек"
        onKeyDown={onTabKeyDown}
      >
        {TABS.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            id={`settings-tab-${item.key}`}
            aria-selected={tab === item.key}
            aria-controls={`settings-panel-${item.key}`}
            tabIndex={tab === item.key ? 0 : -1}
            className={cn(tabClass(tab === item.key), 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30')}
            onClick={() => setTab(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`settings-panel-${tab}`} aria-labelledby={`settings-tab-${tab}`}>
        {tab === 'company' && (
          <CompanyTab data={data} pending={updateSettings.isPending} onSave={saveCompany} />
        )}
        {tab === 'sites' && <SitesTab />}
        {tab === 'integrations' && (
          <IntegrationsTab onOpen={setIntegration} onManageSites={() => setTab('sites')} />
        )}
        {tab === 'defaults' && (
          <DefaultsTab data={data} pending={updateSettings.isPending} onSave={saveDefaults} />
        )}
      </div>

      {integration && (
        <IntegrationDrawer kind={integration} website={data.website} onClose={() => setIntegration(null)} />
      )}
    </div>
  );
}
