# Build And Deploy

Build the frontend assets:

```bash
cd web
npm install
npm run build
```

Build a project site:

```bash
PYTHONPATH=src python -m quiver.cli build-site path/to/quiver-project
```

The output directory is:

```text
path/to/quiver-project/results/site/
```

It contains a GitHub Pages-ready static app:

```text
index.html
assets/
graph.json
analysis.json
manifest.json
```

For local review:

```bash
python -m http.server 4173 -d examples/pages
```

Then open:

```text
http://localhost:4173/
```

Example sites are stored as standalone subdirectories under:

```text
examples/pages/
  index.html
  geometric-analysis-narrow-v1/
```

GitHub Pages publishes `examples/pages`, so individual examples are available
under paths such as `/quiver/geometric-analysis-narrow-v1/`.

The app uses hash routes, so GitHub Pages does not need a server-side fallback.

Run the visual smoke checks against the checked-in example site:

```bash
cd web
npx playwright install --with-deps chromium
npm run visual:check
```

The checks open the checked-in geometric analysis example with Playwright on desktop and mobile viewports, verify graph counts against `graph.json`, confirm hub nodes have visible size variation, save screenshots as test artifacts, and exercise node selection rollback.
