import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { ConfirmDialog } from '@/shared/components/ConfirmDialog';
import { useToast } from '@/shared/components/Toast';

export function RequestAccessModal({
  offerId,
  offerName,
  onClose,
}: {
  offerId: string | number;
  offerName: string;
  onClose: () => void;
}) {
  const { addToast } = useToast();
  const queryClient = useQueryClient();

  const request = useMutation({
    mutationFn: () => api.post(`/partner/offers/${offerId}/join`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['partner', 'offers'] });
      addToast('Заявка отправлена', 'success');
      onClose();
    },
    onError: () => addToast('Не удалось отправить заявку', 'error'),
  });

  return (
    <ConfirmDialog
      title="Продвигать оффер"
      confirmLabel="Отправить заявку"
      pendingLabel="Отправка..."
      pending={request.isPending}
      onConfirm={() => request.mutate()}
      onClose={onClose}
    >
      <p className="font-medium text-foreground">{offerName}</p>
      <p>Для этого оффера требуется одобрение бизнеса.</p>
      <p>После одобрения вы сможете продвигать оффер любыми способами и в GEO, разрешённых условиями оффера.</p>
      <p>Данные вашего партнёрского профиля будут доступны бизнесу вместе с заявкой.</p>
    </ConfirmDialog>
  );
}
