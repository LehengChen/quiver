export interface GraphFilters {
  query: string;
  paperId: string;
  minReferences: number;
  relation: string;
  role: string;
  adequacy: string;
  confidence: string;
  showTopical: boolean;
}

export const defaultGraphFilters: GraphFilters = {
  query: "",
  paperId: "",
  minReferences: 2,
  relation: "",
  role: "",
  adequacy: "",
  confidence: "",
  showTopical: false
};
