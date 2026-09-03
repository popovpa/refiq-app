import { useState, type Dispatch } from 'react';
import { CheckCircle2, Sparkles, X } from 'lucide-react';
import { Button } from '@/shared/components/Button';
import { formatOfferAiValue, OFFER_AI_FIELD_LABELS } from '@/shared/ai/format';
import {
  canRequestOfferAiEdit,
  selectedSuggestionCount,
  type OfferAiEditAction,
  type OfferAiEditState,
} from '@/shared/ai/offerEditSession';
import { AI_GUIDANCE_PRESETS } from '@/shared/ai/presets';
import type { OfferAiChange } from '@/shared/ai/types';

const LONG_FIELDS = new Set(['description', 'partner_notes']);
const COMMISSION_FIELDS = ['commission_type', 'commission_value', 'commission_currency'];

export function OfferAiEditPanel({
  state,
  dispatch,
  onRequest,
  onApply,
}: {
  state: OfferAiEditState;
  dispatch: Dispatch<OfferAiEditAction>;
  onRequest: () => void;
  onApply: () => void;
}) {
  const loading = state.phase === 'loading';
  const canClose = state.phase !== 'loading';

  return (
    <div className="ui-card p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <Sparkles size={16} className="text-primary shrink-0" aria-hidden />
          <h2 className="ui-section-title truncate">
            {state.phase === 'review' ? 'Предложения AI' : 'AI-редактирование'}
          </h2>
        </div>
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground disabled:opacity-50 shrink-0"
          aria-label="Закрыть AI-редактирование"
          disabled={!canClose}
          onClick={() => dispatch({ type: 'ASK_CLOSE' })}
        >
          <X size={18} />
        </button>
      </div>

      {(state.phase === 'input' || state.phase === 'loading') && (
        <InputState state={state} dispatch={dispatch} loading={loading} onRequest={onRequest} />
      )}
      {state.phase === 'review' && <ReviewState state={state} dispatch={dispatch} onApply={onApply} />}
      {state.phase === 'applied' && <AppliedState count={state.appliedCount} dispatch={dispatch} />}
    </div>
  );
}

function InputState({
  state,
  dispatch,
  loading,
  onRequest,
}: {
  state: OfferAiEditState;
  dispatch: Dispatch<OfferAiEditAction>;
  loading: boolean;
  onRequest: () => void;
}) {
  return (
    <>
      <div className="space-y-2">
        <p className="ui-label">Что улучшить</p>
        <div className="flex flex-wrap gap-1.5">
          {AI_GUIDANCE_PRESETS.map((item) => {
            const active = state.preset === item.id;
            return (
              <button
                key={item.id}
                type="button"
                disabled={loading}
                className={
                  active
                    ? 'px-2 py-1 rounded-md text-[12px] border border-primary bg-brand-soft text-brand'
                    : 'px-2 py-1 rounded-md text-[12px] border border-border hover:bg-muted'
                }
                onClick={() => dispatch({ type: 'SET_PRESET', preset: active ? null : item.id })}
              >
                {item.label}
              </button>
            );
          })}
        </div>
      </div>
      <label className="block">
        <span className="ui-label">Дополнительное пожелание</span>
        <textarea
          className="ui-input min-h-[72px] h-auto py-2 resize-y"
          placeholder={
            state.continueMode
              ? 'Уточните, что изменить ещё'
              : 'Например: сделай акцент на расположении клиники'
          }
          value={state.instruction}
          readOnly={loading}
          onChange={(e) => dispatch({ type: 'SET_INSTRUCTION', instruction: e.target.value })}
        />
      </label>
      {loading ? (
        <div className="flex items-start gap-3">
          <div className="mt-0.5 animate-spin rounded-full h-5 w-5 border-b-2 border-primary shrink-0" />
          <div>
            <p className="text-sm font-medium">AI анализирует оффер...</p>
            <p className="text-sm text-muted-foreground">Подготавливаем предложения по изменению.</p>
          </div>
        </div>
      ) : state.error ? (
        <div className="space-y-2">
          <p className="text-sm text-destructive">{state.error}</p>
          <p className="text-sm text-muted-foreground">Текущие данные оффера не изменены.</p>
        </div>
      ) : null}
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button type="button" variant="ghost" disabled={loading} onClick={() => dispatch({ type: 'ASK_CLOSE' })}>
          Закрыть
        </Button>
        <Button
          type="button"
          disabled={loading || !canRequestOfferAiEdit(state)}
          onClick={onRequest}
        >
          {state.error ? 'Попробовать ещё раз' : 'Получить предложения'}
        </Button>
      </div>
    </>
  );
}

function ReviewState({
  state,
  dispatch,
  onApply,
}: {
  state: OfferAiEditState;
  dispatch: Dispatch<OfferAiEditAction>;
  onApply: () => void;
}) {
  const selected = selectedSuggestionCount(state);
  const unchanged = unchangedLabels(state.changes);

  return (
    <>
      <p className="text-sm text-muted-foreground">
        {state.changes.length === 0
          ? 'AI не предложил изменений.'
          : `Найдено ${state.changes.length} ${changeWord(state.changes.length)}`}
      </p>
      {state.changes.length > 0 && (
        <div className="space-y-2">
          {state.changes.map((change, index) => (
            <SuggestionRow
              key={`${change.field}-${index}`}
              change={change}
              checked={Boolean(state.selected[index])}
              onToggle={() => dispatch({ type: 'TOGGLE', index })}
            />
          ))}
        </div>
      )}
      {unchanged.length > 0 && (
        <p className="text-xs text-muted-foreground">Не изменяется: {unchanged.join(' · ')}</p>
      )}
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button type="button" variant="ghost" onClick={() => dispatch({ type: 'EDIT_PROMPT' })}>
          Изменить запрос
        </Button>
        <Button type="button" disabled={selected === 0} onClick={onApply}>
          Применить выбранные
        </Button>
      </div>
    </>
  );
}

function AppliedState({
  count,
  dispatch,
}: {
  count: number;
  dispatch: Dispatch<OfferAiEditAction>;
}) {
  return (
    <>
      <div className="flex items-start gap-2">
        <CheckCircle2 size={18} className="text-success shrink-0 mt-0.5" aria-hidden />
        <div>
          <p className="text-sm font-medium">Предложения применены</p>
          <p className="text-sm text-muted-foreground">
            Изменено {count} {fieldWord(count)}.
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button type="button" variant="secondary" onClick={() => dispatch({ type: 'CONTINUE' })}>
          Продолжить с AI
        </Button>
        <Button type="button" variant="ghost" onClick={() => dispatch({ type: 'ASK_CLOSE' })}>
          Закрыть AI-редактирование
        </Button>
      </div>
    </>
  );
}

function SuggestionRow({
  change,
  checked,
  onToggle,
}: {
  change: OfferAiChange;
  checked: boolean;
  onToggle: () => void;
}) {
  const long = isLongSuggestion(change);
  const [expanded, setExpanded] = useState(!long);
  const label = OFFER_AI_FIELD_LABELS[change.field] || change.field;
  const traffic = trafficDelta(change);

  return (
    <div className="flex items-start gap-3 rounded-lg border border-border p-3">
      <input
        type="checkbox"
        className="mt-0.5 h-4 w-4 rounded border-input accent-primary shrink-0"
        checked={checked}
        onChange={onToggle}
        aria-label={label}
      />
      <div className="min-w-0 flex-1 space-y-1.5">
        <p className="text-sm font-medium">{label}</p>
        {long && !expanded ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">Изменено</span>
            <button
              type="button"
              className="text-xs font-medium text-primary hover:underline"
              onClick={() => setExpanded(true)}
            >
              Показать сравнение
            </button>
          </div>
        ) : traffic ? (
          <DiffLine label={traffic.label} value={traffic.value} />
        ) : (
          <>
            <DiffLine label="Было" value={formatOfferAiValue(change.field, change.old_value)} muted strike />
            <DiffLine label="Предлагается" value={formatOfferAiValue(change.field, change.new_value)} />
          </>
        )}
      </div>
    </div>
  );
}

function DiffLine({
  label,
  value,
  muted,
  strike,
}: {
  label: string;
  value: string;
  muted?: boolean;
  strike?: boolean;
}) {
  return (
    <div className="text-sm">
      <p className="text-xs text-muted-foreground">{label}:</p>
      <p className={muted ? 'text-muted-foreground' : undefined}>
        <span className={strike ? 'line-through decoration-muted-foreground/60' : undefined}>{value}</span>
      </p>
    </div>
  );
}

function isLongSuggestion(change: OfferAiChange): boolean {
  if (LONG_FIELDS.has(change.field)) return true;
  const oldText = formatOfferAiValue(change.field, change.old_value);
  const newText = formatOfferAiValue(change.field, change.new_value);
  return oldText.length > 140 || newText.length > 140;
}

function trafficDelta(change: OfferAiChange): { label: string; value: string } | null {
  if (change.field !== 'allowed_traffic' && change.field !== 'forbidden_traffic') return null;
  const oldItems = Array.isArray(change.old_value) ? change.old_value.map(String) : [];
  const newItems = Array.isArray(change.new_value) ? change.new_value.map(String) : [];
  const oldSet = new Set(oldItems);
  const newSet = new Set(newItems);
  const added = newItems.filter((item) => !oldSet.has(item));
  const removed = oldItems.filter((item) => !newSet.has(item));
  if (added.length > 0 && removed.length === 0) {
    return { label: 'Добавить', value: formatOfferAiValue(change.field, added) };
  }
  if (removed.length > 0 && added.length === 0) {
    return { label: 'Убрать', value: formatOfferAiValue(change.field, removed) };
  }
  return null;
}

function unchangedLabels(changes: OfferAiChange[]): string[] {
  const changed = new Set(changes.map((change) => change.field));
  const labels: string[] = [];
  if (!COMMISSION_FIELDS.some((field) => changed.has(field))) labels.push('Комиссия');
  for (const [field, label] of Object.entries(OFFER_AI_FIELD_LABELS)) {
    if (COMMISSION_FIELDS.includes(field) || changed.has(field)) continue;
    labels.push(label);
  }
  return labels;
}

function changeWord(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return 'изменение';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'изменения';
  return 'изменений';
}

function fieldWord(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return 'поле';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'поля';
  return 'полей';
}
