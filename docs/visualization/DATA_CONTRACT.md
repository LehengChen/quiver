# Visualization Data Contract

`quiver build-site` writes three JSON files into `results/site/`.

## graph.json

The normalized graph, currently `quiver.graph.v1`.

Important fields:

- `dataset`: collection metadata.
- `papers`: paper ids and titles.
- `nodes`: concept nodes.
- `edges`: dependency links where `prerequisite -> dependent`.
- `validation`: per-paper evidence coverage rows when available. New rows include `paper_id`.

## analysis.json

Presentation-oriented derived data, currently `quiver.site_analysis.v1`.

Important fields:

- `summary`: concept, dependency, paper, and review counts.
- `counts`: relation/entity/role/adequacy/confidence counts.
- `paper_summaries`: per-paper concept counts, concepts unique to that paper, reused concept counts, dependency counts, and evidence coverage counts.
- `frontier_nodes`: concepts needing more background.
- `reused_nodes`: concepts appearing in more than one paper.
- `overlap_warnings`: concepts with conflicting ontology statuses.
- `relation_groups`: strict dependency relations versus topical relations.

The UI should prefer `analysis.json` for overview/review pages instead of recomputing expensive summaries in React.

## manifest.json

Build and collection metadata, currently `quiver.site_manifest.v1`.

Important fields:

- `project_id`
- `title`
- `generated_at`
- `source_graph`
- `frontend`: `react` or `fallback`
- `build_source`: existing frontend bundle, npm build, or fallback HTML
- `files`: recursive file list for the generated site, including React assets
