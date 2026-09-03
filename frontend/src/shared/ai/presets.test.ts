import { describe, expect, it } from 'vitest';
import { AI_GUIDANCE_PRESETS, canSubmitAiGuidance, toAiGuidancePayload } from './presets';

describe('AI guidance presets', () => {
  it('uses trusted preset ids instead of frontend prompt text', () => {
    expect(AI_GUIDANCE_PRESETS.map((item) => item.id)).toEqual([
      'clearer',
      'shorter',
      'selling',
      'structure',
      'dedupe',
    ]);
    expect(AI_GUIDANCE_PRESETS.some((item) => 'instruction' in item)).toBe(false);
  });

  it('allows a preset without extra guidance', () => {
    expect(canSubmitAiGuidance({ preset: 'shorter', guidance: '' })).toBe(true);
    expect(canSubmitAiGuidance({ preset: '', guidance: 'Сделай короче' })).toBe(true);
    expect(canSubmitAiGuidance({ preset: '', guidance: '' })).toBe(false);
  });

  it('sends preset and guidance as separate fields', () => {
    expect(toAiGuidancePayload({ preset: 'clearer', guidance: 'Акцент на цене' })).toEqual({
      preset: 'clearer',
      guidance: 'Акцент на цене',
    });
  });
});
