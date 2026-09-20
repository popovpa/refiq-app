const REASON_MESSAGES: Record<string, string> = {
  LEGAL_ENTITY_MISSING: 'Не заполнены юридические данные',
  LEGAL_ENTITY_NOT_VERIFIED: 'Юридические данные не подтверждены',
  UNSUPPORTED_PARTNER_TYPE: 'Выплаты доступны самозанятым / НПД, ИП и юридическим лицам',
  PARTNER_INDIVIDUAL_REQUIRES_NPD: 'Для получения выплат физическое лицо должно иметь статус самозанятого / НПД.',
  PARTNER_TAX_STATUS_INVALID: 'Недопустимый налоговый статус для выбранного типа',
  PARTNER_LEGAL_TYPE_NOT_SUPPORTED: 'Недопустимый тип партнёра для выплат',
  NPD_STATUS_INVALID: 'Статус НПД не подтверждён',
  PAYOUT_PROFILE_MISSING: 'Не заполнены реквизиты',
  PAYOUT_PROFILE_NOT_VERIFIED: 'Реквизиты не подтверждены',
  PAYMENT_DETAILS_INVALID: 'Банковские реквизиты указаны неверно',
  PARTNER_BLOCKED: 'Профиль партнёра заблокирован',
  FIN_LEGAL_ENTITY_REQUIRED: 'Заполните юридические данные',
  FIN_LEGAL_ENTITY_INVALID: 'Проверьте юридические данные',
  FIN_LEGAL_ENTITY_NOT_VERIFIED: 'Юридические данные не подтверждены',
  LEGAL_ENTITY_STATUS_CHANGED: 'Статус юридических данных уже изменился',
  FIN_PARTNER_NOT_PAYOUT_ELIGIBLE: 'Партнёр не может получать выплаты',
  FIN_PAYOUT_PROFILE_REQUIRED: 'Заполните реквизиты для выплат',
  FIN_SELF_DEAL_FORBIDDEN: 'Нельзя продвигать собственный оффер как партнёр',
  SAME_USER_BUSINESS_MEMBER: 'Собственный оффер продвигается через бизнес-пространство, без партнёрского доступа.',
  OWN_BUSINESS_OFFER: 'Собственный оффер продвигается через бизнес-пространство, без партнёрского доступа.',
  SAME_LEGAL_ENTITY: 'Нельзя продвигать оффер своей юридической организации как партнёр.',
  SELF_PROMOTION_FORBIDDEN: 'Партнёр не может получать комиссию за оффер собственного бизнеса.',
  COMMISSION_SELF_DEAL_FORBIDDEN: 'Нельзя начислить партнёрскую комиссию за собственный оффер.',
  PAYOUT_SELF_DEAL_FORBIDDEN: 'Нельзя сформировать выплату за продвижение собственного оффера.',
  FIN_COMMISSION_NOT_AVAILABLE: 'Комиссия ещё недоступна к выплате',
  FIN_PAYOUT_ALREADY_PROCESSED: 'Выплата уже обработана',
  FIN_PAYOUT_BELOW_MINIMUM: 'Сумма ниже минимальной выплаты',
  FIN_LIVE_TRANSACTIONS_DISABLED: 'Реальные платежи отключены',
  FIN_PROVIDER_ERROR: 'Ошибка платёжного провайдера',
  FIN_RECONCILIATION_REQUIRED: 'Требуется сверка платежа',
  FIN_PARTNER_TRAFFIC_SUSPENDED: 'Партнёрский трафик приостановлен из-за просроченной выплаты',
  LEGAL_ENTITY_LOOKUP_INVALID_REQUEST: 'Некорректный запрос поиска организации',
  LEGAL_ENTITY_LOOKUP_UNAVAILABLE: 'Не удалось выполнить поиск. Попробуйте ещё раз или заполните данные вручную.',
  LEGAL_ENTITY_LOOKUP_RATE_LIMITED: 'Слишком много запросов. Подождите немного и повторите поиск.',
  LEGAL_ENTITY_LOOKUP_CONFIGURATION_ERROR: 'Поиск организаций временно недоступен.',
  LEGAL_ENTITY_NOT_FOUND: 'Организация не найдена',
  LEGAL_ENTITY_NOT_ACTIVE: 'Организация не действует и не может быть использована',
};

export function financeReasonText(code?: string | null, fallback?: string | null) {
  if (code && REASON_MESSAGES[code]) {
    // Prefer a specific backend message when it is more precise than the generic label.
    if (fallback && code === 'FIN_LEGAL_ENTITY_INVALID') return fallback;
    return REASON_MESSAGES[code];
  }
  return fallback || 'Выплата сейчас недоступна';
}

export function financeApiErrorText(err: unknown, fallback = 'Не удалось сохранить'): string {
  if (err && typeof err === 'object' && 'error' in err) {
    const payload = (err as { error?: { code?: string; message?: string } }).error;
    if (
      payload?.code &&
      ['FIN_LEGAL_ENTITY_INVALID', 'PARTNER_INDIVIDUAL_REQUIRES_NPD', 'PARTNER_TAX_STATUS_INVALID'].includes(
        payload.code,
      ) &&
      payload.message
    ) {
      return payload.message;
    }
    if (payload?.code) return financeReasonText(payload.code, payload.message || fallback);
    if (payload?.message) return payload.message;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

export interface FinancialMode {
  financial_mode?: string;
  financial_transactions_enabled?: boolean;
  live?: boolean;
}
