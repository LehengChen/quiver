import { memo, type PointerEvent, type RefObject, useEffect, useMemo, useRef, useState } from "react";
import { Maximize2, Minimize2, RotateCcw, XCircle } from "lucide-react";
import type { GraphIndexes } from "../../data/graphIndexes";
import { neighboringNodeIds } from "../../data/selectors";
import { buildGraphScene } from "../../graphRenderer/graphScene";
import type { GraphScene, SceneEdge, SceneNode } from "../../graphRenderer/sceneTypes";
import { useElementSize } from "../../hooks/useElementSize";
import type { ConceptEdge, ConceptNode } from "../../types/graph";
import styles from "./GraphCanvas.module.css";

interface GraphCanvasProps {
  nodes: ConceptNode[];
  edges: ConceptEdge[];
  indexes: GraphIndexes;
  degreeByNode: Map<string, number>;
  selectedNodeId: string;
  hasSelection: boolean;
  onClearSelection: () => void;
  onSelectNode: (nodeId: string) => void;
}

interface ViewState {
  x: number;
  y: number;
  scale: number;
}

interface ViewRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface CanvasEdge extends SceneEdge {
  path2d: Path2D;
}

export function GraphCanvas({
  nodes,
  edges,
  indexes,
  degreeByNode,
  selectedNodeId,
  hasSelection,
  onClearSelection,
  onSelectNode
}: GraphCanvasProps) {
  const scene = useMemo(() => buildGraphScene(nodes, edges, degreeByNode), [degreeByNode, edges, nodes]);
  const canvasEdges = useMemo<CanvasEdge[]>(() => scene.edges.map((edge) => ({ ...edge, path2d: new Path2D(edge.path) })), [scene.edges]);
  const [view, setView] = useState<ViewState>({ x: 0, y: 0, scale: 1 });
  const [dragStart, setDragStart] = useState<{ x: number; y: number; viewX: number; viewY: number } | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const { ref: viewportRef, size: viewportSize } = useElementSize<HTMLDivElement>();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frameRef = useRef<number | null>(null);
  const pendingViewRef = useRef<ViewState | null>(null);

  const neighborIds = useMemo(() => (selectedNodeId ? neighboringNodeIds(selectedNodeId, indexes) : new Set<string>()), [indexes, selectedNodeId]);
  const viewportWidth = Math.max(1, viewportSize.width || 1);
  const viewportHeight = Math.max(1, viewportSize.height || 1);

  const readableView = useMemo(() => {
    const aspect = viewportWidth / viewportHeight;
    const targetWidth = aspect > 1.45 ? Math.max(1500, aspect * 980) : 1150;
    const scale = scene.bounds.width > 2200 ? Math.min(4.2, Math.max(1, scene.bounds.width / targetWidth)) : 1;
    return { x: 0, y: 0, scale };
  }, [scene.bounds.width, viewportHeight, viewportWidth]);

  useEffect(() => {
    setView(readableView);
  }, [readableView]);

  useEffect(() => {
    if (!isFullscreen) return;
    const previousOverflow = document.body.style.overflow;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsFullscreen(false);
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [isFullscreen]);

  useEffect(() => {
    const target = viewportRef.current;
    if (!target) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = target.getBoundingClientRect();
      const localX = event.clientX - rect.left;
      const localY = event.clientY - rect.top;
      const direction = event.deltaY > 0 ? -0.08 : 0.08;
      setView((current) => {
        const currentScreenScale = Math.max(0.001, viewportWidth * current.scale / scene.bounds.width);
        const sceneX = current.x + localX / currentScreenScale;
        const sceneY = current.y + localY / currentScreenScale;
        const scale = Math.min(4, Math.max(0.45, current.scale + direction));
        const nextScreenScale = Math.max(0.001, viewportWidth * scale / scene.bounds.width);
        return constrainView({
          x: sceneX - localX / nextScreenScale,
          y: sceneY - localY / nextScreenScale,
          scale
        });
      });
    };
    target.addEventListener("wheel", onWheel, { passive: false });
    return () => target.removeEventListener("wheel", onWheel);
  }, [scene.bounds.width, viewportHeight, viewportRef, viewportWidth]);

  useEffect(() => {
    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    };
  }, []);

  const viewRect = useMemo<ViewRect>(() => {
    const width = scene.bounds.width / view.scale;
    const height = width / Math.max(0.2, viewportWidth / viewportHeight);
    return { x: view.x, y: view.y, width, height };
  }, [scene.bounds.width, view.scale, view.x, view.y, viewportHeight, viewportWidth]);
  const screenScale = viewportWidth / viewRect.width;
  const graphTransform = `translate(${-viewRect.x * screenScale}, ${-viewRect.y * screenScale}) scale(${screenScale})`;
  const overviewRect = clampRect(viewRect, scene.bounds.width, scene.bounds.height);
  const surfaceClassName = isFullscreen ? `${styles.surface} ${styles.fullscreen}` : styles.surface;

  useCanvasEdges(canvasRef, canvasEdges, selectedNodeId, viewRect, viewportWidth, viewportHeight);

  function scheduleView(next: ViewState) {
    pendingViewRef.current = constrainView(next);
    if (frameRef.current !== null) return;
    frameRef.current = requestAnimationFrame(() => {
      frameRef.current = null;
      const pending = pendingViewRef.current;
      if (pending) setView(pending);
      pendingViewRef.current = null;
    });
  }

  function onPointerDown(event: PointerEvent<SVGSVGElement>) {
    if ((event.target as Element).closest("[data-node]")) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragStart({ x: event.clientX, y: event.clientY, viewX: view.x, viewY: view.y });
  }

  function onPointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!dragStart) return;
    const currentScreenScale = Math.max(0.001, viewportWidth * view.scale / scene.bounds.width);
    scheduleView({
      ...view,
      x: dragStart.viewX - (event.clientX - dragStart.x) / currentScreenScale,
      y: dragStart.viewY - (event.clientY - dragStart.y) / currentScreenScale
    });
  }

  function onPointerUp(event: PointerEvent<SVGSVGElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    setDragStart(null);
  }

  function resetView() {
    setView(constrainView(readableView));
  }

  function fitAll() {
    setView(constrainView({ x: 0, y: 0, scale: 1 }));
  }

  function constrainView(next: ViewState): ViewState {
    const width = scene.bounds.width / next.scale;
    const height = width / Math.max(0.2, viewportWidth / viewportHeight);
    const horizontalPadding = Math.max(240, width * 0.48);
    const verticalPadding = Math.max(220, height * 0.48);
    const minX = -horizontalPadding;
    const minY = -verticalPadding;
    const maxX = Math.max(minX, scene.bounds.width - width + horizontalPadding);
    const maxY = Math.max(minY, scene.bounds.height - height + verticalPadding);
    return {
      ...next,
      x: Math.min(maxX, Math.max(minX, next.x)),
      y: Math.min(maxY, Math.max(minY, next.y))
    };
  }

  return (
    <section className={surfaceClassName} aria-label="Concept dependency graph">
      <div className={styles.toolbar}>
        <span>{nodes.length} concepts</span>
        <span>{edges.length} links</span>
        <span className={styles.direction}>{"prerequisite -> dependent"}</span>
        {hasSelection ? (
          <button type="button" onClick={onClearSelection} title="Clear selection" aria-label="Clear selection">
            <XCircle size={15} />
          </button>
        ) : null}
        <button type="button" onClick={resetView} title="Reset view" aria-label="Reset view">
          <RotateCcw size={15} />
        </button>
        <button
          type="button"
          onClick={() => setIsFullscreen((current) => !current)}
          title={isFullscreen ? "Exit full screen graph" : "Enter full screen graph"}
          aria-label={isFullscreen ? "Exit full screen graph" : "Enter full screen graph"}
        >
          {isFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
        </button>
        <button type="button" onClick={fitAll} title="Fit all" aria-label="Fit all">
          <span aria-hidden="true">1:1</span>
        </button>
      </div>
      <div ref={viewportRef} className={styles.viewport}>
        <canvas ref={canvasRef} className={styles.edgeCanvas} data-edge-count={scene.edges.length} aria-hidden="true" />
        <svg
          className={styles.svg}
          viewBox={`0 0 ${viewportWidth} ${viewportHeight}`}
          preserveAspectRatio="none"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onPointerLeave={() => setDragStart(null)}
        >
          <g data-graph-content="true" transform={graphTransform}>
            <NodeLayer
              nodes={scene.nodes}
              selectedNodeId={selectedNodeId}
              neighborIds={neighborIds}
              onSelectNode={onSelectNode}
            />
          </g>
        </svg>
        <Overview scene={scene} overviewRect={overviewRect} />
      </div>
    </section>
  );
}

function useCanvasEdges(
  canvasRef: RefObject<HTMLCanvasElement | null>,
  edges: CanvasEdge[],
  focusNodeId: string,
  viewRect: ViewRect,
  viewportWidth: number,
  viewportHeight: number
) {
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || viewportWidth <= 1 || viewportHeight <= 1) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.round(viewportWidth * dpr));
    canvas.height = Math.max(1, Math.round(viewportHeight * dpr));
    canvas.style.width = `${viewportWidth}px`;
    canvas.style.height = `${viewportHeight}px`;

    const context = canvas.getContext("2d");
    if (!context) return;
    context.setTransform(1, 0, 0, 1, 0, 0);
    context.clearRect(0, 0, canvas.width, canvas.height);

    const screenScale = viewportWidth / viewRect.width;
    context.setTransform(screenScale * dpr, 0, 0, screenScale * dpr, -viewRect.x * screenScale * dpr, -viewRect.y * screenScale * dpr);
    context.lineCap = "round";
    context.lineJoin = "round";

    edges.forEach((edge) => {
      context.globalAlpha = edgeOpacity(edge, focusNodeId);
      context.strokeStyle = edgeStroke(edge, focusNodeId);
      context.fillStyle = edgeStroke(edge, focusNodeId);
      context.lineWidth = edgeWidth(edge);
      context.setLineDash([]);
      context.stroke(edge.path2d);
      drawArrow(context, edge);
    });
    context.setLineDash([]);
    context.globalAlpha = 1;
  }, [canvasRef, edges, focusNodeId, viewRect.height, viewRect.width, viewRect.x, viewRect.y, viewportHeight, viewportWidth]);
}

const NodeLayer = memo(function NodeLayer({
  nodes,
  selectedNodeId,
  neighborIds,
  onSelectNode
}: {
  nodes: SceneNode[];
  selectedNodeId: string;
  neighborIds: Set<string>;
  onSelectNode: (nodeId: string) => void;
}) {
  return (
    <g className={styles.nodeLayer}>
      {nodes.map((node) => {
        const isSelected = node.id === selectedNodeId;
        return (
          <g
            key={node.id}
            data-node={node.id}
            data-degree={node.degree}
            className={styles.nodeGroup}
            transform={`translate(${node.x}, ${node.y})`}
            opacity={nodeOpacity(node, selectedNodeId, neighborIds)}
            onClick={() => onSelectNode(node.id)}
          >
            {node.isHub ? <circle className={styles.hubHalo} r={node.radius + 7} /> : null}
            <circle className={styles.nodeHit} r={node.radius + 8} />
            <circle
              data-node-circle="true"
              r={node.radius + (isSelected ? 3 : 0)}
              fill={node.isHub ? "#f7fbff" : "#ffffff"}
              stroke={isSelected ? "#175cd3" : nodeStroke(node)}
              strokeWidth={isSelected ? 3 : 1.8}
            />
            <title>{node.label || node.id}</title>
            <text x={node.radius + 8} y={4} className={node.isHub ? styles.hubLabel : styles.nodeLabel}>
              {node.label}
            </text>
          </g>
        );
      })}
    </g>
  );
});

function Overview({ scene, overviewRect }: { scene: GraphScene; overviewRect: { x: number; y: number; width: number; height: number } }) {
  return (
    <svg
      className={styles.overview}
      viewBox={`0 0 ${scene.bounds.width} ${scene.bounds.height}`}
      preserveAspectRatio="none"
      aria-hidden="true"
      focusable="false"
    >
      <rect className={styles.overviewBackground} x="0" y="0" width={scene.bounds.width} height={scene.bounds.height} />
      <OverviewMap scene={scene} />
      <rect
        className={styles.overviewWindow}
        x={overviewRect.x}
        y={overviewRect.y}
        width={overviewRect.width}
        height={overviewRect.height}
      />
    </svg>
  );
}

const OverviewMap = memo(function OverviewMap({ scene }: { scene: GraphScene }) {
  return (
    <g>
      {scene.nodes.map((node) => (
        <circle key={node.id} className={node.isHub ? styles.overviewHub : styles.overviewNode} cx={node.x} cy={node.y} r={node.isHub ? 15 : 9} />
      ))}
    </g>
  );
});

function edgeOpacity(edge: SceneEdge, focusNodeId: string): number {
  if (!focusNodeId) {
    if (edge.relation === "belongs_to_topic") return 0.1;
    if (edge.strength >= 9) return 0.38;
    if (edge.strength >= 6) return 0.24;
    return 0.13;
  }
  return edge.dependent === focusNodeId || edge.prerequisite === focusNodeId ? 0.95 : 0.045;
}

function nodeOpacity(node: SceneNode, selectedNodeId: string, neighborIds: Set<string>): number {
  if (!selectedNodeId) return 0.92;
  if (node.id === selectedNodeId || neighborIds.has(node.id)) return 1;
  return 0.26;
}

function edgeStroke(edge: SceneEdge, focusNodeId: string): string {
  if (focusNodeId && edge.dependent === focusNodeId) return "#b54708";
  if (focusNodeId && edge.prerequisite === focusNodeId) return "#175cd3";
  if (edge.relation === "belongs_to_topic") return "#c6ced6";
  return "#64798a";
}

function edgeWidth(edge: SceneEdge): number {
  if (edge.relation === "belongs_to_topic") return 0.9;
  if (edge.strength >= 9) return 1.45;
  if (edge.strength >= 6) return 1.15;
  return 0.85;
}

function drawArrow(context: CanvasRenderingContext2D, edge: SceneEdge) {
  const dx = edge.targetX - edge.sourceX;
  const dy = edge.targetY - edge.sourceY;
  const angle = Math.atan2(dy, dx);
  const size = edge.strength >= 9 ? 9 : 7;
  context.save();
  context.translate(edge.targetX, edge.targetY);
  context.rotate(angle);
  context.beginPath();
  context.moveTo(0, 0);
  context.lineTo(-size, -size * 0.45);
  context.lineTo(-size, size * 0.45);
  context.closePath();
  context.fill();
  context.restore();
}

function nodeStroke(node: SceneNode): string {
  if (node.degree >= 10) return "#1d3b53";
  if (node.degree >= 6) return "#31536a";
  return "#68798a";
}

function clampRect(rect: { x: number; y: number; width: number; height: number }, maxWidth: number, maxHeight: number) {
  const x = Math.max(0, Math.min(rect.x, maxWidth));
  const y = Math.max(0, Math.min(rect.y, maxHeight));
  return {
    x,
    y,
    width: Math.max(0, Math.min(rect.width, maxWidth - x)),
    height: Math.max(0, Math.min(rect.height, maxHeight - y))
  };
}
