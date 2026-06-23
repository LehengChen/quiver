export interface CountBucket {
  key: string;
  count: number;
}

export interface PaperSummary {
  id: string;
  title: string;
  concepts: number;
  unique_concepts: number;
  reused_concepts: number;
  dependency_links: number;
  evidence_warnings: number;
  concepts_needing_context: number;
}

export interface ReviewConcept {
  id: string;
  label: string;
  reason: string;
  adequacy?: string;
  confidence?: string;
  local_role?: string;
  paper_ids: string[];
}

export interface ReusedConcept {
  id: string;
  label: string;
  paper_ids: string[];
  paper_count: number;
}

export interface OverlapWarning {
  id: string;
  label: string;
  ontology_statuses: string[];
  paper_ids: string[];
}

export interface RelationGroup {
  strict_dependency: string[];
  topical: string[];
}

export interface SiteAnalysis {
  schema_version: string;
  generated_at: string;
  summary: {
    papers: number;
    concepts: number;
    dependencies: number;
    concepts_needing_context: number;
    reused_concepts: number;
    overlapping_concepts: number;
    evidence_warnings: number;
  };
  counts: {
    relations: CountBucket[];
    entity_types: CountBucket[];
    local_roles: CountBucket[];
    adequacy: CountBucket[];
    confidence: CountBucket[];
  };
  paper_summaries: PaperSummary[];
  frontier_nodes: ReviewConcept[];
  reused_nodes: ReusedConcept[];
  overlap_warnings: OverlapWarning[];
  relation_groups: RelationGroup;
}
