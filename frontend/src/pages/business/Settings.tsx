import { useEffect } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
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
import { BillingTab } from './settings/BillingTab';
import { LegalEntityForm, type LegalEntityFormValue } from '@/shared/finance/LegalEntityForm';
import { TestModeBanner } from '@/shared/finance/banners';
import type { LegalEntityWriteValue } from '@/shared/finance/legalEntity';
import { financeApiErrorText } from '@/shared/finance/messages';
import type {
  BusinessWorkspaceSettings,
  CompanyForm,
  DefaultsForm,
  IntegrationKind,
  SettingsTab,
} from './settings/types';
import {
  BUSINESS_SETTINGS_BILLING_PATH,
  isSettingsTab,
  settingsPathForTab,
  SETTINGS_TABS,
} from './settings/types';

function tabFromLocation(pathname: string, searchTab: string | null): SettingsTab {
  if (pathname === BUSINESS_SETTINGS_BILLING_PATH || searchTab === 'billing') {
    return 'billing';
  }
  if (isSettingsTab(searchTab) && searchTab !== 'billing') {
    return searchTab;
  }
  return 'company';
}

export function BusinessSettings() {
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const initialIntegration = searchParams.get('integration');
  const tab = tabFromLocation(location.pathname, searchParams.get('tab'));
  const integration: IntegrationKind | null =
    initialIntegration === 'postback' || initialIntegration === 'sdk' ? initialIntegration : null;

  // Canonicalize billing deep-link: ?tab=billing → /business/settings/billing
  useEffect(() => {
    if (location.pathname === '/business/settings' && searchParams.get('tab') === 'billing') {
      navigate(BUSINESS_SETTINGS_BILLING_PATH, { replace: true });
    }
  }, [location.pathname, navigate, searchParams]);

  const { data, isLoading } = useQuery<BusinessWorkspaceSettings>({
    queryKey: ['business', 'settings'],
    queryFn: () => api.get('/business/settings'),
  });
  const { data: legal, isLoading: legalLoading } = useQuery<{
    legal_entity: LegalEntityFormValue | null;
    financial_mode?: string;
  }>({
    queryKey: ['business', 'legal-entity'],
    queryFn: () => api.get('/business/legal-entity'),
    enabled: tab === 'legal',
  });

  const updateLegal = useMutation({
    mutationFn: (payload: LegalEntityWriteValue) => api.patch('/business/legal-entity', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['business', 'legal-entity'] });
      addToast('Юридические данные сохранены', 'success');
    },
    onError: (err) => addToast(financeApiErrorText(err, 'Не удалось сохранить юридические данные'), 'error'),
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
    navigate(settingsPathForTab(key));
    if (focus) {
      requestAnimationFrame(() => document.getElementById(`settings-tab-${key}`)?.focus());
    }
  };

  const onTabKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const index = SETTINGS_TABS.findIndex((item) => item.key === tab);
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      selectTab(SETTINGS_TABS[(index + 1) % SETTINGS_TABS.length].key, true);
    }
    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      selectTab(SETTINGS_TABS[(index - 1 + SETTINGS_TABS.length) % SETTINGS_TABS.length].key, true);
    }
  };

  const setIntegration = (kind: IntegrationKind | null) => {
    const next = new URLSearchParams(searchParams);
    if (kind) {
      next.set('tab', 'integrations');
      next.set('integration', kind);
    } else {
      next.delete('integration');
      if (!next.get('tab')) next.set('tab', 'integrations');
    }
    const query = next.toString();
    navigate(query ? `/business/settings?${query}` : '/business/settings');
  };

  if (isLoading || !data || (tab === 'legal' && legalLoading)) {
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
      {tab === 'legal' && <TestModeBanner visible={legal?.financial_mode === 'TEST'} />}
      <div
        className="flex gap-1 bg-muted rounded-md p-0.5 w-fit flex-wrap"
        role="tablist"
        aria-label="Разделы настроек"
        onKeyDown={onTabKeyDown}
      >
        {SETTINGS_TABS.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            id={`settings-tab-${item.key}`}
            aria-selected={tab === item.key}
            aria-controls={`settings-panel-${item.key}`}
            tabIndex={tab === item.key ? 0 : -1}
            className={cn(tabClass(tab === item.key), 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30')}
            onClick={() => selectTab(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`settings-panel-${tab}`} aria-labelledby={`settings-tab-${tab}`}>
        {tab === 'company' && (
          <CompanyTab data={data} pending={updateSettings.isPending} onSave={saveCompany} />
        )}
        {tab === 'legal' && (
          <LegalEntityForm
            context="business"
            value={legal?.legal_entity}
            pending={updateLegal.isPending}
            onSave={(payload) => updateLegal.mutate(payload)}
            onLookupApplied={() => queryClient.invalidateQueries({ queryKey: ['business', 'legal-entity'] })}
          />
        )}
        {tab === 'sites' && <SitesTab />}
        {tab === 'integrations' && (
          <IntegrationsTab onOpen={setIntegration} onManageSites={() => selectTab('sites')} />
        )}
        {tab === 'defaults' && (
          <DefaultsTab data={data} pending={updateSettings.isPending} onSave={saveDefaults} />
        )}
        {tab === 'billing' && <BillingTab />}
      </div>

      {integration && (
        <IntegrationDrawer kind={integration} website={data.website} onClose={() => setIntegration(null)} />
      )}
    </div>
  );
}
