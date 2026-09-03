import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { api, type ApiError } from '@/shared/api/client';
import { Button } from '@/shared/components/Button';
import { useToast } from '@/shared/components/Toast';
import type { BusinessCampaign } from '@/pages/business/OfferPromotionTab';

export function CreateBusinessCampaignModal({
  offerId,
  campaign,
  onClose,
  onCreated,
}: {
  offerId: string;
  campaign?: BusinessCampaign | null;
  onClose: () => void;
  onCreated: (campaign: BusinessCampaign) => void;
}) {
  const { addToast } = useToast();
  const isEdit = Boolean(campaign);
  const [name, setName] = useState(campaign?.name || '');
  const [description, setDescription] = useState(campaign?.description || '');
  const [formError, setFormError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () =>
      isEdit && campaign
        ? api.patch<BusinessCampaign>(`/business/offers/${offerId}/campaigns/${campaign.id}`, {
            name: name.trim(),
            description: description.trim() || null,
          })
        : api.post<BusinessCampaign>(`/business/offers/${offerId}/campaigns`, {
            name: name.trim(),
            description: description.trim() || null,
          }),
    onSuccess: (saved) => {
      addToast(isEdit ? 'Кампания обновлена' : 'Кампания создана', 'success');
      onCreated(saved);
    },
    onError: (error: unknown) => {
      const apiError = error as ApiError | undefined;
      setFormError(apiError?.error?.message || (isEdit ? 'Не удалось сохранить кампанию' : 'Не удалось создать кампанию'));
    },
  });

  const submit = () => {
    if (!name.trim()) {
      setFormError('Укажите название');
      return;
    }
    setFormError(null);
    save.mutate();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-foreground/30" onClick={onClose} />
      <div className="relative ui-card w-full max-w-md p-5 space-y-4 shadow-soft">
        <div className="flex items-start justify-between gap-3">
          <h2 className="ui-section-title">{isEdit ? 'Кампания' : 'Новая кампания'}</h2>
          <button type="button" onClick={onClose} className="text-muted-foreground hover:text-foreground" aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>
        <CampaignFields
          name={name}
          description={description}
          onNameChange={setName}
          onDescriptionChange={setDescription}
        />
        {formError && <p className="text-sm text-destructive">{formError}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" disabled={save.isPending} onClick={onClose}>
            Отмена
          </Button>
          <Button type="button" disabled={save.isPending} onClick={submit}>
            {save.isPending ? 'Сохранение...' : isEdit ? 'Сохранить' : 'Создать'}
          </Button>
        </div>
      </div>
    </div>
  );
}

export function CampaignFields({
  name,
  description,
  onNameChange,
  onDescriptionChange,
}: {
  name: string;
  description: string;
  onNameChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
}) {
  return (
    <div className="space-y-3">
      <label className="block">
        <span className="ui-label">Название *</span>
        <input className="ui-input" value={name} onChange={(e) => onNameChange(e.target.value)} />
      </label>
      <label className="block">
        <span className="ui-label">Описание</span>
        <textarea
          className="ui-input min-h-[80px]"
          value={description}
          onChange={(e) => onDescriptionChange(e.target.value)}
        />
      </label>
    </div>
  );
}
