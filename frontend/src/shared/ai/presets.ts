export const AI_GUIDANCE_PRESETS = [
  { id: 'clearer', label: 'Сделать понятнее' },
  { id: 'shorter', label: 'Сделать короче' },
  { id: 'selling', label: 'Сделать более продающим' },
  { id: 'structure', label: 'Улучшить структуру' },
  { id: 'dedupe', label: 'Убрать повторы' },
] as const;

export const AI_REWRITE_PRESETS = [
  ...AI_GUIDANCE_PRESETS,
  { id: 'tone', label: 'Изменить тон' },
] as const;

export type AiGuidancePresetId = (typeof AI_REWRITE_PRESETS)[number]['id'];

/** Whole-offer AI edit may still combine a preset with optional free-text. */
export type AiGuidanceRequest = {
  preset?: AiGuidancePresetId;
  guidance?: string;
};

/** Field rewrite accepts only a fixed technical improvement type. */
export type AiRewriteRequest = {
  preset: AiGuidancePresetId;
};

export function canSubmitAiGuidance(request: { preset?: string | null; guidance?: string | null }): boolean {
  return Boolean((request.preset && request.preset.trim()) || (request.guidance && request.guidance.trim()));
}

export function canSubmitAiRewrite(request: { preset?: string | null }): boolean {
  return Boolean(request.preset && AI_REWRITE_PRESETS.some((item) => item.id === request.preset));
}

export function toAiGuidancePayload(request: AiGuidanceRequest): { preset?: string; guidance?: string } {
  const preset = request.preset?.trim();
  const guidance = request.guidance?.trim();
  return {
    ...(preset ? { preset } : {}),
    ...(guidance ? { guidance } : {}),
  };
}

export function toAiRewritePayload(request: AiRewriteRequest): { preset: string } {
  return { preset: request.preset };
}
