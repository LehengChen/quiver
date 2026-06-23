import { useNavigate } from "react-router-dom";
import { ReviewTable, type ReviewTableRow } from "../../components/ReviewTable/ReviewTable";
import { adequacyLabel, confidenceLabel, contextReasonLabel, ontologyLabel, relationLabel, roleLabel } from "../../data/displayLabels";
import { useCollectionPath } from "../../hooks/useCollectionPath";
import type { SiteAnalysis } from "../../types/analysis";
import type { ConceptGraph } from "../../types/graph";
import type { ReviewTab } from "../../types/display";
import { useReviewPageState } from "./useReviewPageState";
import styles from "./ReviewPage.module.css";

interface ReviewPageProps {
  graph: ConceptGraph;
  analysis: SiteAnalysis;
}

const tabs: Array<{ id: ReviewTab; label: string }> = [
  { id: "context", label: "Needs background" },
  { id: "evidence", label: "Evidence coverage" },
  { id: "overlap", label: "Overlapping concepts" },
  { id: "reuse", label: "Reused concepts" },
  { id: "relations", label: "Relations" }
];

export function ReviewPage({ graph, analysis }: ReviewPageProps) {
  const { tab, setTab } = useReviewPageState();
  const navigate = useNavigate();
  const toCollectionPath = useCollectionPath();
  const rows = rowsForTab(tab, analysis);

  function onSelect(id: string) {
    if (tab === "evidence") navigate(toCollectionPath("graph", { paper: id }));
    else if (tab === "relations") navigate(toCollectionPath("graph", { relation: id }));
    else navigate(toCollectionPath("graph", { node: id }));
  }

  return (
    <div className={styles.page}>
      <section className={styles.header}>
        <div>
          <h2>Review the concept collection</h2>
          <p>
            These views highlight concepts that need more background, evidence coverage gaps, overlapping definitions, recurring concepts, and
            relation distribution across {graph.papers.length} papers.
          </p>
        </div>
      </section>
      <div className={styles.tabs} role="tablist" aria-label="Review views">
        {tabs.map((item) => (
          <button key={item.id} type="button" className={item.id === tab ? styles.active : ""} onClick={() => setTab(item.id)}>
            {item.label}
          </button>
        ))}
      </div>
      <ReviewTable rows={rows} onSelect={onSelect} />
    </div>
  );
}

function rowsForTab(tab: ReviewTab, analysis: SiteAnalysis): ReviewTableRow[] {
  if (tab === "context") {
    return analysis.frontier_nodes.map((node) => ({
      id: node.id,
      title: node.label,
      subtitle: contextReasonLabel(node.adequacy, node.confidence, node.local_role),
      tags: [adequacyLabel(node.adequacy), confidenceLabel(node.confidence), roleLabel(node.local_role)].filter(Boolean),
      metric: node.paper_ids.length
    }));
  }
  if (tab === "evidence") {
    return [...analysis.paper_summaries]
      .sort((left, right) => right.evidence_warnings - left.evidence_warnings)
      .filter((paper) => paper.evidence_warnings > 0)
      .map((paper) => ({
        id: paper.id,
        title: paper.title,
        subtitle: `${paper.concepts} concepts, ${paper.dependency_links} dependency links`,
        metric: `+${paper.evidence_warnings}`
      }));
  }
  if (tab === "overlap") {
    return analysis.overlap_warnings.map((node) => ({
      id: node.id,
      title: node.label,
      subtitle: node.paper_ids.join(", "),
      tags: node.ontology_statuses.map(ontologyLabel),
      metric: node.paper_ids.length
    }));
  }
  if (tab === "reuse") {
    return analysis.reused_nodes.map((node) => ({
      id: node.id,
      title: node.label,
      subtitle: node.paper_ids.join(", "),
      metric: node.paper_count
    }));
  }
  return analysis.counts.relations.map((relation) => ({
    id: relation.key,
    title: relationLabel(relation.key),
    subtitle: analysis.relation_groups.topical.includes(relation.key) ? "Topic grouping" : "Dependency link",
    metric: relation.count
  }));
}
