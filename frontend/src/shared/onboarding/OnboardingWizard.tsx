import { useState } from 'react';
import { Briefcase, Users } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { ConfirmDialog } from '@/shared/components/ConfirmDialog';
import { LegalEntityLookup } from '@/shared/finance/LegalEntityLookup';
import { cn } from '@/shared/utils/cn';
import { ONBOARDING_COUNTRIES, PARTNER_ONBOARDING_TYPES } from '@/shared/onboarding/constants';
import {
  applyCandidateToOrgForm,
  emptyOrgForm,
  orgFormHasEdits,
  splitFio,
  type OrgOnboardingForm,
  type PartnerKind,
} from '@/shared/onboarding/flow';
import { OnboardingOrgForm } from '@/shared/onboarding/OnboardingOrgForm';
import { type OrgFormErrors, validateOrgOnboardingForm } from '@/shared/onboarding/validation';
import type { ActivateBusinessPayload, ActivatePartnerPayload } from '@/shared/api/roles';

type Step = 'choose' | 'partner-type' | 'search' | 'form' | 'self-employed';

export function OnboardingWizard({
  userEmail,
  userName,
  userPhone,
  pending,
  error,
  startAt,
  onError,
  onSaveBusiness,
  onSavePartner,
  onBack,
}: {
  userEmail?: string;
  userName?: string;
  userPhone?: string;
  pending?: boolean;
  error?: string;
  startAt?: 'choose' | 'business' | 'partner';
  onError: (message: string) => void;
  onSaveBusiness: (payload: ActivateBusinessPayload) => void;
  onSavePartner: (payload: ActivatePartnerPayload) => void;
  onBack?: () => void;
}) {
  const [step, setStep] = useState<Step>(startAt === 'business' ? 'search' : startAt === 'partner' ? 'partner-type' : 'choose');
  const [mode, setMode] = useState<'business' | 'partner' | null>(startAt === 'choose' || !startAt ? null : startAt);
  const [partnerKind, setPartnerKind] = useState<PartnerKind | null>(null);
  const [form, setForm] = useState<OrgOnboardingForm>(() =>
    emptyOrgForm({
      work_email: userEmail || '',
      phone: userPhone || '',
      contact_name: userName || '',
    }),
  );
  const [snapshot, setSnapshot] = useState<OrgOnboardingForm | null>(null);
  const [errors, setErrors] = useState<OrgFormErrors>({});
  const [confirmSearch, setConfirmSearch] = useState(false);

  const context = mode === 'partner' ? 'partner' : 'business';
  const searchSubject = partnerKind && partnerKind !== 'INDIVIDUAL' ? partnerKind : undefined;

  const patch = (next: Partial<OrgOnboardingForm>) => {
    setForm((current) => ({ ...current, ...next }));
    setErrors({});
    onError('');
  };

  const goBackToSearch = () => {
    if (snapshot && orgFormHasEdits(form, snapshot)) {
      setConfirmSearch(true);
      return;
    }
    setStep('search');
  };

  const saveOrg = () => {
    const nextErrors = validateOrgOnboardingForm(form, { context });
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    const fio = splitFio(form.contact_name);
    if (mode === 'partner') {
      onSavePartner({
        subject_type: form.subject_type,
        legal_name: form.legal_name,
        first_name: fio.first_name || form.first_name,
        last_name: fio.last_name || form.last_name,
        middle_name: fio.middle_name,
        inn: form.inn,
        ogrn: form.ogrn,
        ogrnip: form.ogrnip,
        legal_address: form.legal_address,
        country: form.country,
        phone: form.phone,
        contact_name: form.contact_name,
        candidate_id: form.candidate_id,
      });
      return;
    }
    onSaveBusiness({
      name: form.legal_name || form.contact_name,
      website: form.website,
      country: form.country,
      work_email: form.work_email,
      phone: form.phone,
      subject_type: form.subject_type,
      legal_name: form.legal_name,
      inn: form.inn,
      ogrn: form.ogrn,
      ogrnip: form.ogrnip,
      legal_address: form.legal_address,
      contact_name: form.contact_name,
      job_title: form.job_title,
      candidate_id: form.candidate_id,
    });
  };

  const saveSelfEmployed = () => {
    const nextErrors = validateOrgOnboardingForm(form, { context: 'partner', selfEmployed: true });
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    const fio = splitFio(form.contact_name);
    onSavePartner({
      subject_type: 'INDIVIDUAL',
      tax_status: 'NPD',
      first_name: fio.first_name,
      last_name: fio.last_name,
      middle_name: fio.middle_name,
      inn: form.inn,
      country: form.country,
      city: form.city,
      phone: form.phone,
      contact_name: form.contact_name,
    });
  };

  return (
    <div className="space-y-5">
      {error ? <div className="bg-destructive/10 text-destructive text-sm p-3 rounded-lg">{error}</div> : null}

      {step === 'choose' ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <ChoiceCard
            icon={Users}
            title="Партнёр"
            description="Продвигайте офферы компаний и получайте комиссию с конверсий."
            action="Стать партнёром"
            disabled={pending}
            onClick={() => {
              setMode('partner');
              setStep('partner-type');
              onError('');
            }}
          />
          <ChoiceCard
            icon={Briefcase}
            title="Бизнес"
            description="Создавайте офферы, подключайте партнёров и развивайте продажи."
            action="Стать бизнесом"
            disabled={pending}
            onClick={() => {
              setMode('business');
              setPartnerKind(null);
              setForm((current) => ({ ...current, subject_type: 'LEGAL_ENTITY' }));
              setStep('search');
              onError('');
            }}
          />
        </div>
      ) : null}

      {step === 'partner-type' ? (
        <div className="space-y-4">
          <div className="space-y-1 text-center sm:text-left">
            <h2 className="text-lg font-semibold">Как вы будете работать?</h2>
            <p className="text-sm text-muted-foreground">Самозанятый, ИП или юридическое лицо — обычное физлицо зарегистрировать нельзя.</p>
          </div>
          <div className="grid grid-cols-1 gap-2">
            {PARTNER_ONBOARDING_TYPES.map((item) => (
              <button
                key={item.value}
                type="button"
                disabled={pending}
                onClick={() => {
                  setPartnerKind(item.value);
                  setForm((current) => ({ ...current, subject_type: item.value, tax_status: item.value === 'INDIVIDUAL' ? 'NPD' : current.tax_status }));
                  setStep(item.value === 'INDIVIDUAL' ? 'self-employed' : 'search');
                }}
                className="ui-card p-4 text-left hover:border-primary/30 hover:bg-accent/40"
              >
                <p className="font-medium">{item.label}</p>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {step === 'search' ? (
        <LegalEntityLookup
          context={context}
          subjectType={searchSubject}
          heading="Найдите организацию"
          description="Введите название, ИНН или ОГРН — мы автоматически заполним основные реквизиты."
          onSelect={(candidate) => {
            const next = applyCandidateToOrgForm(
              { ...form, subject_type: candidate.subject_type || form.subject_type },
              candidate,
            );
            setForm(next);
            setSnapshot(next);
            setStep('form');
          }}
          onManual={() => {
            const next = {
              ...form,
              candidate_id: null,
              subject_type: partnerKind && partnerKind !== 'INDIVIDUAL' ? partnerKind : form.subject_type,
            };
            setForm(next);
            setSnapshot(next);
            setStep('form');
          }}
        />
      ) : null}

      {step === 'form' ? (
        <OnboardingOrgForm
          form={form}
          errors={errors}
          context={context}
          pending={pending}
          onChange={patch}
          onSave={saveOrg}
          onSearchAnother={goBackToSearch}
        />
      ) : null}

      {step === 'self-employed' ? (
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            saveSelfEmployed();
          }}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="block sm:col-span-2">
              <span className="ui-label">ФИО</span>
              <input className={cn('ui-input', errors.contact_name && 'border-destructive/50')} value={form.contact_name} onChange={(e) => patch({ contact_name: e.target.value })} />
              {errors.contact_name ? <span className="mt-1 block text-xs text-destructive">{errors.contact_name}</span> : null}
            </label>
            <label className="block">
              <span className="ui-label">ИНН</span>
              <input className={cn('ui-input', errors.inn && 'border-destructive/50')} inputMode="numeric" value={form.inn} onChange={(e) => patch({ inn: e.target.value })} />
              {errors.inn ? <span className="mt-1 block text-xs text-destructive">{errors.inn}</span> : null}
            </label>
            <label className="block">
              <span className="ui-label">Страна</span>
              <select className="ui-input" value={form.country} onChange={(e) => patch({ country: e.target.value })}>
                {ONBOARDING_COUNTRIES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="ui-label">Город</span>
              <input className="ui-input" value={form.city} onChange={(e) => patch({ city: e.target.value })} />
            </label>
            <label className="block">
              <span className="ui-label">Email</span>
              <input type="email" className={cn('ui-input', errors.work_email && 'border-destructive/50')} value={form.work_email} onChange={(e) => patch({ work_email: e.target.value })} />
              {errors.work_email ? <span className="mt-1 block text-xs text-destructive">{errors.work_email}</span> : null}
            </label>
            <label className="block sm:col-span-2">
              <span className="ui-label">Телефон</span>
              <input className={cn('ui-input', errors.phone && 'border-destructive/50')} value={form.phone} onChange={(e) => patch({ phone: e.target.value })} />
              {errors.phone ? <span className="mt-1 block text-xs text-destructive">{errors.phone}</span> : null}
            </label>
          </div>
          <Button type="submit" className="w-full" disabled={pending}>
            {pending ? 'Сохранение...' : 'Сохранить'}
          </Button>
        </form>
      ) : null}

      {step !== 'choose' ? (
        <Button
          type="button"
          variant="ghost"
          className="w-full"
          disabled={pending}
          onClick={() => {
            if (step === 'form' || step === 'self-employed' || step === 'search') {
              if (mode === 'partner' && (step === 'search' || step === 'self-employed' || step === 'form')) {
                setStep(step === 'form' ? 'search' : 'partner-type');
                return;
              }
              if (mode === 'business' && step === 'form') {
                goBackToSearch();
                return;
              }
            }
            if (onBack) onBack();
            else {
              setStep('choose');
              setMode(null);
              setPartnerKind(null);
            }
          }}
        >
          Назад
        </Button>
      ) : null}

      {confirmSearch ? (
        <ConfirmDialog
          title="Изменения не сохранены"
          confirmLabel="Продолжить поиск"
          cancelLabel="Остаться"
          onConfirm={() => {
            setConfirmSearch(false);
            setStep('search');
          }}
          onClose={() => setConfirmSearch(false)}
        >
          При выборе другой организации текущие изменения будут потеряны.
        </ConfirmDialog>
      ) : null}
    </div>
  );
}

function ChoiceCard({
  icon: Icon,
  title,
  description,
  action,
  disabled,
  onClick,
}: {
  icon: typeof Users;
  title: string;
  description: string;
  action: string;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'ui-card p-5 text-left space-y-4 transition-colors',
        'hover:border-primary/30 hover:bg-accent/40',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30',
        'disabled:pointer-events-none disabled:opacity-60',
      )}
    >
      <div className="w-9 h-9 rounded-md bg-accent text-primary flex items-center justify-center">
        <Icon size={18} />
      </div>
      <div className="space-y-1.5">
        <h2 className="text-base font-semibold">{title}</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
      </div>
      <span className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground">
        {action}
      </span>
    </button>
  );
}
