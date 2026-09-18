import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import { api } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/utils/cn';
import { LegalEntityLookup } from '@/shared/finance/LegalEntityLookup';
import {
  type LegalEntityCandidate,
  type LookupContext,
  lookupEnabledForSubject,
  registryIdLine,
} from '@/shared/finance/lookup';
import { financeApiErrorText } from '@/shared/finance/messages';
import {
  isUnsupportedPartnerIndividual,
  legalEntityWritePayload,
  nextTaxStatusOnSubjectChange,
  partnerLegalFormError,
  subjectTypeOptions,
  taxStatusOptions,
  UNSUPPORTED_PARTNER_INDIVIDUAL_MESSAGE,
  verificationStatusClass,
  verificationStatusLabel,
} from '@/shared/finance/legalEntity';

export interface LegalEntityFormValue {
  id?: number;
  subject_type: string;
  tax_status: string;
  country: string;
  legal_name: string;
  first_name: string;
  last_name: string;
  middle_name: string;
  inn: string;
  kpp?: string;
  ogrn: string;
  ogrnip: string;
  legal_address: string;
  verification_status?: string;
  verification_reason?: string | null;
  verification_reason_code?: string | null;
  lookup_provider?: string | null;
  lookup_invalid?: boolean;
}

const EMPTY: LegalEntityFormValue = {
  subject_type: 'LEGAL_ENTITY',
  tax_status: 'UNKNOWN',
  country: 'RU',
  legal_name: '',
  first_name: '',
  last_name: '',
  middle_name: '',
  inn: '',
  kpp: '',
  ogrn: '',
  ogrnip: '',
  legal_address: '',
};

function hasIdentity(value?: Partial<LegalEntityFormValue> | null) {
  return Boolean(value?.inn && (value.legal_name || value.last_name));
}

export function LegalEntityForm({
  value,
  pending,
  onSave,
  className,
  context,
  onLookupApplied,
}: {
  value?: Partial<LegalEntityFormValue> | null;
  pending?: boolean;
  onSave: (payload: ReturnType<typeof legalEntityWritePayload>) => void;
  className?: string;
  context: LookupContext;
  onLookupApplied?: () => void;
}) {
  const [form, setForm] = useState<LegalEntityFormValue>({ ...EMPTY, ...value });
  const [manual, setManual] = useState(false);
  const [selected, setSelected] = useState(hasIdentity(value));
  const [lookupPending, setLookupPending] = useState(false);
  const [lookupError, setLookupError] = useState('');
  const [formError, setFormError] = useState('');

  useEffect(() => {
    setForm({ ...EMPTY, ...value });
    if (hasIdentity(value)) setSelected(true);
  }, [value]);

  const set = (key: keyof LegalEntityFormValue, next: string) => {
    setForm((current) => ({ ...current, [key]: next }));
    setFormError('');
  };
  const changeSubjectType = (nextType: string) => {
    if (!nextType) return;
    const nextTax = nextTaxStatusOnSubjectChange(context, nextType, form.tax_status);
    setForm((current) => ({ ...current, subject_type: nextType, tax_status: nextTax }));
    setFormError('');
    if (lookupEnabledForSubject(context, nextType)) {
      setSelected(false);
      setManual(false);
    }
  };
  const save = (submit: boolean) => {
    if (context === 'partner') {
      const error = partnerLegalFormError(form, submit);
      if (error) {
        setFormError(error);
        return;
      }
    }
    onSave(legalEntityWritePayload(form, submit));
  };
  const status = form.verification_status || 'DRAFT';
  const lookupEnabled = lookupEnabledForSubject(context, form.subject_type);
  const registryLocked = Boolean(form.lookup_provider) && selected && !manual;
  const showLookup = lookupEnabled && !selected && !manual;
  const allowedTypes = subjectTypeOptions(context);
  const taxOptions = taxStatusOptions(context, form.subject_type, form.tax_status);
  const unsupportedIndividual = context === 'partner' && isUnsupportedPartnerIndividual(form.subject_type, form.tax_status);
  const npdLocked = context === 'partner' && form.subject_type === 'INDIVIDUAL' && form.tax_status === 'NPD';
  const typeSelectValue = unsupportedIndividual ? '' : form.subject_type;

  const applyCandidate = async (candidate: LegalEntityCandidate) => {
    setLookupError('');
    setLookupPending(true);
    try {
      const result = await api.post<{ legal_entity: LegalEntityFormValue }>(
        '/legal-entity-lookup/select',
        { candidate_id: candidate.candidate_id, target_context: context },
      );
      setForm({ ...EMPTY, ...result.legal_entity });
      setSelected(true);
      setManual(false);
      onLookupApplied?.();
    } catch (err) {
      setLookupError(financeApiErrorText(err, 'Не удалось выбрать организацию'));
    } finally {
      setLookupPending(false);
    }
  };

  const typeField = (
    <label className="space-y-1 min-w-0">
      <span className="ui-label">Тип</span>
      <select
        className="ui-input"
        value={typeSelectValue}
        disabled={registryLocked}
        onChange={(e) => changeSubjectType(e.target.value)}
      >
        {unsupportedIndividual ? <option value="">Выберите тип</option> : null}
        {allowedTypes.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <div className={cn('ui-card p-5 space-y-4 min-w-0', className)}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="ui-section-title">Юридические данные</h2>
        <span className={cn('ui-badge shrink-0', verificationStatusClass(status))}>
          {verificationStatusLabel(status)}
        </span>
      </div>
      <VerificationBanner status={status} reason={form.verification_reason} />
      {unsupportedIndividual ? (
        <div className="flex gap-2.5 rounded-lg border border-warning/30 bg-orange-50 px-3 py-2 text-sm text-warning">
          <AlertTriangle size={16} className="shrink-0 mt-0.5" aria-hidden />
          <div className="min-w-0">
            <p className="font-medium">{UNSUPPORTED_PARTNER_INDIVIDUAL_MESSAGE}</p>
            <p className="text-warning/80">Выберите самозанятого / НПД, ИП или юридическое лицо.</p>
          </div>
        </div>
      ) : null}
      {lookupError ? <p className="text-sm text-destructive">{lookupError}</p> : null}
      {formError ? <p className="text-sm text-destructive">{formError}</p> : null}

      {showLookup ? (
        <>
          {typeField}
          <LegalEntityLookup
            context={context}
            subjectType={form.subject_type}
            onSelect={applyCandidate}
            onManual={() => setManual(true)}
            selecting={lookupPending}
          />
        </>
      ) : null}

      {selected && !manual ? (
        <div className="rounded-lg border border-border/80 bg-muted/30 px-3 py-3 space-y-1">
          <p className="text-sm font-medium">✓ {form.legal_name || [form.last_name, form.first_name].filter(Boolean).join(' ')}</p>
          <p className="text-xs text-muted-foreground">
            {registryIdLine({
              inn: form.inn,
              ogrn: form.ogrn,
              ogrnip: form.ogrnip,
              subject_type: form.subject_type,
            })}
          </p>
          {form.legal_address ? <p className="text-xs text-muted-foreground">{form.legal_address}</p> : null}
          {lookupEnabled ? (
            <button
              type="button"
              className="text-sm text-primary pt-1"
              onClick={() => {
                setSelected(false);
                setManual(false);
              }}
            >
              Изменить организацию
            </button>
          ) : null}
        </div>
      ) : null}

      {(!showLookup || selected || manual || !lookupEnabled) && (
        <div className="grid grid-cols-1 min-[900px]:grid-cols-2 gap-x-4 gap-y-4">
          {typeField}
          <label className="space-y-1 min-w-0">
            <span className="ui-label">Налоговый статус</span>
            <select
              className="ui-input"
              value={form.tax_status}
              disabled={npdLocked || unsupportedIndividual}
              onChange={(e) => set('tax_status', e.target.value)}
            >
              {taxOptions.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 min-w-0 col-span-full">
            <span className="ui-label">Наименование</span>
            <input className="ui-input" value={form.legal_name} disabled={registryLocked} onChange={(e) => set('legal_name', e.target.value)} />
          </label>
          {form.subject_type !== 'LEGAL_ENTITY' && (
            <>
              <label className="space-y-1 min-w-0">
                <span className="ui-label">Имя</span>
                <input className="ui-input" value={form.first_name} disabled={registryLocked && Boolean(form.first_name)} onChange={(e) => set('first_name', e.target.value)} />
              </label>
              <label className="space-y-1 min-w-0">
                <span className="ui-label">Фамилия</span>
                <input className="ui-input" value={form.last_name} disabled={registryLocked && Boolean(form.last_name)} onChange={(e) => set('last_name', e.target.value)} />
              </label>
            </>
          )}
          <label className="space-y-1 min-w-0">
            <span className="ui-label">
              ИНН
              {form.subject_type === 'LEGAL_ENTITY' ? ' (10 цифр)' : ' (12 цифр)'}
            </span>
            <input
              className="ui-input"
              inputMode="numeric"
              maxLength={form.subject_type === 'LEGAL_ENTITY' ? 10 : 12}
              value={form.inn}
              disabled={registryLocked}
              onChange={(e) => set('inn', e.target.value)}
            />
          </label>
          {form.subject_type === 'LEGAL_ENTITY' && (
            <label className="space-y-1 min-w-0">
              <span className="ui-label">ОГРН (13 цифр)</span>
              <input className="ui-input" inputMode="numeric" maxLength={13} value={form.ogrn} disabled={registryLocked} onChange={(e) => set('ogrn', e.target.value)} />
            </label>
          )}
          {form.subject_type === 'SOLE_PROPRIETOR' && (
            <label className="space-y-1 min-w-0">
              <span className="ui-label">ОГРНИП (15 цифр)</span>
              <input className="ui-input" inputMode="numeric" maxLength={15} value={form.ogrnip} disabled={registryLocked} onChange={(e) => set('ogrnip', e.target.value)} />
            </label>
          )}
          <label className="space-y-1 min-w-0 col-span-full">
            <span className="ui-label">Юридический адрес</span>
            <textarea
              className="ui-input min-h-[80px] h-20 py-2"
              value={form.legal_address}
              disabled={registryLocked && Boolean(form.legal_address)}
              onChange={(e) => set('legal_address', e.target.value)}
            />
          </label>
        </div>
      )}

      {(!showLookup || selected || manual || !lookupEnabled) && (
        <div className="flex flex-wrap gap-2 pt-1">
          <Button type="button" variant="secondary" disabled={pending || lookupPending} onClick={() => save(false)}>
            Сохранить черновик
          </Button>
          <Button type="button" disabled={pending || lookupPending} onClick={() => save(true)}>
            Отправить на проверку
          </Button>
        </div>
      )}
    </div>
  );
}

function VerificationBanner({ status, reason }: { status: string; reason?: string | null }) {
  if (status === 'REJECTED') {
    return (
      <div className="flex gap-2.5 rounded-lg border border-destructive/30 bg-red-50 px-3 py-2 text-sm text-destructive">
        <AlertTriangle size={16} className="shrink-0 mt-0.5" aria-hidden />
        <div className="min-w-0">
          <p className="font-medium">Юридические данные отклонены</p>
          {reason ? <p className="text-destructive/80">{reason}</p> : null}
          <p className="text-destructive/80">Исправьте данные и отправьте на проверку повторно.</p>
        </div>
      </div>
    );
  }
  if (status === 'PENDING_VERIFICATION' || status === 'REVIEW_REQUIRED') {
    return (
      <div className="flex gap-2.5 rounded-lg border border-warning/30 bg-orange-50 px-3 py-2 text-sm text-warning">
        <Info size={16} className="shrink-0 mt-0.5" aria-hidden />
        <div className="min-w-0">
          <p className="font-medium">Данные проверяются</p>
          <p className="text-warning/80">Финансовые операции станут доступны после подтверждения.</p>
        </div>
      </div>
    );
  }
  if (status === 'VERIFIED') {
    return (
      <div className="flex items-center gap-2.5 rounded-lg border border-success/30 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
        <CheckCircle2 size={16} className="shrink-0" aria-hidden />
        <p className="font-medium">Юридические данные подтверждены</p>
      </div>
    );
  }
  if (status === 'BLOCKED') {
    return (
      <div className="flex items-center gap-2.5 rounded-lg border border-destructive/30 bg-red-50 px-3 py-2 text-sm text-destructive">
        <AlertTriangle size={16} className="shrink-0" aria-hidden />
        <p className="font-medium">Юридические данные заблокированы</p>
      </div>
    );
  }
  return null;
}
