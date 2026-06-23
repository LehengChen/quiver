import type { ConceptEdge, ConceptNode } from "../types/graph";
import type { GraphScene, SceneEdge, SceneNode, ScenePoint } from "./sceneTypes";

const TOP_MARGIN = 118;
const LEFT_MARGIN = 92;
const ROW_GAP = 58;
const COLUMN_GAP = 248;
const HUB_LABEL_LIMIT = 28;

export function buildGraphScene(nodes: ConceptNode[], edges: ConceptEdge[], degreeByNode: Map<string, number>): GraphScene {
  const nodeIds = new Set(nodes.map((node) => node.id));
  const dependencyEdges = edges.filter((edge) => edge.relation !== "belongs_to_topic" && nodeIds.has(edge.prerequisite) && nodeIds.has(edge.dependent));
  const layers = dependencyLayers(nodes, dependencyEdges);
  const orderedLayers = orderLayers(nodes, layers, degreeByNode);
  const sceneNodes = placeNodes(orderedLayers, degreeByNode);
  const nodeById = new Map(sceneNodes.map((node) => [node.id, node]));
  const sceneEdges = edges.flatMap((edge) => {
    const source = nodeById.get(edge.prerequisite);
    const target = nodeById.get(edge.dependent);
    return source && target ? [buildSceneEdge(edge, source, target)] : [];
  });
  const maxX = Math.max(900, ...sceneNodes.map((node) => node.x + node.radius + 260), ...sceneEdges.map((edge) => edge.labelX + 180));
  const maxY = Math.max(640, ...sceneNodes.map((node) => node.y + node.radius + 76), ...sceneEdges.map((edge) => edge.labelY + 48));
  return {
    nodes: sceneNodes,
    edges: sceneEdges,
    nodeById,
    bounds: {
      width: maxX,
      height: maxY
    }
  };
}

export function sceneNodeRadius(degree = 0): number {
  return Math.min(18, 5.5 + Math.sqrt(Math.max(0, degree)) * 3.45);
}

function stableHash(text: string): number {
  let hash = 0;
  for (let index = 0; index < text.length; index += 1) {
    hash = (hash * 33 + text.charCodeAt(index)) >>> 0;
  }
  return hash;
}

function dependencyLayers(nodes: ConceptNode[], edges: ConceptEdge[]): Map<string, number> {
  const incoming = new Map(nodes.map((node) => [node.id, 0]));
  const outgoing = new Map(nodes.map((node) => [node.id, [] as string[]]));
  edges.forEach((edge) => {
    outgoing.get(edge.prerequisite)?.push(edge.dependent);
    incoming.set(edge.dependent, (incoming.get(edge.dependent) || 0) + 1);
  });

  const layers = new Map(nodes.map((node) => [node.id, 0]));
  const queue = [...nodes.filter((node) => (incoming.get(node.id) || 0) === 0).map((node) => node.id)].sort();
  let cursor = 0;
  while (cursor < queue.length) {
    const current = queue[cursor];
    cursor += 1;
    for (const dependent of outgoing.get(current) || []) {
      layers.set(dependent, Math.max(layers.get(dependent) || 0, (layers.get(current) || 0) + 1));
      incoming.set(dependent, (incoming.get(dependent) || 0) - 1);
      if ((incoming.get(dependent) || 0) === 0) queue.push(dependent);
    }
  }

  if (cursor < nodes.length) {
    nodes.forEach((node) => {
      if ((incoming.get(node.id) || 0) > 0) {
        const prerequisites = edges.filter((edge) => edge.dependent === node.id).map((edge) => layers.get(edge.prerequisite) || 0);
        layers.set(node.id, prerequisites.length ? Math.max(...prerequisites) + 1 : layers.get(node.id) || 0);
      }
    });
  }
  return layers;
}

function orderLayers(nodes: ConceptNode[], layers: Map<string, number>, degreeByNode: Map<string, number>): Map<number, ConceptNode[]> {
  const grouped = new Map<number, ConceptNode[]>();
  nodes.forEach((node) => {
    const layer = layers.get(node.id) || 0;
    grouped.set(layer, [...(grouped.get(layer) || []), node]);
  });

  const layerIds = [...grouped.keys()].sort((left, right) => left - right);
  layerIds.forEach((layer) => {
    grouped.set(
      layer,
      [...(grouped.get(layer) || [])].sort((left, right) => {
        const score = (degreeByNode.get(right.id) || 0) - (degreeByNode.get(left.id) || 0);
        return score || left.id.localeCompare(right.id);
      })
    );
  });

  return grouped;
}

function placeNodes(orderedLayers: Map<number, ConceptNode[]>, degreeByNode: Map<string, number>): SceneNode[] {
  const layerIds = [...orderedLayers.keys()].sort((left, right) => left - right);
  const hubCutoff = hubThreshold([...orderedLayers.values()].flat(), degreeByNode);
  const sceneNodes: SceneNode[] = [];

  layerIds.forEach((layer, column) => {
    const nodes = orderedLayers.get(layer) || [];
    nodes.forEach((node, nodeIndex) => {
      const degree = degreeByNode.get(node.id) || 0;
      sceneNodes.push({
        id: node.id,
        label: node.label || node.id,
        layer,
        degree,
        radius: sceneNodeRadius(degree),
        x: LEFT_MARGIN + column * COLUMN_GAP,
        y: TOP_MARGIN + nodeIndex * ROW_GAP,
        showLabel: degree >= hubCutoff,
        isHub: degree >= hubCutoff
      });
    });
  });
  return promoteHubLabels(sceneNodes);
}

function hubThreshold(nodes: ConceptNode[], degreeByNode: Map<string, number>): number {
  const degrees = nodes.map((node) => degreeByNode.get(node.id) || 0).sort((left, right) => right - left);
  return Math.max(6, degrees[Math.min(HUB_LABEL_LIMIT - 1, degrees.length - 1)] || 6);
}

function promoteHubLabels(nodes: SceneNode[]): SceneNode[] {
  const hubs = [...nodes].sort((left, right) => right.degree - left.degree).slice(0, HUB_LABEL_LIMIT);
  const hubIds = new Set(hubs.map((node) => node.id));
  return nodes.map((node) => ({ ...node, showLabel: node.showLabel || hubIds.has(node.id) }));
}

function buildSceneEdge(edge: ConceptEdge, source: SceneNode, target: SceneNode): SceneEdge {
  const clipped = clipEdge(source, target);
  const dx = Math.max(48, Math.abs(clipped.target.x - clipped.source.x));
  const direction = target.x >= source.x ? 1 : -1;
  const longness = Math.abs(target.layer - source.layer);
  const lift = ((stableHash(edge.id) % 19) - 9) * Math.min(2.6, Math.max(1, longness / 3));
  const c1: ScenePoint = { x: clipped.source.x + direction * Math.min(180, dx * 0.44), y: clipped.source.y + lift };
  const c2: ScenePoint = { x: clipped.target.x - direction * Math.min(180, dx * 0.44), y: clipped.target.y - lift };
  const labelX = (clipped.source.x + clipped.target.x) / 2;
  const labelY = (clipped.source.y + clipped.target.y) / 2 + lift * 0.35;
  return {
    id: edge.id,
    prerequisite: edge.prerequisite,
    dependent: edge.dependent,
    relation: edge.relation,
    path: `M ${round(clipped.source.x)} ${round(clipped.source.y)} C ${round(c1.x)} ${round(c1.y)}, ${round(c2.x)} ${round(c2.y)}, ${round(
      clipped.target.x
    )} ${round(clipped.target.y)}`,
    labelX,
    labelY,
    sourceX: clipped.source.x,
    sourceY: clipped.source.y,
    targetX: clipped.target.x,
    targetY: clipped.target.y,
    isLong: longness > 2,
    strength: Math.max(source.degree, target.degree)
  };
}

function clipEdge(source: SceneNode, target: SceneNode): { source: ScenePoint; target: ScenePoint } {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.hypot(dx, dy) || 1;
  const ux = dx / distance;
  const uy = dy / distance;
  return {
    source: {
      x: source.x + ux * (source.radius + 4),
      y: source.y + uy * (source.radius + 4)
    },
    target: {
      x: target.x - ux * (target.radius + 12),
      y: target.y - uy * (target.radius + 12)
    }
  };
}

function round(value: number): number {
  return Math.round(value * 10) / 10;
}
