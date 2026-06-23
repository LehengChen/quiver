import { Link, useNavigate } from "react-router-dom";
import { StatsBar } from "../../components/StatsBar/StatsBar";
import { ReviewTable } from "../../components/ReviewTable/ReviewTable";
import { highWarningPapers } from "../../data/selectors";
import { useCollectionPath } from "../../hooks/useCollectionPath";
import type { SiteAnalysis } from "../../types/analysis";
import type { ConceptGraph } from "../../types/graph";
import styles from "./OverviewPage.module.css";

interface OverviewPageProps {
  graph: ConceptGraph;
  analysis: SiteAnalysis;
}

export function OverviewPage({ graph, analysis }: OverviewPageProps) {
  const navigate = useNavigate();
  const toCollectionPath = useCollectionPath();
  const warningRows = highWarningPapers(analysis)
    .slice(0, 5)
    .map((paper) => ({
      id: paper.id,
      title: paper.title,
      subtitle: `${paper.concepts} concepts, ${paper.dependency_links} links`,
      metric: `+${paper.evidence_warnings}`
    }));

  const reusedRows = analysis.reused_nodes.slice(0, 5).map((node) => ({
    id: node.id,
    title: node.label,
    subtitle: node.paper_ids.join(", "),
    metric: node.paper_count
  }));

  return (
    <div className={styles.page}>
      <section className={styles.intro}>
        <div>
          <h2>Concept structure across {graph.papers.length} papers</h2>
          <p>
            Explore the concepts in this collection, how they depend on each other, which ideas recur across papers, and which
            areas need more background or evidence review.
          </p>
        </div>
        <div className={styles.actions}>
          <Link to={toCollectionPath("graph")}>Open concept map</Link>
          <Link to={toCollectionPath("review")}>Review evidence</Link>
        </div>
      </section>
      <StatsBar analysis={analysis} />
      <section className={styles.grid}>
        <div>
          <div className={styles.sectionTitle}>
            <h3>Evidence coverage hotspots</h3>
            <Link to={toCollectionPath("review", { tab: "evidence" })}>View all</Link>
          </div>
          <ReviewTable rows={warningRows} onSelect={(paperId) => navigate(toCollectionPath("graph", { paper: paperId }))} />
        </div>
        <div>
          <div className={styles.sectionTitle}>
            <h3>Concepts reused across papers</h3>
            <Link to={toCollectionPath("review", { tab: "reuse" })}>View all</Link>
          </div>
          <ReviewTable rows={reusedRows} onSelect={(nodeId) => navigate(toCollectionPath("graph", { node: nodeId }))} />
        </div>
      </section>
    </div>
  );
}
