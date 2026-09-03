import { describe, expect, it } from 'vitest';
import {
  canRequestOfferAiEdit,
  createOfferAiEditState,
  offerAiEditReducer,
} from './offerEditSession';

describe('offerAiEditSession', () => {
  it('allows a trusted preset without extra guidance', () => {
    const withPreset = offerAiEditReducer(createOfferAiEditState(true), {
      type: 'SET_PRESET',
      preset: 'shorter',
    });
    expect(canRequestOfferAiEdit(withPreset)).toBe(true);
    expect(offerAiEditReducer(withPreset, { type: 'REQUEST' }).phase).toBe('loading');
  });

  it('does not start a request without preset or guidance', () => {
    const empty = createOfferAiEditState(true);
    expect(canRequestOfferAiEdit(empty)).toBe(false);
    expect(offerAiEditReducer(empty, { type: 'REQUEST' }).phase).toBe('input');
  });
});
