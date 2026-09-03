import type { ApiError } from '@/shared/api/client';

const MESSAGES: Record<string, string> = {
  AI_NOT_CONFIGURED: 'AI не настроен. Добавьте ключ провайдера в настройках сервера.',
  AI_UNAVAILABLE: 'AI временно недоступен. Попробуйте ещё раз.',
  AI_TIMEOUT: 'Превышено время ожидания ответа AI. Попробуйте ещё раз.',
  AI_RATE_LIMIT: 'Слишком много запросов к AI. Подождите немного и повторите.',
  AI_QUOTA_EXCEEDED: 'Исчерпан лимит AI-провайдера. Проверьте тариф и квоту API-ключа.',
  AI_MODEL_UNAVAILABLE: 'Указанная модель AI недоступна. Для картинок нужен gpt-image-* или luna через Responses API — проверьте OPENAI_IMAGE_MODEL.',
  AI_INVALID_RESPONSE: 'Не удалось обработать ответ AI. Попробуйте переформулировать запрос.',
  AI_UNAUTHORIZED: 'Провайдер AI отклонил запрос.',
  AI_CAPABILITY_UNAVAILABLE: 'Эта возможность AI пока недоступна.',
  AI_FIELD_NOT_SUPPORTED: 'Это поле нельзя улучшить с помощью AI.',
  INVALID_AI_GUIDANCE:
    'Не удалось применить пожелание. Используйте поле для изменения стиля, длины, структуры или акцентов текста. Фактические данные изменяйте в полях оффера.',
  CREATIVE_CONTENT_BLOCKED: 'Материал нарушает правила продвижения. Исправьте текст перед публикацией.',
  CREATIVE_TYPE_INVALID: 'Этот тип материала пока недоступен.',
  CREATIVE_IMAGE_EDIT_UNAVAILABLE: 'Редактирование баннера с AI пока недоступно.',
  AI_ASSET_UPLOAD_FAILED: 'Не удалось сохранить изображение.',
};

export function aiErrorMessage(error: unknown, fallback = 'Не удалось выполнить запрос к AI'): string {
  const apiError = error as ApiError | undefined;
  const code = apiError?.error?.code;
  const message =
    typeof apiError?.error?.message === 'string' ? apiError.error.message.trim() : '';
  // Prefer API detail for guidance refusals (specific Russian reason from the guard).
  if (code === 'INVALID_AI_GUIDANCE' && message) return message;
  if (code && MESSAGES[code]) return MESSAGES[code];
  if (message) return message;
  return fallback;
}
