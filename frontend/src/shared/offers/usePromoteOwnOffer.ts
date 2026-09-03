import { useRef } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '@/shared/api/client';
import type { SessionData } from '@/shared/api/auth';
import { useToast } from '@/shared/components/Toast';
import {
  OWN_OFFER_PROMOTE_ERROR,
  OWN_OFFER_PROMOTE_TOAST,
  canStartOwnOfferPromote,
  ownOfferPromoteContext,
  ownOfferPromotePath,
} from '@/shared/offers/promoteOwnOffer';

export function usePromoteOwnOffer() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const queryClient = useQueryClient();
  const inFlight = useRef(false);

  const mutation = useMutation({
    mutationFn: (offerId: string | number) =>
      api.post<SessionData>('/me/context', ownOfferPromoteContext(offerId)),
    onSuccess: (data, offerId) => {
      queryClient.setQueryData(['session'], data);
      addToast(OWN_OFFER_PROMOTE_TOAST, 'info');
      navigate(ownOfferPromotePath(offerId));
    },
    onError: () => addToast(OWN_OFFER_PROMOTE_ERROR, 'error'),
    onSettled: () => {
      inFlight.current = false;
    },
  });

  const pending = mutation.isPending || inFlight.current;

  const promote = (offerId: string | number) => {
    if (!canStartOwnOfferPromote(pending)) return;
    inFlight.current = true;
    mutation.mutate(offerId);
  };

  return { promote, pending };
}
