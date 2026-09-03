import { useNavigate, useSearchParams } from 'react-router-dom';
import { OfferWizard } from '@/shared/offers/wizard/OfferWizard';

export function BusinessOfferNew() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const startWithAi = searchParams.get('ai') === '1';

  return (
    <OfferWizard
      initialAiBrief={startWithAi}
      onBack={() => navigate('/business/offers')}
      onCreated={(id) => navigate(`/business/offers/${id}`)}
    />
  );
}
