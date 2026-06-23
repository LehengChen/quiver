const ROLE_LABELS: Record<string, string> = {
  background: "Background",
  supporting: "Supporting concept",
  main: "Central concept",
  frontier: "Needs background"
};

const ADEQUACY_LABELS: Record<string, string> = {
  adequate: "Enough background",
  needs_one_layer: "Needs one more layer",
  unclear: "Unclear background",
  conflict: "Conflicting background"
};

const CONFIDENCE_LABELS: Record<string, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence"
};

const RELATION_LABELS: Record<string, string> = {
  definition_depends_on: "Definition depends on",
  uses_method: "Uses method",
  has_property: "Has property",
  constructed_using: "Constructed using",
  specializes: "Specializes",
  belongs_to_topic: "Belongs to topic",
  has_primitive: "Has primitive",
  computed_by: "Computed by"
};

const ONTOLOGY_LABELS: Record<string, string> = {
  new: "New in this collection",
  existing: "Previously established",
  refined: "Refined here",
  uncertain: "Needs review"
};

export function titleCaseToken(value?: string): string {
  if (!value) return "";
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function roleLabel(value?: string): string {
  return value ? ROLE_LABELS[value] || titleCaseToken(value) : "";
}

export function adequacyLabel(value?: string): string {
  return value ? ADEQUACY_LABELS[value] || titleCaseToken(value) : "";
}

export function confidenceLabel(value?: string): string {
  return value ? CONFIDENCE_LABELS[value] || titleCaseToken(value) : "";
}

export function relationLabel(value?: string): string {
  return value ? RELATION_LABELS[value] || titleCaseToken(value) : "";
}

export function ontologyLabel(value?: string): string {
  return value ? ONTOLOGY_LABELS[value] || titleCaseToken(value) : "";
}

export function contextReasonLabel(adequacy?: string, confidence?: string, role?: string): string {
  const reasons = [adequacy && adequacy !== "adequate" ? adequacyLabel(adequacy) : "", confidence === "low" ? "Low confidence" : ""].filter(
    Boolean
  );
  if (!reasons.length && role === "frontier") return "Needs more background";
  return reasons.join("; ") || "Needs more background";
}
