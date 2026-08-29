export function tracePath(rqcid: string) {
  return `/trace/${encodeURIComponent(rqcid)}`;
}

export interface SearchItem {
  type: string;
  id: string | number;
  title: string;
  subtitle?: string | null;
  href?: string;
  rqcid?: string;
  primary_action?: string | null;
  context?: Record<string, string | number | null | undefined>;
}

export function hrefForSearchItem(item: SearchItem) {
  if (item.primary_action === 'open_trace' && item.rqcid) return tracePath(item.rqcid);
  if (item.href) return item.href;
  switch (item.type) {
    case 'trace':
    case 'click':
      return item.rqcid ? tracePath(String(item.rqcid)) : '/clicks';
    case 'business':
      return `/businesses/${item.id}`;
    case 'partner':
      return `/partners/${item.id}`;
    case 'offer':
      return `/offers/${item.id}`;
    case 'site':
      return `/sites/${item.id}`;
    case 'tracking_link':
      return `/tracking-links/${item.id}`;
    case 'conversion':
      return `/conversions/${item.id}`;
    default:
      return '/';
  }
}

export function entityHref(type: string, id: string | number | null | undefined) {
  if (id === null || id === undefined || id === '') return null;
  const map: Record<string, string> = {
    business: `/businesses/${id}`,
    partner: `/partners/${id}`,
    offer: `/offers/${id}`,
    site: `/sites/${id}`,
    tracking_link: `/tracking-links/${id}`,
    conversion: `/conversions/${id}`,
    commission: `/commissions/${id}`,
    payout: `/payouts/${id}`,
    click: typeof id === 'string' && id.length === 12 ? tracePath(id) : `/clicks/${id}`,
    postback: '/postbacks',
  };
  return map[type] || null;
}
