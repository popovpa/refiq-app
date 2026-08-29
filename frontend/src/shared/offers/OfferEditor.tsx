import { useState, type ReactNode } from 'react';
import { Button } from '@/shared/components/Button';
import { OfferForm } from '@/shared/offers/OfferForm';
import { OfferFormSidebar } from '@/shared/offers/OfferFormSidebar';
import { canSubmitOffer, offerFormErrors } from '@/shared/offers/offerFormMeta';
import type { OfferFormValues } from '@/shared/offers/types';
import type { AiMarkedFields, AiRewriteField } from '@/shared/ai/types';

export function OfferEditor({
  title,
  backLabel,
  onBack,
  form,
  onChange,
  status,
  financialWarning,
  pending,
  secondaryLabel,
  primaryLabel,
  requireCommission,
  onCancel,
  onSecondary,
  onPrimary,
  tools,
  banner,
  aiMarked,
  rewriteSlot,
  imageFromWebsite,
}: {
  title: string;
  backLabel: string;
  onBack: () => void;
  form: OfferFormValues;
  onChange: (next: OfferFormValues) => void;
  status?: string | null;
  financialWarning?: boolean;
  pending: boolean;
  secondaryLabel: string;
  primaryLabel: string;
  requireCommission: boolean;
  onCancel: () => void;
  onSecondary: () => void;
  onPrimary: () => void;
  tools?: ReactNode;
  banner?: ReactNode;
  aiMarked?: AiMarkedFields;
  rewriteSlot?: (field: AiRewriteField) => ReactNode;
  imageFromWebsite?: boolean;
}) {
  const [attempted, setAttempted] = useState(false);
  const errors = attempted ? offerFormErrors(form, requireCommission) : {};

  const run = (action: () => void) => {
    setAttempted(true);
    if (!canSubmitOffer(form, requireCommission)) return;
    action();
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <button type="button" onClick={onBack} className="text-sm text-muted-foreground hover:text-primary">
          {backLabel}
        </button>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <h1 className="ui-page-title">{title}</h1>
          <div className="flex flex-wrap gap-2 lg:justify-end">
            {tools}
            <Button type="button" variant="ghost" disabled={pending} onClick={onCancel}>
              Отмена
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={pending}
              onClick={() => run(onSecondary)}
            >
              {secondaryLabel}
            </Button>
            <Button type="button" disabled={pending} onClick={() => run(onPrimary)}>
              {pending ? 'Сохранение...' : primaryLabel}
            </Button>
          </div>
        </div>
      </div>

      {banner}

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(260px,28%)]">
        <OfferForm
          form={form}
          onChange={onChange}
          errors={errors}
          financialWarning={financialWarning}
          aiMarked={aiMarked}
          rewriteSlot={rewriteSlot}
          imageFromWebsite={imageFromWebsite}
        />
        <aside className="lg:sticky lg:top-4">
          <OfferFormSidebar form={form} status={status} />
        </aside>
      </div>
    </div>
  );
}
