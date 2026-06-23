import type { SiteAnalysis } from "../types/analysis";
import type { GraphFilters } from "../types/filters";
import type { ConceptEdge, ConceptGraph, ConceptNode } from "../types/graph";
import type { GraphIndexes } from "./graphIndexes";

export interface FilteredGraph {
  nodes: ConceptNode[];
  edges: ConceptEdge[];
  visibleNodeIds: Set<string>;
}

export function nodeReferenceCounts(graph: ConceptGraph): Map<string, number> {
  const counts = new Map(graph.nodes.map((node) => [node.id, 0]));
  graph.edges.forEach((edge) => {
    if (edge.relation === "belongs_to_topic") return;
    const weight = Math.max(1, edge.paper_ids?.length || 0);
    if (counts.has(edge.prerequisite)) counts.set(edge.prerequisite, (counts.get(edge.prerequisite) || 0) + weight);
    if (counts.has(edge.dependent)) counts.set(edge.dependent, (counts.get(edge.dependent) || 0) + weight);
  });
  graph.nodes.forEach((node) => {
    const paperCount = node.paper_ids?.length || 0;
    if (paperCount > (counts.get(node.id) || 0)) counts.set(node.id, paperCount);
  });
  return counts;
}

function matchesQuery(node: ConceptNode, query: string): boolean {
  if (!query) return true;
  const haystack = [node.id, node.label, node.summary, ...(node.aliases || [])].join(" ").toLowerCase();
  return haystack.includes(query.toLowerCase());
}

function nodeTouchesPaper(node: ConceptNode, paperId: string): boolean {
  return !paperId || (node.paper_ids || []).includes(paperId);
}

function edgeTouchesPaper(edge: ConceptEdge, paperId: string): boolean {
  return !paperId || (edge.paper_ids || []).includes(paperId);
}

function edgeMatchesFilters(edge: ConceptEdge, filters: GraphFilters, visibleNodeIds: Set<string>): boolean {
  if (!visibleNodeIds.has(edge.dependent) || !visibleNodeIds.has(edge.prerequisite)) return false;
  if (filters.relation && edge.relation !== filters.relation) return false;
  if (!filters.relation && !filters.showTopical && edge.relation === "belongs_to_topic") return false;
  if (!edgeTouchesPaper(edge, filters.paperId)) return false;
  return true;
}

export function selectFilteredGraph(
  graph: ConceptGraph,
  filters: GraphFilters
): FilteredGraph {
  const referenceCounts = nodeReferenceCounts(graph);
  const baseNodes = graph.nodes.filter((node) => {
    if (!matchesQuery(node, filters.query)) return false;
    if (!nodeTouchesPaper(node, filters.paperId)) return false;
    if ((referenceCounts.get(node.id) || 0) < filters.minReferences) return false;
    if (filters.role && node.local_role !== filters.role) return false;
    if (filters.adequacy && node.adequacy !== filters.adequacy) return false;
    if (filters.confidence && node.confidence !== filters.confidence) return false;
    return true;
  });

  let visibleNodeIds = new Set(baseNodes.map((node) => node.id));
  let matchingEdges = graph.edges.filter((edge) => edgeMatchesFilters(edge, filters, visibleNodeIds));

  if (filters.relation) {
    visibleNodeIds = new Set<string>();
    matchingEdges.forEach((edge) => {
      visibleNodeIds.add(edge.dependent);
      visibleNodeIds.add(edge.prerequisite);
    });
  }

  const matchingEdgeIds = new Set(matchingEdges.map((edge) => edge.id));
  const edges = graph.edges.filter(
    (edge) => visibleNodeIds.has(edge.dependent) && visibleNodeIds.has(edge.prerequisite) && matchingEdgeIds.has(edge.id)
  );
  const nodes = graph.nodes.filter((node) => visibleNodeIds.has(node.id));

  return { nodes, edges, visibleNodeIds };
}

export function neighboringNodeIds(nodeId: string, indexes: GraphIndexes): Set<string> {
  const ids = new Set<string>();
  [...(indexes.incomingByNode.get(nodeId) || []), ...(indexes.outgoingByNode.get(nodeId) || [])].forEach((edge) => {
    ids.add(edge.dependent);
    ids.add(edge.prerequisite);
  });
  ids.delete(nodeId);
  return ids;
}

export function paperTitle(indexes: GraphIndexes, paperId: string): string {
  return indexes.papersById.get(paperId) || paperId;
}

export function highWarningPapers(analysis: SiteAnalysis) {
  return [...analysis.paper_summaries].sort((a, b) => b.evidence_warnings - a.evidence_warnings).filter((paper) => paper.evidence_warnings > 0);
}
