import type { ReactNode } from 'react';

export const OFFER_WIZARD_ASIDE_PX = 352;
export const OFFER_WIZARD_ASIDE_WIDE_PX = 360;
export const OFFER_WIZARD_ASIDE_MID_PX = 320;
export const OFFER_WIZARD_GAP_CLASS = 'gap-4 lg:gap-5';

export const OFFER_WIZARD_GRID_CLASS =
  'grid w-full min-w-0 items-start gap-4 lg:gap-5 max-md:grid-cols-1 md:grid-cols-[minmax(0,1fr)_320px] lg:grid-cols-[minmax(0,1fr)_352px] xl:grid-cols-[minmax(0,1fr)_360px]';

export function OfferWizardWorkspace({ children }: { children: ReactNode }) {
  return <div className="w-full min-w-0 space-y-3">{children}</div>;
}

export function OfferWizardHeader({
  title,
  backLabel,
  onBack,
}: {
  title: string;
  backLabel: string;
  onBack: () => void;
}) {
  return (
    <div className="space-y-3">
      <button type="button" onClick={onBack} className="text-sm text-muted-foreground hover:text-primary">
        {backLabel}
      </button>
      <h1 className="ui-page-title">{title}</h1>
    </div>
  );
}

export function OfferWizardGrid({
  stepper,
  main,
  aside,
}: {
  stepper: ReactNode;
  main: ReactNode;
  aside: ReactNode;
}) {
  return (
    <div className={OFFER_WIZARD_GRID_CLASS}>
      <OfferWizardMain>
        <OfferWizardStepper>{stepper}</OfferWizardStepper>
        {main}
      </OfferWizardMain>
      <OfferWizardAside>{aside}</OfferWizardAside>
    </div>
  );
}

export function OfferWizardMain({ children }: { children: ReactNode }) {
  return <div className="min-w-0 space-y-3">{children}</div>;
}

export function OfferWizardAside({ children }: { children: ReactNode }) {
  return <aside className="w-full min-w-0 space-y-3 md:sticky md:top-4">{children}</aside>;
}

export function OfferWizardStepper({ children }: { children: ReactNode }) {
  return <div className="w-full min-w-0">{children}</div>;
}

export function OfferWizardFormCard({ children }: { children: ReactNode }) {
  return <div className="ui-card min-w-0 space-y-4 p-4">{children}</div>;
}
