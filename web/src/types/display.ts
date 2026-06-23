export type ReviewTab = "context" | "evidence" | "overlap" | "reuse" | "relations";

export interface SelectionState {
  nodeId: string;
  edgeId: string;
}
