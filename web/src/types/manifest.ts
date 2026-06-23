export interface SiteManifest {
  schema_version: string;
  project_id: string;
  title: string;
  generated_at: string;
  source_graph: string;
  files: string[];
  frontend?: "react" | "fallback";
  build_source?: "existing_dist" | "npm_build" | "fallback_html";
}
