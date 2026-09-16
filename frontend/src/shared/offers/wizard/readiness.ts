import type { OfferFormValues } from '@/shared/offers/types';
import { offerFormErrors } from '@/shared/offers/offerFormMeta';
import type { WizardStepId } from '@/shared/offers/wizard/meta';

export type ReadinessItem = {
  id: WizardStepId;
  label: string;
  required: boolean;
  done: boolean;
  current?: boolean;
};

export function stepComplete(form: OfferFormValues, step: Exclude<WizardStepId, 'review'>): boolean {
  const errors = offerFormErrors(form, true);
  if (step === 'basics') {
    return !errors.name && !errors.category && !errors.description && !errors.partner_notes && !errors.access_policy;
  }
  if (step === 'traffic') {
    return !errors.geo_countries && !errors.allowed_traffic;
  }
  return !errors.conversion_type && !errors.commission_value && !errors.attribution_window_days && !errors.hold_period_days;
}

export function offerReadiness(form: OfferFormValues, current: WizardStepId): ReadinessItem[] {
  return [
    { id: 'basics', label: 'Основное', required: true, done: stepComplete(form, 'basics'), current: current === 'basics' },
    { id: 'traffic', label: 'Трафик', required: true, done: stepComplete(form, 'traffic'), current: current === 'traffic' },
    {
      id: 'conversions',
      label: 'Конверсии',
      required: true,
      done: stepComplete(form, 'conversions'),
      current: current === 'conversions',
    },
    {
      id: 'review',
      label: 'Проверка',
      required: true,
      done: canPublishOffer(form),
      current: current === 'review',
    },
  ];
}

export function readinessPercent(form: OfferFormValues): number {
  const done = (['basics', 'traffic', 'conversions'] as const).filter((step) => stepComplete(form, step)).length;
  return done * 25;
}

export function canPublishOffer(form: OfferFormValues): boolean {
  return stepComplete(form, 'basics') && stepComplete(form, 'traffic') && stepComplete(form, 'conversions');
}
