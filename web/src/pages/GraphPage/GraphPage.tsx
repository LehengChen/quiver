import { type PointerEvent, useMemo } from "react";
import { FiltersPanel } from "../../components/FiltersPanel/FiltersPanel";
import { GraphCanvas } from "../../components/GraphCanvas/GraphCanvas";
import { InspectorPanel } from "../../components/InspectorPanel/InspectorPanel";
import { PaperMeta } from "../../components/PaperMeta/PaperMeta";
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
  const selectedPaper = filters.paperId ? graph.papers.find((paper) => paper.id === filters.paperId) : undefined;
  const selectedPaperSummary = filters.paperId ? analysis.paper_summaries.find((paper) => paper.id === filters.paperId) : undefined;
  const visibleSelectedNodeId = filtered.visibleNodeIds.has(selectedNodeId) ? selectedNodeId : "";

  function onPagePointerDown(event: PointerEvent<HTMLDivElement>) {
    if (!selectedNodeId || event.button !== 0) return;
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (
      target.closest(
        [
          '[aria-label="Concept dependency graph"]',
          '[aria-label="Concept details"]',
          "[data-node]",
          "a",
          "button",
          "input",
          "select",
          "textarea",
          "[role='button']"
        ].join(",")
      )
    ) {
      return;
    }
    clearSelection();
  }

  return (
    <div className={styles.page} onPointerDownCapture={onPagePointerDown}>
      <FiltersPanel
        graph={graph}
        analysis={analysis}
        filters={filters}
        onChange={updateFilters}
        onReset={resetGraph}
      />
      {selectedPaper ? <PaperMeta paper={selectedPaper} summary={selectedPaperSummary} compact /> : null}
      <div className={styles.mapStage}>
        <GraphCanvas
          nodes={filtered.nodes}
          edges={filtered.edges}
          indexes={indexes}
          degreeByNode={referenceByNode}
          selectedNodeId={visibleSelectedNodeId}
          onClearSelection={clearSelection}
          onSelectNode={selectNode}
        />
        <InspectorPanel selectedNode={selectedNode} indexes={indexes} onClose={clearSelection} onSelectNode={selectNode} />
      </div>
    </div>
  );
}
