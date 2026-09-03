import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { api, type ApiError } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { useToast } from '@/shared/components/Toast';
import { validateDestinationUrl } from '@/shared/links/destinationUrl';
import { CampaignFields } from '@/shared/promotion/CreateBusinessCampaignModal';
import type { BusinessCampaign, BusinessOwnLink } from '@/pages/business/OfferPromotionTab';

const CREATE_CAMPAIGN = '__create__';

export function CreateBusinessLinkModal({
  offerId,
  campaigns,
  onClose,
  onCreated,
}: {
  offerId: string;
  campaigns: BusinessCampaign[];
  onClose: () => void;
  onCreated: (link: BusinessOwnLink) => void;
}) {
  const { addToast } = useToast();
  const [destinationUrl, setDestinationUrl] = useState('');
  const [linkName, setLinkName] = useState('');
  const [campaignChoice, setCampaignChoice] = useState('');
  const [campaignName, setCampaignName] = useState('');
  const [campaignDescription, setCampaignDescription] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const { data: offer } = useQuery<{ product_url?: string | null }>({
    queryKey: ['business', 'offers', offerId],
    queryFn: () => api.get(`/business/offers/${offerId}`),
  });

  const create = useMutation({
    mutationFn: async ({
      destination,
      campaignId,
    }: {
      destination: string;
      campaignId: number | null;
    }) => {
      let resolvedCampaignId = campaignId;
      if (campaignChoice === CREATE_CAMPAIGN) {
        const campaign = await api.post<BusinessCampaign>(`/business/offers/${offerId}/campaigns`, {
          name: campaignName.trim(),
          description: campaignDescription.trim() || null,
        });
        resolvedCampaignId = campaign.id;
      }
      return api.post<BusinessOwnLink>(`/business/offers/${offerId}/links`, {
        destination_url: destination,
        campaign_id: resolvedCampaignId,
        name: linkName.trim() || null,
      });
    },
    onSuccess: (link) => {
      addToast('Ссылка создана', 'success');
      onCreated(link);
    },
    onError: (error: unknown) => {
      const apiError = error as ApiError | undefined;
      setFormError(apiError?.error?.message || 'Не удалось создать ссылку');
    },
  });

  const submit = () => {
    const checked = validateDestinationUrl(destinationUrl);
    if (!checked.ok) {
      setFormError(checked.message);
      return;
    }
    if (campaignChoice === CREATE_CAMPAIGN && !campaignName.trim()) {
      setFormError('Укажите название кампании');
      return;
    }
    const campaignId = campaignChoice && campaignChoice !== CREATE_CAMPAIGN ? Number(campaignChoice) : null;
    setFormError(null);
    create.mutate({ destination: checked.value, campaignId });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className="relative ui-card w-full max-w-lg p-5 space-y-4 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <h2 className="ui-section-title">Создать ссылку</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>

        <label className="block">
          <span className="ui-label">Кампания</span>
          <select
            className="ui-input"
            value={campaignChoice}
            onChange={(e) => setCampaignChoice(e.target.value)}
          >
            <option value="">Без кампании</option>
            {campaigns.map((campaign) => (
              <option key={campaign.id} value={String(campaign.id)}>
                {campaign.name}
              </option>
            ))}
            <option value={CREATE_CAMPAIGN}>+ Создать кампанию</option>
          </select>
        </label>

        {campaignChoice === CREATE_CAMPAIGN && (
          <CampaignFields
            name={campaignName}
            description={campaignDescription}
            onNameChange={setCampaignName}
            onDescriptionChange={setCampaignDescription}
          />
        )}

        <label className="block">
          <span className="ui-label">Название</span>
          <input
            className="ui-input"
            placeholder="Например: Яндекс Директ"
            value={linkName}
            onChange={(e) => setLinkName(e.target.value)}
          />
        </label>

        <label className="block">
          <span className="ui-label">Destination URL *</span>
          <input
            className="ui-input"
            placeholder={offer?.product_url || 'https://'}
            value={destinationUrl}
            onChange={(e) => {
              setDestinationUrl(e.target.value);
              if (formError) setFormError(null);
            }}
          />
        </label>

        {formError && <p className="text-sm text-destructive">{formError}</p>}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" disabled={create.isPending} onClick={onClose}>
            Отмена
          </Button>
          <Button type="button" disabled={create.isPending} onClick={submit}>
            {create.isPending ? 'Создание...' : 'Создать ссылку'}
          </Button>
        </div>
      </div>
    </div>
  );
}
