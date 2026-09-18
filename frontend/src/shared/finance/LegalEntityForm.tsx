import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { cn } from '@/shared/utils/cn';
import { legalEntityWritePayload, verificationStatusClass, verificationStatusLabel } from '@/shared/finance/legalEntity';

export interface LegalEntityFormValue {
  subject_type: string;
  tax_status: string;
  country: string;
  legal_name: string;
  first_name: string;
  last_name: string;
  middle_name: string;
  inn: string;
  ogrn: string;
  ogrnip: string;
  legal_address: string;
  verification_status?: string;
  verification_reason?: string | null;
  verification_reason_code?: string | null;
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
  ogrn: '',
  ogrnip: '',
  legal_address: '',
};

export function LegalEntityForm({
  value,
  pending,
  onSave,
  className,
}: {
  value?: Partial<LegalEntityFormValue> | null;
  pending?: boolean;
  onSave: (payload: ReturnType<typeof legalEntityWritePayload>) => void;
  className?: string;
}) {
  const [form, setForm] = useState<LegalEntityFormValue>({ ...EMPTY, ...value });
  useEffect(() => {
    setForm({ ...EMPTY, ...value });
  }, [value]);

  const set = (key: keyof LegalEntityFormValue, next: string) => {
    setForm((current) => ({ ...current, [key]: next }));
  };
  const status = form.verification_status || 'DRAFT';

  return (
    <div className={cn('ui-card p-5 space-y-4 min-w-0', className)}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="ui-section-title">Юридические данные</h2>
        <span className={cn('ui-badge shrink-0', verificationStatusClass(status))}>
          {verificationStatusLabel(status)}
        </span>
      </div>
      <VerificationBanner
        status={status}
        reason={form.verification_reason}
      />
      <div className="grid grid-cols-1 min-[900px]:grid-cols-2 gap-x-4 gap-y-4">
        <label className="space-y-1 min-w-0">
          <span className="ui-label">Тип</span>
          <select className="ui-input" value={form.subject_type} onChange={(e) => set('subject_type', e.target.value)}>
            <option value="INDIVIDUAL">Физлицо / самозанятый</option>
            <option value="SOLE_PROPRIETOR">ИП</option>
            <option value="LEGAL_ENTITY">Юридическое лицо</option>
          </select>
        </label>
        <label className="space-y-1 min-w-0">
          <span className="ui-label">Налоговый статус</span>
          <select className="ui-input" value={form.tax_status} onChange={(e) => set('tax_status', e.target.value)}>
            <option value="UNKNOWN">Не указан</option>
            <option value="NPD">НПД</option>
            <option value="USN">УСН</option>
            <option value="OSN">ОСН</option>
            <option value="PATENT">Патент</option>
            <option value="OTHER">Другой</option>
          </select>
        </label>
        <label className="space-y-1 min-w-0 col-span-full">
          <span className="ui-label">Наименование</span>
          <input className="ui-input" value={form.legal_name} onChange={(e) => set('legal_name', e.target.value)} />
        </label>
        <label className="space-y-1 min-w-0">
          <span className="ui-label">Имя</span>
          <input className="ui-input" value={form.first_name} onChange={(e) => set('first_name', e.target.value)} />
        </label>
        <label className="space-y-1 min-w-0">
          <span className="ui-label">Фамилия</span>
          <input className="ui-input" value={form.last_name} onChange={(e) => set('last_name', e.target.value)} />
        </label>
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
            onChange={(e) => set('inn', e.target.value)}
          />
        </label>
        {form.subject_type === 'LEGAL_ENTITY' && (
          <label className="space-y-1 min-w-0">
            <span className="ui-label">ОГРН (13 цифр)</span>
            <input
              className="ui-input"
              inputMode="numeric"
              maxLength={13}
              value={form.ogrn}
              onChange={(e) => set('ogrn', e.target.value)}
            />
          </label>
        )}
        {form.subject_type === 'SOLE_PROPRIETOR' && (
          <label className="space-y-1 min-w-0">
            <span className="ui-label">ОГРНИП (15 цифр)</span>
            <input
              className="ui-input"
              inputMode="numeric"
              maxLength={15}
              value={form.ogrnip}
              onChange={(e) => set('ogrnip', e.target.value)}
            />
          </label>
        )}
        <label className="space-y-1 min-w-0 col-span-full">
          <span className="ui-label">Юридический адрес</span>
          <textarea className="ui-input min-h-[80px] h-20 py-2" value={form.legal_address} onChange={(e) => set('legal_address', e.target.value)} />
        </label>
      </div>
      <div className="flex flex-wrap gap-2 pt-1">
        <Button type="button" variant="secondary" disabled={pending} onClick={() => onSave(legalEntityWritePayload(form, false))}>
          Сохранить черновик
        </Button>
        <Button type="button" disabled={pending} onClick={() => onSave(legalEntityWritePayload(form, true))}>
          Отправить на проверку
        </Button>
      </div>
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
