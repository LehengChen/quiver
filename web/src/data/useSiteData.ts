import { useEffect, useState } from "react";
import { loadSiteData, type SiteData } from "./loadSiteData";

type LoadState =
  | { status: "loading"; data: null; error: null }
  | { status: "ready"; data: SiteData; error: null }
  | { status: "error"; data: null; error: Error };

export function useSiteData(): LoadState {
  const [state, setState] = useState<LoadState>({ status: "loading", data: null, error: null });

  useEffect(() => {
    let cancelled = false;
    loadSiteData()
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data, error: null });
      })
      .catch((error: Error) => {
        if (!cancelled) setState({ status: "error", data: null, error });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}
