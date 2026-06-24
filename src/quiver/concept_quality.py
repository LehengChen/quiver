"""Shared concept-node quality checks."""

from __future__ import annotations

import re
from typing import Any

RESULT_KINDS = {
    "theorem",
    "lemma",
    "proposition",
    "corollary",
    "definition",
    "example",
    "remark",
    "conjecture",
    "claim",
    "assertion",
}

DOCUMENT_RESULT_REF_RE = re.compile(
    r"\b("
    + "|".join(sorted(RESULT_KINDS))
    + r")\s+[A-Z]?\d+(?:\.\d+)*(?:[a-z])?\b",
    re.IGNORECASE,
)


def has_document_result_ref(text: str | None) -> bool:
    """Return true when text contains a paper-local numbered result reference."""
    return bool(text and DOCUMENT_RESULT_REF_RE.search(text))


def has_document_result_id(text: str | None) -> bool:
    """Return true for ids like theorem_2_1 or corrected_lemma_2_40."""
    if not text:
        return False
    parts = [part for part in re.split(r"[_\W]+", text.lower()) if part]
    for idx, part in enumerate(parts):
        if part in RESULT_KINDS and _looks_like_result_number(
            parts[idx + 1 :],
            allow_single_number_suffix=part != "conjecture",
        ):
            return True
    return False


def _looks_like_result_number(parts: list[str], *, allow_single_number_suffix: bool) -> bool:
    """Match paper-local result numbers without rejecting named concepts.

    Local result ids usually encode labels like ``lemma_2_40`` or
    ``theorem_a_1``.  A single dimension token in a named concept, such as
    ``smale_conjecture_3_manifolds``, should remain valid.
    """
    if not parts:
        return False
    first = parts[0]
    if _looks_like_result_number_token(first):
        return (
            len(parts) == 1
            or (len(parts) > 1 and _looks_like_result_number_token(parts[1]))
            or allow_single_number_suffix
        )
    if re.fullmatch(r"[a-z]|[ivxlcdm]+", first) and len(parts) > 1:
        return _looks_like_result_number_token(parts[1])
    return False


def _looks_like_result_number_token(part: str) -> bool:
    return bool(re.fullmatch(r"\d+[a-z]?", part))


def concept_node_exclusion_reason(node: dict[str, Any]) -> str | None:
    """Explain why a node should not enter the reusable concept graph."""
    entity_type = str(node.get("entity_type") or "").lower()
    if entity_type == "theorem":
        return "theorem nodes are not part of the concept graph; extract the underlying object, property, construction, or method"

    canonical_id = str(node.get("id") or node.get("canonical_id") or "")
    if has_document_result_id(canonical_id):
        return "canonical_id encodes a paper-local numbered theorem/lemma/proposition"

    label = str(node.get("label") or node.get("canonical_name") or node.get("display_name") or "")
    if has_document_result_ref(label):
        return "label contains a paper-local numbered theorem/lemma/proposition reference"

    for alias in node.get("aliases", []) or []:
        if has_document_result_ref(str(alias)):
            return "alias contains a paper-local numbered theorem/lemma/proposition reference"

    return None
