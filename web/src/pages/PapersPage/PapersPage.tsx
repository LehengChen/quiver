import type { ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ReviewTable } from "../../components/ReviewTable/ReviewTable";
import { EvidenceList } from "../../components/EvidenceList/EvidenceList";
import { RichText } from "../../components/RichText/RichText";
import { useCollectionPath } from "../../hooks/useCollectionPath";
import type { SiteAnalysis } from "../../types/analysis";
import type { ConceptEdge, ConceptGraph, ConceptNode } from "../../types/graph";
import styles from "./PapersPage.module.css";

interface PapersPageProps {
  graph: ConceptGraph;
  analysis: SiteAnalysis;
}

export function PapersPage({ graph, analysis }: PapersPageProps) {
  const navigate = useNavigate();
  const toCollectionPath = useCollectionPath();
  const [params] = useSearchParams();
  const selectedPaperId = params.get("paper") || "";
  const selectedNodeId = params.get("node") || "";
  const selectedPaper = selectedPaperId ? graph.papers.find((paper) => paper.id === selectedPaperId) : undefined;
  const selectedNode = selectedNodeId ? graph.nodes.find((node) => node.id === selectedNodeId) : undefined;
  const selectedPaperSummary = selectedPaperId ? analysis.paper_summaries.find((paper) => paper.id === selectedPaperId) : undefined;
  const rows = analysis.paper_summaries.map((paper) => ({
    id: paper.id,
    title: paper.title,
    subtitle: `${paper.concepts} concepts, ${paper.unique_concepts} unique here, ${paper.reused_concepts} reused, ${paper.dependency_links} links`,
    tags: paper.concepts_needing_context ? [`${paper.concepts_needing_context} need background`] : [],
    metric: paper.evidence_warnings ? `+${paper.evidence_warnings}` : undefined
  }));

  return (
    <div className={styles.page}>
      <section className={styles.header}>
        <h2>Papers in this collection</h2>
        <p>
          Browse {graph.papers.length} papers by introduced concepts, reused concepts, dependency links, and evidence coverage.
        </p>
      </section>
      {selectedPaper ? (
        <PaperSupportPanel
          graph={graph}
          paperId={selectedPaper.id}
          paperTitle={selectedPaper.title}
          paperSummary={selectedPaperSummary}
          selectedNode={selectedNode}
        />
      ) : null}
      <ReviewTable
        rows={rows}
        onSelect={(paperId) => {
          navigate(toCollectionPath("graph", { paper: paperId, node: selectedNodeId }));
        }}
      />
    </div>
  );
}

function PaperSupportPanel({
  graph,
  paperId,
  paperTitle,
  paperSummary,
  selectedNode
}: {
  graph: ConceptGraph;
  paperId: string;
  paperTitle: string;
  paperSummary?: SiteAnalysis["paper_summaries"][number];
  selectedNode?: ConceptNode;
}) {
  const nodeAppearsInPaper = selectedNode ? (selectedNode.paper_ids || []).includes(paperId) : false;
  const incoming = selectedNode ? paperEdges(graph, selectedNode.id, paperId, "incoming") : [];
  const outgoing = selectedNode ? paperEdges(graph, selectedNode.id, paperId, "outgoing") : [];
  const toCollectionPath = useCollectionPath();

  return (
    <section className={styles.supportPanel} aria-label="Paper support details">
      <div className={styles.supportHeader}>
        <div>
          <span className={styles.eyebrow}>Paper support</span>
          <h3>
            <RichText text={paperTitle || paperId} inline />
          </h3>
          {paperSummary ? (
            <p>
              {paperSummary.concepts} concepts, {paperSummary.unique_concepts} unique here, {paperSummary.dependency_links} links
            </p>
          ) : null}
        </div>
        <Link to={toCollectionPath("graph", { paper: paperId, node: selectedNode?.id })}>
          Open in graph
        </Link>
      </div>
      {selectedNode ? (
        <div className={styles.nodeSupport}>
          <div className={styles.nodeTitle}>
            <span className={styles.eyebrow}>Selected concept</span>
            <strong>
              <RichText text={selectedNode.label || selectedNode.id} inline />
            </strong>
          </div>
          {!nodeAppearsInPaper ? (
            <p className={styles.empty}>This concept is not attached directly to this paper, but related edges may still be listed if present.</p>
          ) : null}
          <div className={styles.supportGrid}>
            <SupportColumn title="Concept evidence">
              <EvidenceList evidence={nodeAppearsInPaper ? selectedNode.evidence : []} limit={6} />
            </SupportColumn>
            <SupportColumn title="Supports in this paper">
              <EdgeList edges={outgoing} graph={graph} direction="outgoing" />
            </SupportColumn>
            <SupportColumn title="Depends on in this paper">
              <EdgeList edges={incoming} graph={graph} direction="incoming" />
            </SupportColumn>
          </div>
        </div>
      ) : (
        <p className={styles.empty}>Select a concept from the graph to inspect its support for this paper.</p>
      )}
    </section>
  );
}

function SupportColumn({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className={styles.supportColumn}>
      <h4>{title}</h4>
      {children}
    </div>
  );
}

function EdgeList({ edges, graph, direction }: { edges: ConceptEdge[]; graph: ConceptGraph; direction: "incoming" | "outgoing" }) {
  if (!edges.length) {
    return <p className={styles.empty}>No dependency link in this paper.</p>;
  }
  return (
    <ul className={styles.edgeList}>
      {edges.map((edge) => {
        const otherId = direction === "outgoing" ? edge.dependent : edge.prerequisite;
        const other = graph.nodes.find((node) => node.id === otherId);
        return (
          <li key={edge.id}>
            <strong>
              <RichText text={other?.label || otherId} inline />
            </strong>
            <span className={styles.edgeRelation}>{edge.relation.replaceAll("_", " ")}</span>
            <EvidenceList evidence={edge.evidence} limit={2} />
          </li>
        );
      })}
    </ul>
  );
}

function paperEdges(graph: ConceptGraph, nodeId: string, paperId: string, direction: "incoming" | "outgoing"): ConceptEdge[] {
  return graph.edges.filter((edge) => {
    if (!(edge.paper_ids || []).includes(paperId)) return false;
    if (direction === "incoming") return edge.dependent === nodeId;
    return edge.prerequisite === nodeId;
  });
}
