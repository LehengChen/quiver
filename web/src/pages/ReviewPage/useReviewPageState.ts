import { useSearchParams } from "react-router-dom";
import type { ReviewTab } from "../../types/display";

const TABS: ReviewTab[] = ["context", "evidence", "overlap", "reuse", "relations"];

export function useReviewPageState() {
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab") as ReviewTab | null;
  const tab = raw && TABS.includes(raw) ? raw : "context";

  function setTab(next: ReviewTab) {
    const updated = new URLSearchParams(params);
    updated.set("tab", next);
    setParams(updated);
  }

  return { tab, setTab };
}
