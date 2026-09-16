import { useQuery } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '@/shared/api/client';
import { Skeleton } from '@/shared/components/Skeleton';
import { OfferWizard } from '@/shared/offers/wizard/OfferWizard';
import { offerToForm } from '@/shared/offers/types';

interface OfferDetail {
  name: string;
  description: string | null;
  image_url?: string | null;
  category?: string | null;
  category_code?: string | null;
  geo?: string | null;
  conversion_type: string;
  access_policy: string;
  attribution_window_days: number;
  hold_period_days?: number;
  partner_notes?: string | null;
  allowed_traffic?: string[];
  product_url?: string | null;
  commission_rules: Array<{ type: string; value: number; currency: string | null }>;
  status: string;
}

export function BusinessOfferEdit() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data, isLoading } = useQuery<OfferDetail>({
    queryKey: ['business', 'offers', id],
    queryFn: () => api.get(`/business/offers/${id}`),
    enabled: !!id,
  });

  if (isLoading || !data) {
    return <Skeleton className="h-96 rounded-xl" />;
  }

  return (
    <OfferWizard
      mode="edit"
      offerId={id}
      status={data.status}
      initialForm={offerToForm(data)}
      onBack={() => navigate(`/business/offers/${id}`)}
      onSaved={() => navigate(`/business/offers/${id}`)}
    />
  );
}
