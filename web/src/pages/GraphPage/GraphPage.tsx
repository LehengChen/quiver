import { useMemo } from "react";
import { FiltersPanel } from "../../components/FiltersPanel/FiltersPanel";
import { GraphCanvas } from "../../components/GraphCanvas/GraphCanvas";
import { InspectorPanel } from "../../components/InspectorPanel/InspectorPanel";
import { buildGraphIndexes } from "../../data/graphIndexes";
import { nodeReferenceCounts, selectFilteredGraph } from "../../data/selectors";
import type { SiteAnalysis } from "../../types/analysis";
import type { ConceptGraph } from "../../types/graph";
import { useGraphPageState } from "./useGraphPageState";
import styles from "./GraphPage.module.css";

interface GraphPageProps {
  graph: ConceptGraph;
  analysis: SiteAnalysis;
}

export function GraphPage({ graph, analysis }: GraphPageProps) {
  const indexes = useMemo(() => buildGraphIndexes(graph), [graph]);
  const referenceByNode = useMemo(() => nodeReferenceCounts(graph), [graph]);
  const { filters, selectedNodeId, updateFilters, selectNode, clearSelection, resetGraph } = useGraphPageState();
  const filtered = useMemo(() => selectFilteredGraph(graph, filters), [filters, graph]);
  const selectedNode = selectedNodeId ? indexes.nodesById.get(selectedNodeId) : undefined;
  const visibleSelectedNodeId = filtered.visibleNodeIds.has(selectedNodeId) ? selectedNodeId : "";
  const hasSelection = Boolean(selectedNodeId);

  return (
    <div className={styles.page}>
      <FiltersPanel
        graph={graph}
        analysis={analysis}
        filters={filters}
        hasSelection={hasSelection}
        onChange={updateFilters}
        onClearSelection={clearSelection}
        onReset={resetGraph}
      />
      <div className={styles.mapStage}>
        <GraphCanvas
          nodes={filtered.nodes}
          edges={filtered.edges}
          indexes={indexes}
          degreeByNode={referenceByNode}
          selectedNodeId={visibleSelectedNodeId}
          hasSelection={hasSelection}
          onClearSelection={clearSelection}
          onSelectNode={selectNode}
        />
        <InspectorPanel selectedNode={selectedNode} indexes={indexes} onClose={clearSelection} onSelectNode={selectNode} />
      </div>
    </div>
  );
}
