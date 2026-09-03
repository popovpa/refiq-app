import { describe, expect, it } from 'vitest';
import {
  AI_GUIDANCE_PRESETS,
  AI_REWRITE_PRESETS,
  canSubmitAiGuidance,
  canSubmitAiRewrite,
  toAiGuidancePayload,
  toAiRewritePayload,
} from './presets';

describe('AI guidance presets', () => {
  it('uses trusted preset ids instead of frontend prompt text', () => {
    expect(AI_GUIDANCE_PRESETS.map((item) => item.id)).toEqual([
      'clearer',
      'shorter',
      'selling',
      'structure',
      'dedupe',
    ]);
    expect(AI_REWRITE_PRESETS.map((item) => item.id)).toEqual([
      'clearer',
      'shorter',
      'selling',
      'structure',
      'dedupe',
      'tone',
    ]);
    expect(AI_GUIDANCE_PRESETS.some((item) => 'instruction' in item)).toBe(false);
  });

  it('allows a preset without extra guidance for offer edit', () => {
    expect(canSubmitAiGuidance({ preset: 'shorter', guidance: '' })).toBe(true);
    expect(canSubmitAiGuidance({ preset: '', guidance: 'Сделай короче' })).toBe(true);
    expect(canSubmitAiGuidance({ preset: '', guidance: '' })).toBe(false);
  });

  it('field rewrite accepts only known presets', () => {
    expect(canSubmitAiRewrite({ preset: 'selling' })).toBe(true);
    expect(canSubmitAiRewrite({ preset: 'unknown' })).toBe(false);
    expect(canSubmitAiRewrite({ preset: '' })).toBe(false);
  });

  it('sends only preset for field rewrite', () => {
    expect(toAiRewritePayload({ preset: 'clearer' })).toEqual({ preset: 'clearer' });
  });

  it('sends preset and guidance as separate fields for offer edit', () => {
    expect(toAiGuidancePayload({ preset: 'clearer', guidance: 'Акцент на цене' })).toEqual({
      preset: 'clearer',
      guidance: 'Акцент на цене',
    });
  });
});
