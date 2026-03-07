"""
Memory hygiene helpers.

Kalici kullanici hafizasina sadece stabil tercihlerin girmesini saglar.
Anlik gorev parametreleri (sure, adet, model, son asset vb.) filtrelenir.
"""
from __future__ import annotations

import re


ALLOWED_LEARNED_CATEGORIES = {
    "style",
    "identity",
    "brand",
    "general",
    "workflow",
    "preferred_colors",
}

ALLOWED_STYLE_PREFERENCE_KEYS = {
    "active_style",
    "style_description",
    "color_palette",
}

_MODEL_KEYWORDS = (
    "kling",
    "veo",
    "veo 3",
    "veo 3.1",
    "sora",
    "sora2",
    "seedance",
    "hailuo",
    "luma",
    "runway",
    "pika",
    "nano banana",
    "gpt_image",
    "gpt image",
    "flux",
    "recraft",
    "reve",
)

_TRANSIENT_PATTERNS = (
    re.compile(r"\b\d+\s*(?:saniye(?:lik)?|sn|sec(?:ond)?s?|dakika(?:lik)?|min(?:ute)?s?)\b", re.IGNORECASE),
    re.compile(r"\b(?:duration|sure|süre)\s*[:=]?\s*\d+\b", re.IGNORECASE),
    re.compile(r"\b\d+\s*(?:gorsel|görsel|image|video|varyasyon|variation|adet|tane)\b", re.IGNORECASE),
    re.compile(r"\b(?:bu sefer|simdilik|şimdilik|su an|şu an|az once|az önce|hemen|tek seferlik)\b", re.IGNORECASE),
    re.compile(r"\b(?:son|last)\s+(?:gorsel|görsel|image|video|asset|cikti|çıktı)\b", re.IGNORECASE),
    re.compile(r"https?://\S+", re.IGNORECASE),
)

_DURATION_PATTERN = re.compile(
    r"\b(?P<value>\d+)\s*(?:saniye(?:lik)?|sn|sec(?:ond)?s?|dakika(?:lik)?|min(?:ute)?s?)\b",
    re.IGNORECASE,
)
_COUNT_PATTERN = re.compile(
    r"\b(?P<value>\d+)\s*(?P<unit>gorsel|görsel|image|video|varyasyon|variation|adet|tane)\b",
    re.IGNORECASE,
)
_MULTISPACE_PATTERN = re.compile(r"\s+")
_PUNCT_PATTERN = re.compile(r"[^\w\s]", re.UNICODE)
_STOPWORDS = {
    "bir",
    "ve",
    "ile",
    "icin",
    "için",
    "ama",
    "gibi",
    "olan",
    "olanin",
    "olsun",
    "bana",
    "bunu",
    "bunun",
    "bunuza",
    "kullanici",
    "kullanıcı",
    "icin",
    "gore",
    "göre",
    "daha",
    "then",
    "this",
    "that",
    "with",
    "from",
    "into",
    "like",
    "only",
    "just",
    "create",
    "make",
    "olan",
}


def sanitize_memory_text(text: str) -> str:
    """Anlik gorev parametrelerini metinden temizle."""
    if not text:
        return ""

    cleaned = text.strip()
    for pattern in _TRANSIENT_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)

    for model_name in _MODEL_KEYWORDS:
        cleaned = re.sub(rf"\b{re.escape(model_name)}\b", " ", cleaned, flags=re.IGNORECASE)

    cleaned = cleaned.replace("()", " ").replace("[]", " ")
    cleaned = _MULTISPACE_PATTERN.sub(" ", cleaned).strip(" ,.;:-()[]")
    return cleaned


def is_stable_memory_fact(category: str | None, fact: str | None) -> bool:
    """Kalici hafizaya yazilabilecek kadar stabil mi?"""
    if not fact or not fact.strip():
        return False

    if category and category not in ALLOWED_LEARNED_CATEGORIES:
        return False

    for pattern in _TRANSIENT_PATTERNS:
        if pattern.search(fact):
            return False

    lowered = fact.lower()
    if any(model_name in lowered for model_name in _MODEL_KEYWORDS):
        return False

    sanitized = sanitize_memory_text(fact)
    minimum_length = 3 if category == "preferred_colors" else 8
    return len(sanitized) >= minimum_length


def tokenize_memory_text(text: str) -> set[str]:
    """Benzerlik icin hafiza dostu token seti uret."""
    sanitized = sanitize_memory_text(text).lower()
    sanitized = _PUNCT_PATTERN.sub(" ", sanitized)
    tokens = {
        token
        for token in sanitized.split()
        if len(token) > 2 and token not in _STOPWORDS and not token.isdigit()
    }
    return tokens


def extract_request_constraints(text: str) -> dict:
    """Metindeki acik sure/adet/model tercihlerinin izini cikar."""
    lowered = (text or "").lower()

    duration_match = _DURATION_PATTERN.search(lowered)
    count_match = _COUNT_PATTERN.search(lowered)

    models = {
        model_name
        for model_name in _MODEL_KEYWORDS
        if re.search(rf"\b{re.escape(model_name)}\b", lowered, flags=re.IGNORECASE)
    }

    return {
        "duration": int(duration_match.group("value")) if duration_match else None,
        "count": int(count_match.group("value")) if count_match else None,
        "count_unit": count_match.group("unit").lower() if count_match else None,
        "models": models,
    }


def has_conflicting_request_constraints(current_request: str, historical_prompt: str) -> bool:
    """Gecmis prompt, mevcut istegin acik parametreleriyle cakisiyor mu?"""
    current = extract_request_constraints(current_request)
    historical = extract_request_constraints(historical_prompt)

    if (
        current["duration"] is not None
        and historical["duration"] is not None
        and current["duration"] != historical["duration"]
    ):
        return True

    if (
        current["count"] is not None
        and historical["count"] is not None
        and current["count_unit"] == historical["count_unit"]
        and current["count"] != historical["count"]
    ):
        return True

    if current["models"] and historical["models"] and current["models"].isdisjoint(historical["models"]):
        return True

    return False
