import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { defaultGraphFilters, type GraphFilters } from "../../types/filters";

export function useGraphPageState() {
  const [params, setParams] = useSearchParams();
  const selectedNodeId = params.get("node") || "";

  const filters = useMemo<GraphFilters>(
    () => ({
      query: params.get("q") || defaultGraphFilters.query,
      paperId: params.get("paper") || defaultGraphFilters.paperId,
      minReferences: parseMinReferences(params.get("minRefs")),
      relation: params.get("relation") || defaultGraphFilters.relation,
      role: params.get("role") || defaultGraphFilters.role,
      adequacy: params.get("adequacy") || defaultGraphFilters.adequacy,
      confidence: params.get("confidence") || defaultGraphFilters.confidence,
      showTopical: parseTopical(params.get("topical"))
    }),
    [params]
  );

  function writeFilters(next: GraphFilters, updated: URLSearchParams) {
    setOrDelete(updated, "q", next.query);
    setOrDelete(updated, "paper", next.paperId);
    setOrDelete(updated, "minRefs", next.minReferences === defaultGraphFilters.minReferences ? "" : String(next.minReferences));
    setOrDelete(updated, "relation", next.relation);
    setOrDelete(updated, "role", next.role);
    setOrDelete(updated, "adequacy", next.adequacy);
    setOrDelete(updated, "confidence", next.confidence);
    setOrDelete(updated, "topical", next.showTopical === defaultGraphFilters.showTopical ? "" : next.showTopical ? "1" : "0");
    return updated;
  }

  function updateFilters(next: GraphFilters) {
    const updated = writeFilters(next, new URLSearchParams(params));
    setParams(updated);
  }

  function selectNode(nodeId: string) {
    const updated = new URLSearchParams(params);
    setOrDelete(updated, "node", nodeId);
    updated.delete("edge");
    setParams(updated);
  }

  function clearSelection() {
    const updated = new URLSearchParams(params);
    updated.delete("node");
    updated.delete("edge");
    setParams(updated);
  }

  function resetGraph() {
    setParams(new URLSearchParams());
  }

  return { filters, selectedNodeId, updateFilters, selectNode, clearSelection, resetGraph };
}

function setOrDelete(params: URLSearchParams, key: string, value: string) {
  if (value) params.set(key, value);
  else params.delete(key);
}

function parseTopical(value: string | null): boolean {
  if (value === "0") return false;
  if (value === "1") return true;
  return defaultGraphFilters.showTopical;
}

function parseMinReferences(value: string | null): number {
  if (!value) return defaultGraphFilters.minReferences;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return defaultGraphFilters.minReferences;
  return Math.max(0, Math.round(parsed));
}
