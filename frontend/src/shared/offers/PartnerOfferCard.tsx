import { type KeyboardEvent, type ReactNode } from 'react';
import { ArrowRight, BarChart3, Globe, GraduationCap, Lock, ShoppingCart, Tag, TrendingUp } from 'lucide-react';
import { findCategory, resolveCategoryCode } from '@/shared/catalog/categories';
import { OWN_OFFER_PROMOTE_PENDING_LABEL } from '@/shared/offers/promoteOwnOffer';
import { partnerAccessCta } from '@/shared/offers/partnerAccessCta';
import { conversionLabel } from '@/shared/offers/labels';
import type { OfferListItem } from '@/shared/offers/types';
import {
  formatCommissionContext,
  formatCommissionPrimary,
  formatOfferCr,
  formatOfferEpc,
  formatOfferGeo,
  offerCardAccessLabel,
  offerCardCategoryName,
  offerCardMetricValue,
  offerCardTitle,
} from '@/shared/offers/partnerOfferCardFormat';
import { cn } from '@/shared/utils/cn';

interface PartnerOfferCardProps {
  offer: OfferListItem;
  joinPending: boolean;
  promoteOwnPending?: boolean;
  onOpen: (offerId: OfferListItem['id']) => void;
  onGetLink: (offer: OfferListItem) => void;
  onJoinOpen: (offer: OfferListItem) => void;
  onRequestAccess: (offer: OfferListItem) => void;
  onPromoteOwn?: (offer: OfferListItem) => void;
}

export function PartnerOfferCard({
  offer,
  joinPending,
  promoteOwnPending = false,
  onOpen,
  onGetLink,
  onJoinOpen,
  onRequestAccess,
  onPromoteOwn,
}: PartnerOfferCardProps) {
  const rule = offer.commission_rules?.[0];
  const epc = formatOfferEpc(offer);
  const cr = formatOfferCr(offer);
  const categoryName = offerCardCategoryName(offer);
  const isOwn = Boolean(offer.is_own_offer);
  const cta = partnerAccessCta({
    isOwn,
    offerStatus: offer.status,
    accessPolicy: offer.access_policy,
    partnerStatus: offer.partner_status,
    rejectionReason: offer.rejection_reason,
  });
  const statusNote =
    cta.kind === 'rejected'
      ? [cta.note, cta.reason].filter(Boolean).join(': ')
      : cta.note || null;

  const handleKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onOpen(offer.id);
    }
  };

  const stopCardActivation = (event: { stopPropagation: () => void }) => {
    event.stopPropagation();
  };

  return (
    <article
      role="button"
      tabIndex={0}
      aria-label={`Открыть оффер ${offer.name}`}
      onClick={() => onOpen(offer.id)}
      onKeyDown={handleKeyDown}
      className={cn(
        'group relative flex h-full min-h-0 flex-col overflow-hidden rounded-2xl border border-black/[0.06] bg-white p-3',
        'shadow-[0_4px_16px_rgba(16,24,40,0.05)]',
        'transition-[border-color,box-shadow] duration-150 ease-out',
        'hover:border-black/[0.08] hover:shadow-[0_8px_24px_rgba(16,24,40,0.07)]',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2F6BFF]/30',
      )}
    >
      {isOwn && (
        <span className="absolute right-0 top-0 z-10 rounded-bl-xl bg-brand-soft px-2 py-1 text-[11px] font-medium leading-none text-brand">
          Ваш оффер
        </span>
      )}

      <div className="h-[136px] overflow-hidden rounded-xl bg-slate-100">
        {offer.image_url ? (
          <img src={offer.image_url} alt="" className="block size-full object-cover object-center" />
        ) : (
          <div className="flex size-full items-center justify-center px-3 text-center">
            <p className="text-[13px] font-medium text-slate-400">Без изображения</p>
          </div>
        )}
      </div>

      <h3 className="mt-2.5 min-h-[40px] text-[15px] font-semibold leading-5 tracking-tight text-slate-900 line-clamp-2">
        {offerCardTitle(offer.name)}
      </h3>

      <div className="mt-1.5 min-h-6">
        {categoryName ? (
          <span className="inline-flex max-w-full items-center gap-1 rounded-full bg-[#E8F1FF] px-2 py-0.5 text-[11px] font-medium text-[#2F6BFF]">
            <CategoryChipIcon offer={offer} />
            <span className="truncate">{categoryName}</span>
          </span>
        ) : null}
      </div>

      <div className="mt-2.5 flex items-center gap-3">
        <div className="min-w-0 shrink-0">
          <p className="text-[26px] font-semibold leading-none tracking-tight text-[#2F6BFF]">
            {formatCommissionPrimary(rule)}
          </p>
          <p className="mt-1 max-w-[8.5rem] truncate text-[11px] leading-tight text-slate-500">
            {formatCommissionContext(offer.conversion_type, rule)}
          </p>
        </div>
        <div className="h-10 w-px shrink-0 bg-slate-200" aria-hidden />
        <div className="flex min-w-0 flex-col gap-1 text-[11px] leading-none text-slate-500">
          <MetricRow icon={<ShoppingCart size={12} className="text-slate-400" />}>
            {offerCardMetricValue(conversionLabel(offer.conversion_type))}
          </MetricRow>
          <MetricRow icon={<BarChart3 size={12} className="text-emerald-500" />} title={epc.title}>
            EPC {offerCardMetricValue(epc.value)}
          </MetricRow>
          <MetricRow icon={<TrendingUp size={12} className="text-sky-500" />} title={cr.title}>
            CR {offerCardMetricValue(cr.value)}
          </MetricRow>
        </div>
      </div>

      <div className="mt-2.5 flex min-w-0 gap-1.5">
        <InfoPill icon={<Globe size={12} />} className="bg-emerald-50 text-emerald-800">
          {formatOfferGeo(offer.geo)}
        </InfoPill>
        <InfoPill icon={<Lock size={12} />} className="bg-slate-100 text-slate-600">
          {offerCardAccessLabel(offer.access_policy)}
        </InfoPill>
      </div>

      <div className="mt-auto flex min-h-[52px] flex-col justify-end pt-2.5" onClick={stopCardActivation} onKeyDown={stopCardActivation}>
        {statusNote ? <p className="mb-1 truncate text-[11px] text-amber-700">{statusNote}</p> : <span className="mb-1 h-[16px]" />}
        {cta.kind === 'own-active' && (
          <CardCta disabled={promoteOwnPending} onClick={() => onPromoteOwn?.(offer)}>
            {promoteOwnPending ? OWN_OFFER_PROMOTE_PENDING_LABEL : cta.label}
          </CardCta>
        )}
        {cta.kind === 'own-paused' && (
          <CardCta disabled title={cta.note || undefined}>
            {cta.label}
          </CardCta>
        )}
        {cta.kind === 'create-link' && (
          <CardCta onClick={() => onGetLink(offer)}>{cta.label}</CardCta>
        )}
        {cta.kind === 'pending' && (
          <CardCta tone="muted" disabled>
            {cta.label}
          </CardCta>
        )}
        {cta.kind === 'rejected' && (
          <CardCta onClick={() => onRequestAccess(offer)}>{cta.reapplyLabel || 'Продвигать оффер'}</CardCta>
        )}
        {cta.kind === 'promote-open' && (
          <CardCta disabled={joinPending} onClick={() => onJoinOpen(offer)}>
            {cta.label}
          </CardCta>
        )}
        {cta.kind === 'promote-approval' && (
          <CardCta onClick={() => onRequestAccess(offer)}>{cta.label}</CardCta>
        )}
        {cta.kind === 'invite-only' && (
          <CardCta disabled>{cta.label}</CardCta>
        )}
      </div>
    </article>
  );
}

function CategoryChipIcon({ offer }: { offer: OfferListItem }) {
  const code = resolveCategoryCode(offer.category_code || offer.category) || offer.category;
  const Icon = findCategory(code)?.verticalCode === 'EDUCATION' ? GraduationCap : Tag;
  return <Icon size={11} strokeWidth={2} aria-hidden />;
}

function MetricRow({ icon, title, children }: { icon: ReactNode; title?: string; children: ReactNode }) {
  return (
    <p className="flex min-w-0 items-center gap-1.5" title={title}>
      <span className="shrink-0">{icon}</span>
      <span className="truncate">{children}</span>
    </p>
  );
}

function InfoPill({ icon, className, children }: { icon: ReactNode; className: string; children: ReactNode }) {
  return (
    <span className={cn('inline-flex min-h-7 min-w-0 flex-1 items-center justify-center gap-1 rounded-full px-2 text-[11px] font-medium', className)}>
      <span className="shrink-0 opacity-80">{icon}</span>
      <span className="truncate">{children}</span>
    </span>
  );
}

function CardCta({
  children,
  onClick,
  disabled,
  title,
  tone = 'accent',
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  title?: string;
  tone?: 'accent' | 'muted';
}) {
  return (
    <button
      type="button"
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-lg text-[13px] font-semibold transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2F6BFF]/30',
        'disabled:pointer-events-none disabled:opacity-50',
        tone === 'accent' ? 'bg-[#2F6BFF] text-white hover:bg-[#2458E0]' : 'bg-slate-100 text-slate-700 hover:bg-slate-200',
      )}
    >
      {children}
      {tone === 'accent' && <ArrowRight size={14} strokeWidth={2.25} aria-hidden />}
    </button>
  );
}
