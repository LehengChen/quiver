# Interaction Model

The React app keeps the original static HTML viewer's core behavior:

- The graph view can show the full concept map.
- Search filters concepts by id, label, aliases, and summary.
- Dependency direction is `prerequisite -> dependent`.
- The default graph layout uses the custom graph renderer: dependency depth reads left to right, higher-weight concepts sort toward the top of each column, node size encodes collection-level connectivity, edge curves keep dense full-map views legible, and the overview inset preserves global context while reading a focused viewport.
- Clicking a node opens a floating detail drawer with summary, evidence, papers, dependencies, and dependents.
- Dependency links are visual context only; they are not hover or click targets.
- Full-screen graph mode hides the surrounding page chrome from the reading surface.
- Node labels are stable by default and reserved for hub concepts; the Names control can show all concept names when close reading requires it.
- Dense dependency links render on canvas for interaction performance while concept nodes and labels remain SVG.
- Relation and quality filters are secondary controls under "More filters" to keep the first view readable.
- Selecting a concept highlights its immediate dependency neighborhood without changing which concepts are visible.
- Relation filters show concepts attached to matching links rather than leaving unrelated isolates in view.

New behavior:

- Page routes separate overview, graph exploration, review, and paper browsing.
- Top filters can narrow by paper, relation, role, background, and confidence.
- The top filter bar can collapse so the graph remains the primary reading surface.
- Review pages surface concepts needing background, evidence coverage, overlapping definitions, reused concepts, and relation distribution.
- URL search params preserve selected node, selected paper, active review tab, and graph filters where practical.

Reader-facing language should avoid pipeline-first terminology. Prefer:

- collection instead of run
- evidence coverage instead of validation warnings
- concepts needing background instead of frontier
- overlapping concepts instead of ontology conflicts
- reused concepts instead of merge reuse
