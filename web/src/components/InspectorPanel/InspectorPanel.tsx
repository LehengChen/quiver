import { X } from "lucide-react";
import { Link } from "react-router-dom";
import type { GraphIndexes } from "../../data/graphIndexes";
import { adequacyLabel, confidenceLabel, roleLabel, titleCaseToken } from "../../data/displayLabels";
import { paperTitle } from "../../data/selectors";
import { useCollectionPath } from "../../hooks/useCollectionPath";
import type { ConceptNode } from "../../types/graph";
import { EvidenceList } from "../EvidenceList/EvidenceList";
import { RichText } from "../RichText/RichText";
import styles from "./InspectorPanel.module.css";

interface InspectorPanelProps {
  selectedNode?: ConceptNode;
  indexes: GraphIndexes;
  onClose: () => void;
  onSelectNode: (nodeId: string) => void;
}

function NodeLink({ id, indexes, onSelectNode }: { id: string; indexes: GraphIndexes; onSelectNode: (nodeId: string) => void }) {
  const node = indexes.nodesById.get(id);
  return (
    <button className={styles.linkButton} type="button" onClick={() => onSelectNode(id)}>
      <RichText text={node?.label || id} inline />
    </button>
  );
}

export function InspectorPanel({ selectedNode, indexes, onClose, onSelectNode }: InspectorPanelProps) {
  const toCollectionPath = useCollectionPath();
  if (!selectedNode) return null;

  const incoming = indexes.incomingByNode.get(selectedNode.id) || [];
  const outgoing = indexes.outgoingByNode.get(selectedNode.id) || [];
  const papers = selectedNode.paper_ids || [];

  return (
    <aside className={styles.panel} aria-label="Concept details">
      <div className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Concept</p>
          <h2>
            <RichText text={selectedNode.label || selectedNode.id} inline />
          </h2>
        </div>
        <button type="button" onClick={onClose} aria-label="Close concept details" title="Close concept details">
          <X size={16} />
        </button>
      </div>
      <RichText className={styles.summary} text={selectedNode.summary || "No summary is attached."} />
      <div className={styles.metaGrid}>
        <Meta label="Type" value={titleCaseToken(selectedNode.entity_type)} />
        <Meta label="Role" value={roleLabel(selectedNode.local_role)} />
        <Meta label="Context" value={adequacyLabel(selectedNode.adequacy)} />
        <Meta label="Confidence" value={confidenceLabel(selectedNode.confidence)} />
      </div>
      <h3>Papers</h3>
      <div className={styles.paperLinks}>
        {papers.map((paperId) => (
          <Link key={paperId} to={toCollectionPath("graph", { paper: paperId, node: selectedNode.id })}>
            <span className={styles.paperTitle}>
              <RichText text={paperTitle(indexes, paperId)} inline />
            </span>
            <strong>Filter graph</strong>
          </Link>
        ))}
        {!papers.length ? <span className={styles.empty}>No paper link is attached.</span> : null}
      </div>
      {selectedNode.aliases?.length ? <Meta label="Aliases" value={selectedNode.aliases.join("; ")} /> : null}
      <h3>Depends on</h3>
      <div className={styles.stack}>
        {incoming.slice(0, 12).map((edge) => (
          <NodeLink key={edge.id} id={edge.prerequisite} indexes={indexes} onSelectNode={onSelectNode} />
        ))}
        {!incoming.length ? <span className={styles.empty}>No incoming dependencies.</span> : null}
      </div>
      <h3>Supports</h3>
      <div className={styles.stack}>
        {outgoing.slice(0, 12).map((edge) => (
          <NodeLink key={edge.id} id={edge.dependent} indexes={indexes} onSelectNode={onSelectNode} />
        ))}
        {!outgoing.length ? <span className={styles.empty}>No outgoing dependents.</span> : null}
      </div>
      <h3>Evidence</h3>
      <EvidenceList evidence={selectedNode.evidence} />
    </aside>
  );
}

function Meta({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <div className={styles.meta}>
      <span>{label}</span>
      <strong>
        <RichText text={value} inline />
      </strong>
    </div>
  );
}
