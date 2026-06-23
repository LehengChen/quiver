"""Prompt construction for graph-delta extraction."""

from __future__ import annotations

import json
from typing import Any


def build_extract_prompt(package: dict[str, Any]) -> str:
    paper = package.get("paper", {})
    context = {
        "paper": paper,
        "existing_graph_summary": package.get("existing_graph_summary", {}),
        "local_search_results": package.get("local_search_results", []),
        "allowed_existing_nodes": package.get("allowed_existing_nodes", []),
        "extraction_policy": package.get("extraction_policy", {}),
    }
    example = {
        "schema_version": "quiver.graph_delta.v1",
        "paper_id": paper.get("id", ""),
        "paper_title": paper.get("title", ""),
        "nodes": [
            {
                "canonical_id": "stable_snake_case_id",
                "label": "Human readable name",
                "entity_type": "definition | object | method | property | topic | notation | primitive",
                "ontology_status": "new | existing | refined | uncertain",
                "local_role": "main | supporting | background | frontier",
                "aliases": [],
                "summary": "One or two sentence definition.",
                "evidence": [{"quote": "short exact evidence span", "section": "section name or empty string"}],
                "confidence": "high | medium | low",
                "adequacy": "adequate | needs_one_layer | conflict | unclear",
            }
        ],
        "edges": [
            {
                "dependent": "canonical_id",
                "prerequisite": "canonical_id",
                "relation": "definition_depends_on | uses_method | has_property | constructed_using | specializes | belongs_to_topic | has_primitive | computed_by",
                "evidence": [{"quote": "short exact evidence span", "section": "section name or empty string"}],
                "confidence": "high | medium | low",
            }
        ],
        "notes": [],
    }
    return f"""You are extracting a concept dependency graph delta from one math paper.

Return JSON only. Do not wrap it in Markdown.

Task:
- Read the paper excerpt.
- Extract only concepts that are needed to understand or formalize the paper.
- Use local_search_results to avoid duplicating existing concepts.
- allowed_existing_nodes contains existing graph nodes that may be reused directly.
- If a concept already exists and its definition/dependencies look adequate, reuse it and do not expand it.
- Any concept used as an edge endpoint must appear in nodes. For an existing adequate concept, include a lightweight node with ontology_status "existing" and adequacy "adequate".
- Expand at most one dependency layer beyond the paper's own frontier, only when a definition is unclear, dependencies are incomplete, supporting concepts are missing, or an existing graph item appears wrong.
- Prefer explicit mathematical definitions over broad topics.

Concept node eligibility:
- Nodes must be reusable mathematical concepts: objects, definitions, properties, constructions, methods, topics, notation, or primitives.
- Do not create theorem/lemma/proposition/corollary nodes.
- Do not use paper-local result labels such as "Theorem 2.1", "Lemma 3.4", "Proposition 1.7", "Corollary 2.9", "Definition 1.1", "Remark 4.3", or ids like "theorem_2_1" as canonical_id, label, or alias.
- Numbered result references may appear only inside evidence quotes or section names.
- If a numbered theorem states a reusable mathematical idea, name the underlying idea directly, e.g. a property, conjecture, construction, method, or named field-recognizable theorem without the paper-local number.
- If the excerpt only says that an unstated theorem uses another result, omit the unstated theorem as a node and mention the omission in notes.

Edge direction:
- Use explicit fields, never implicit arrow direction.
- dependent = the concept being defined, constructed, computed, specialized, or explained.
- prerequisite = the concept it depends on.
- Example: a quiver representation depends on a quiver, so dependent is "quiver_representation" and prerequisite is "quiver".
- Relation names are dependency predicates. Use "computed_by" when a quantity or invariant is computed by a method, and use "uses_method" when a concept depends on a method or formalism.

Required JSON schema shape:
{json.dumps(example, indent=2, ensure_ascii=False)}

Context package:
{json.dumps(context, indent=2, ensure_ascii=False)}

Paper excerpt:
<<<PAPER_EXCERPT
{package.get("source_excerpt", "")}
PAPER_EXCERPT
"""
