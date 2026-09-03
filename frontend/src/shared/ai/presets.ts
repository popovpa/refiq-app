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

export type AiGuidanceRequest = {
  preset?: AiGuidancePresetId;
  guidance?: string;
};

export function canSubmitAiGuidance(request: { preset?: string | null; guidance?: string | null }): boolean {
  return Boolean((request.preset && request.preset.trim()) || (request.guidance && request.guidance.trim()));
}

export function toAiGuidancePayload(request: AiGuidanceRequest): { preset?: string; guidance?: string } {
  const preset = request.preset?.trim();
  const guidance = request.guidance?.trim();
  return {
    ...(preset ? { preset } : {}),
    ...(guidance ? { guidance } : {}),
  };
}
