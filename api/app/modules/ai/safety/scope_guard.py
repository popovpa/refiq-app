from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.modules.ai.safety.intents import GuidanceIntent
from app.modules.ai.safety.normalize import fold_for_match
from app.modules.ai.safety.policy import AiOperationPolicy, get_operation_policy
from app.modules.ai.safety.operations import AiOperation

MIXED_GUIDANCE_MESSAGE = (
    "Пожелание содержит инструкции, не относящиеся к редактированию текущего поля. "
    "Оставьте только пожелания к стилю, формулировке или содержанию на основе существующих данных."
)
OUT_OF_SCOPE_MESSAGE = (
    "Пожелание должно относиться к редактированию текущего поля "
    "и не должно добавлять неподтверждённые данные."
)
UNGROUNDED_FACT_MESSAGE = (
    "Нельзя добавлять факты, цены, числа или утверждения, которых нет в данных оффера. "
    "Измените соответствующие поля оффера, затем повторите улучшение."
)

_CALC_VERBS = (
    "результат выражения",
    "результат вычисления",
    "добавь результат",
    "вставь результат",
    "посчитай",
    "вычисли",
    "calculate",
    "compute",
    "add the result",
    "insert the result",
)
_CALC_EXPR = re.compile(
    r"(?:результат|посчитай|вычисли|calculate|compute|добавь|вставь).{0,40}"
    r"\d+\s*[+\-×xX*/÷]\s*\d+"
    r"|"
    r"\d+\s*[+\-×xX*/÷]\s*\d+.{0,40}(?:результат|назван|title|вставь|добавь)",
    re.I | re.S,
)
_PROGRAMMING = (
    "напиши на python",
    "написать на python",
    "пример на python",
    "python код",
    "flask",
    "fastapi",
    "rest api",
    "django",
    "javascript",
    "напиши код",
    "write code",
    "write a python",
)
_QA = (
    "что такое",
    "кто такой",
    "расскажи про",
    "объясни мне",
    "what is",
    "explain to me",
)
_ADD_FACT = (
    "добавь что",
    "добавь, что",
    "укажи что",
    "укажи, что",
    "добавь цену",
    "добавь скидку",
    "добавь гарантию",
    "работает лет",
    "гарантия",
    "скидка",
    "бесплатн",
    "add that",
    "add a price",
    "add discount",
)
_STYLE = (
    "стиль",
    "тон",
    "молодеж",
    "молодёж",
    "корпоратив",
    "делов",
    "продающ",
    "понятнее",
    "короче",
    "длиннее",
    "структур",
    "формулиров",
    "читаем",
    "акцент",
    "убедительн",
    "современн",
    "строг",
    "неформальн",
    "разговорн",
    "style",
    "tone",
    "shorter",
    "clearer",
)
_PERCENT_DISCOUNT = re.compile(
    r"(?:скидк\w*|discount).{0,20}\d+\s*%|\d+\s*%.{0,20}(?:скидк\w*|discount)",
    re.I,
)
_MADE_UP_PRICE = re.compile(
    r"(?:добавь|вставь|укажи).{0,30}(?:цен\w*|price).{0,20}\d[\d\s]{2,}",
    re.I,
)


@dataclass(frozen=True)
class ScopeInspection:
    allowed: bool
    category: str
    reason_code: str
    valid_intents: tuple[str, ...] = ()
    invalid_intents: tuple[str, ...] = ()
    message: str = OUT_OF_SCOPE_MESSAGE
    extra: dict = field(default_factory=dict)


def inspect_scope(
    text: str | None,
    *,
    operation: AiOperation,
    policy: AiOperationPolicy | None = None,
) -> ScopeInspection:
    policy = policy or get_operation_policy(operation)
    raw = (text or "").strip()
    if not raw:
        return ScopeInspection(True, "VALID_GUIDANCE", "OK")

    folded = fold_for_match(raw)
    valid: list[str] = []
    invalid: list[str] = []

    if any(marker in folded for marker in _STYLE):
        valid.append(GuidanceIntent.CHANGE_STYLE.value)
    if any(token in folded for token in ("короче", "shorter", "сжат")):
        valid.append(GuidanceIntent.SHORTEN.value)
    if any(token in folded for token in ("понятнее", "clearer", "яснее")):
        valid.append(GuidanceIntent.IMPROVE_CLARITY.value)
    if any(token in folded for token in ("структур", "structure")):
        valid.append(GuidanceIntent.IMPROVE_STRUCTURE.value)
    if any(token in folded for token in ("убери повтор", "дедуп", "без повтор", "dedupe")):
        valid.append(GuidanceIntent.REMOVE_REPETITION.value)

    if _has_calculation(raw, folded):
        invalid.append(GuidanceIntent.CALCULATION.value)
    if any(token in folded for token in _PROGRAMMING):
        invalid.append(GuidanceIntent.PROGRAMMING.value)
    if any(token in folded for token in _QA) and not valid:
        invalid.append(GuidanceIntent.GENERAL_QA.value)
    if _PERCENT_DISCOUNT.search(raw) or any(
        token in folded for token in ("добавь скидку", "вычисли скидку", "посчитай скидку")
    ):
        invalid.append(GuidanceIntent.ADD_UNVERIFIED_DISCOUNT.value)
    if _MADE_UP_PRICE.search(raw) or "добавь цену" in folded:
        invalid.append(GuidanceIntent.ADD_UNVERIFIED_PRICE.value)
    if any(token in folded for token in _ADD_FACT) and GuidanceIntent.CALCULATION.value not in invalid:
        # "добавь результат" already covered; remaining add-fact phrases
        if not _has_calculation(raw, folded):
            invalid.append(GuidanceIntent.ADD_UNVERIFIED_FACT.value)

    # Deduplicate while preserving order
    valid = list(dict.fromkeys(valid))
    invalid = list(dict.fromkeys(invalid))
    forbidden = {intent.value for intent in policy.forbidden_intents}
    invalid = [intent for intent in invalid if intent in forbidden]

    if invalid and valid:
        return ScopeInspection(
            False,
            "MIXED_VALID_AND_INVALID_GUIDANCE",
            "CONTAINS_OUT_OF_SCOPE_INSTRUCTION",
            tuple(valid),
            tuple(invalid),
            MIXED_GUIDANCE_MESSAGE,
        )
    if invalid:
        category = (
            "UNGROUNDED_FACT_REQUEST"
            if any(item.startswith("ADD_UNVERIFIED") or item == "CALCULATION" for item in invalid)
            else "OUT_OF_SCOPE"
        )
        message = UNGROUNDED_FACT_MESSAGE if category == "UNGROUNDED_FACT_REQUEST" else OUT_OF_SCOPE_MESSAGE
        if GuidanceIntent.CALCULATION.value in invalid and not valid:
            message = OUT_OF_SCOPE_MESSAGE
        return ScopeInspection(
            False,
            category,
            invalid[0],
            tuple(valid),
            tuple(invalid),
            message,
        )
    return ScopeInspection(True, "VALID_GUIDANCE", "OK", tuple(valid), ())


def _has_calculation(raw: str, folded: str) -> bool:
    if any(token in folded for token in _CALC_VERBS):
        return True
    return bool(_CALC_EXPR.search(raw))
