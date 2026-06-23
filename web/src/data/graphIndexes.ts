import type { ConceptEdge, ConceptGraph, ConceptNode } from "../types/graph";

export interface GraphIndexes {
  nodesById: Map<string, ConceptNode>;
  edgesById: Map<string, ConceptEdge>;
  incomingByNode: Map<string, ConceptEdge[]>;
  outgoingByNode: Map<string, ConceptEdge[]>;
  papersById: Map<string, string>;
}

function pushEdge(map: Map<string, ConceptEdge[]>, key: string, edge: ConceptEdge): void {
  const current = map.get(key);
  if (current) current.push(edge);
  else map.set(key, [edge]);
}

export function buildGraphIndexes(graph: ConceptGraph): GraphIndexes {
  const nodesById = new Map(graph.nodes.map((node) => [node.id, node]));
  const edgesById = new Map(graph.edges.map((edge) => [edge.id, edge]));
  const incomingByNode = new Map<string, ConceptEdge[]>();
  const outgoingByNode = new Map<string, ConceptEdge[]>();
  const papersById = new Map(graph.papers.map((paper) => [paper.id, paper.title]));

  graph.edges.forEach((edge) => {
    pushEdge(incomingByNode, edge.dependent, edge);
    pushEdge(outgoingByNode, edge.prerequisite, edge);
  });

  return { nodesById, edgesById, incomingByNode, outgoingByNode, papersById };
}
