export type EntityType = "definition" | "object" | "method" | "property" | "topic" | "notation" | "primitive" | string;
export type LocalRole = "main" | "supporting" | "background" | "frontier" | string;
export type Adequacy = "adequate" | "needs_one_layer" | "conflict" | "unclear" | string;
export type Confidence = "high" | "medium" | "low" | string;

export interface EvidenceSpan {
  quote: string;
  section: string;
}

export interface Paper {
  id: string;
  title: string;
  mrnumber?: number;
  authors?: string[];
  doi?: string;
  doi_url?: string;
  journal?: string;
  year?: number;
  volume?: string;
  number?: string;
  pages?: string;
  page_count_estimate?: number;
  primary_msc?: string;
  primary_msc_description?: string;
  citation_count?: number;
  item_type?: string;
  entry_type?: string;
  selection_tags?: string[];
  topic_selection?: string;
}

export interface ConceptNode {
  id: string;
  label: string;
  entity_type?: EntityType;
  ontology_status?: string;
  ontology_statuses?: string[];
  local_role?: LocalRole;
  aliases?: string[];
  summary?: string;
  confidence?: Confidence;
  adequacy?: Adequacy;
  paper_ids?: string[];
  evidence?: EvidenceSpan[];
}

export interface ConceptEdge {
  id: string;
  dependent: string;
  prerequisite: string;
  relation: string;
  confidence?: Confidence;
  paper_ids?: string[];
  evidence?: EvidenceSpan[];
}

export interface GraphDataset {
  id?: string;
  title?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ConceptGraph {
  schema_version: string;
  dataset?: GraphDataset;
  papers: Paper[];
  nodes: ConceptNode[];
  edges: ConceptEdge[];
  validation?: Array<Record<string, unknown>>;
}
