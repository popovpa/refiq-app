import type { OfferAiChange } from '@/shared/ai/types';

export type OfferAiEditPhase = 'closed' | 'input' | 'loading' | 'review' | 'applied';

export type OfferAiEditState = {
  phase: OfferAiEditPhase;
  instruction: string;
  continueMode: boolean;
  changes: OfferAiChange[];
  selected: Record<number, boolean>;
  appliedCount: number;
  error: string | null;
  confirmClose: boolean;
};

export type OfferAiEditAction =
  | { type: 'OPEN' }
  | { type: 'SET_INSTRUCTION'; instruction: string }
  | { type: 'REQUEST' }
  | { type: 'SUCCESS'; changes: OfferAiChange[] }
  | { type: 'FAIL'; error: string }
  | { type: 'TOGGLE'; index: number }
  | { type: 'APPLIED'; count: number }
  | { type: 'EDIT_PROMPT' }
  | { type: 'CONTINUE' }
  | { type: 'ASK_CLOSE' }
  | { type: 'STAY' }
  | { type: 'CLOSE' };

export function createOfferAiEditState(open = false): OfferAiEditState {
  return {
    phase: open ? 'input' : 'closed',
    instruction: '',
    continueMode: false,
    changes: [],
    selected: {},
    appliedCount: 0,
    error: null,
    confirmClose: false,
  };
}

export function selectedSuggestionCount(state: OfferAiEditState): number {
  return state.changes.reduce((count, _, index) => count + (state.selected[index] ? 1 : 0), 0);
}

export function selectedSuggestions(state: OfferAiEditState): OfferAiChange[] {
  return state.changes.filter((_, index) => state.selected[index]);
}

function closedState(): OfferAiEditState {
  return createOfferAiEditState(false);
}

function selectAll(changes: OfferAiChange[]): Record<number, boolean> {
  return Object.fromEntries(changes.map((_, index) => [index, true]));
}

export function offerAiEditReducer(state: OfferAiEditState, action: OfferAiEditAction): OfferAiEditState {
  switch (action.type) {
    case 'OPEN':
      if (state.phase !== 'closed') return state;
      return { ...createOfferAiEditState(true) };
    case 'SET_INSTRUCTION':
      if (state.phase !== 'input') return state;
      return { ...state, instruction: action.instruction, error: null };
    case 'REQUEST':
      if (state.phase !== 'input' || !state.instruction.trim()) return state;
      return { ...state, phase: 'loading', error: null, confirmClose: false };
    case 'SUCCESS':
      if (state.phase !== 'loading') return state;
      return {
        ...state,
        phase: 'review',
        changes: action.changes,
        selected: selectAll(action.changes),
        error: null,
      };
    case 'FAIL':
      if (state.phase !== 'loading') return state;
      return { ...state, phase: 'input', error: action.error };
    case 'TOGGLE':
      if (state.phase !== 'review') return state;
      return {
        ...state,
        selected: { ...state.selected, [action.index]: !state.selected[action.index] },
      };
    case 'APPLIED':
      if (state.phase !== 'review') return state;
      return {
        ...state,
        phase: 'applied',
        appliedCount: action.count,
        confirmClose: false,
        changes: [],
        selected: {},
      };
    case 'EDIT_PROMPT':
      if (state.phase !== 'review') return state;
      return {
        ...state,
        phase: 'input',
        continueMode: false,
        error: null,
        changes: [],
        selected: {},
      };
    case 'CONTINUE':
      if (state.phase !== 'applied') return state;
      return {
        ...state,
        phase: 'input',
        instruction: '',
        continueMode: true,
        error: null,
        appliedCount: 0,
        changes: [],
        selected: {},
      };
    case 'ASK_CLOSE':
      if (state.phase === 'closed' || state.phase === 'loading') return state;
      if (state.phase === 'review' && state.changes.length > 0) {
        return { ...state, confirmClose: true };
      }
      return closedState();
    case 'STAY':
      return { ...state, confirmClose: false };
    case 'CLOSE':
      return closedState();
    default:
      return state;
  }
}
