# Visualization

The Quiver visualization is a static React app for presenting concept dependency maps extracted from a paper collection.

Primary goals:

- Show the full concept map with search, filtering, node selection, and dependency direction.
- Help readers understand which concepts are central, reused across papers, or still need background.
- Provide paper-level and evidence-level drilldowns without exposing pipeline details as the main story.
- Build to static files that can be hosted by GitHub Pages.
- Keep the graph drawing layer custom, so layout, hub emphasis, edge curves, and selection behavior can be tuned for concept dependencies rather than inherited from a generic chart.

First supported routes:

- `#/` collection overview
- `#/graph` concept map explorer
- `#/review` review-oriented views for evidence coverage, concepts needing background, overlaps, and reused concepts
- `#/papers` paper browser

Design constraints:

- White background, restrained borders, compact typography, and minimal decoration.
- Graph color is restrained by default; node size carries collection-level connectivity, dependency direction reads left to right, node centers align to a fixed grid sorted by weight within each column, curved edges reduce full-map clutter, and an overview inset shows the current viewport inside the wider map.
- The graph renderer avoids hover-driven redraws, draws dense links on canvas, keeps nodes/labels in SVG, and provides full-screen mode plus an all-names toggle for close reading.
- Global CSS defines tokens and layout primitives; component styles use CSS modules.
- State starts with URL/search params plus page-local React state. Zustand is intentionally deferred until shared interaction state becomes complex.
