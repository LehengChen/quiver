import { useParams } from "react-router-dom";

type QueryValue = string | number | boolean | undefined | null;

export function collectionPath(collectionId: string, page = "", query?: Record<string, QueryValue> | URLSearchParams | string): string {
  const base = `/${encodeURIComponent(collectionId)}`;
  const pagePath = page ? `/${page.replace(/^\/+/, "")}` : "";
  const queryString = formatQuery(query);
  return `${base}${pagePath}${queryString}`;
}

export function useCollectionPath() {
  const { collectionId = "" } = useParams();
  return (page = "", query?: Record<string, QueryValue> | URLSearchParams | string) => collectionPath(collectionId, page, query);
}

function formatQuery(query?: Record<string, QueryValue> | URLSearchParams | string): string {
  if (!query) return "";
  if (typeof query === "string") {
    const trimmed = query.replace(/^\?/, "");
    return trimmed ? `?${trimmed}` : "";
  }
  const params = query instanceof URLSearchParams ? new URLSearchParams(query) : new URLSearchParams();
  if (!(query instanceof URLSearchParams)) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
    });
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}
