export interface ScenePoint {
  x: number;
  y: number;
}

export interface SceneNode extends ScenePoint {
  id: string;
  label: string;
  degree: number;
  layer: number;
  radius: number;
  showLabel: boolean;
  isHub: boolean;
}

export interface SceneEdge {
  id: string;
  prerequisite: string;
  dependent: string;
  relation: string;
  path: string;
  labelX: number;
  labelY: number;
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  isLong: boolean;
  strength: number;
}

export interface GraphScene {
  nodes: SceneNode[];
  edges: SceneEdge[];
  nodeById: Map<string, SceneNode>;
  bounds: {
    width: number;
    height: number;
  };
}
