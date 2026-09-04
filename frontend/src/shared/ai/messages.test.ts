import { describe, expect, it } from 'vitest';
import { aiErrorMessage } from '@/shared/ai/messages';

describe('aiErrorMessage', () => {
  it('prefers API message for INVALID_AI_GUIDANCE', () => {
    expect(
      aiErrorMessage({
        status: 400,
        error: {
          code: 'INVALID_AI_GUIDANCE',
          message:
            'Пожелание содержит инструкции, не относящиеся к редактированию текущего поля. Оставьте только пожелания к стилю, формулировке или содержанию на основе существующих данных.',
        },
      })
    ).toContain('не относящиеся к редактированию');
  });

  it('falls back to mapped message when INVALID_AI_GUIDANCE has no detail', () => {
    expect(
      aiErrorMessage({
        status: 400,
        error: { code: 'INVALID_AI_GUIDANCE', message: '' },
      })
    ).toContain('Фактические данные изменяйте в полях оффера');
  });
});
