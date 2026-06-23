import type { ConceptGraph } from "../types/graph";
import type { SiteAnalysis } from "../types/analysis";
import type { SiteManifest } from "../types/manifest";

export interface SiteCollection {
  id: string;
  projectId: string;
  title: string;
  graph: ConceptGraph;
  analysis: SiteAnalysis;
  manifest: SiteManifest;
}

export interface SiteData {
  graph: ConceptGraph;
  analysis: SiteAnalysis;
  manifest: SiteManifest;
  collections: SiteCollection[];
  title: string;
}

interface SiteCollectionsIndex {
  schema_version: string;
  title?: string;
  collections?: SiteCollectionIndexEntry[];
}

interface SiteCollectionIndexEntry {
  id: string;
  project_id?: string;
  title?: string;
  graph: string;
  analysis: string;
  manifest?: string;
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Unable to load ${path}: ${response.status}`);
  }
  return (await response.json()) as T;
}

async function fetchOptionalJson<T>(path: string): Promise<T | null> {
  const response = await fetch(path, { cache: "no-store" });
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Unable to load ${path}: ${response.status}`);
  }
  return (await response.json()) as T;
}

function sitePath(path: string): string {
  return path.startsWith("./") || path.startsWith("/") ? path : `./${path}`;
}

export async function loadSiteData(): Promise<SiteData> {
  const collectionIndex = await fetchOptionalJson<SiteCollectionsIndex>("./collections.json");
  if (collectionIndex?.collections?.length) {
    const collections = await Promise.all(
      collectionIndex.collections.map(async (entry) => {
        const [graph, analysis, manifest] = await Promise.all([
          fetchJson<ConceptGraph>(sitePath(entry.graph)),
          fetchJson<SiteAnalysis>(sitePath(entry.analysis)),
          entry.manifest ? fetchJson<SiteManifest>(sitePath(entry.manifest)) : fetchJson<SiteManifest>("./manifest.json")
        ]);
        return {
          id: entry.id,
          projectId: entry.project_id || manifest.project_id || entry.id,
          title: entry.title || manifest.title || entry.id,
          graph,
          analysis,
          manifest
        };
      })
    );
    const active = collections[0];
    return {
      graph: active.graph,
      analysis: active.analysis,
      manifest: active.manifest,
      collections,
      title: collectionIndex.title || active.title
    };
  }

  const [graph, analysis, manifest] = await Promise.all([
    fetchJson<ConceptGraph>("./graph.json"),
    fetchJson<SiteAnalysis>("./analysis.json"),
    fetchJson<SiteManifest>("./manifest.json")
  ]);
  const collection = {
    id: manifest.project_id,
    projectId: manifest.project_id,
    title: manifest.title || manifest.project_id,
    graph,
    analysis,
    manifest
  };
  return { graph, analysis, manifest, collections: [collection], title: collection.title };
}
