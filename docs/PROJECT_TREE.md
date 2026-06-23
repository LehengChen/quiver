# Quiver Project Tree

Quiver is split into a Python extraction harness, a static React presentation app, durable improvement notes, and a public example site for GitHub Pages.

```text
quiver/
  src/quiver/
    ingest.py          # markdown paper indexing
    packages.py        # Codex-ready package construction
    prompts.py         # graph-delta extraction prompt
    codex.py           # Codex request preparation/execution
    serial.py          # serial accumulated extraction runner
    merge.py           # deterministic graph replay
    validate.py        # delta validation and evidence checks
    audit.py           # run-level audit reports
    monitor.py         # lightweight run heartbeat
    site_data.py       # site graph/analysis/manifest data export
    site.py            # static site build entrypoint

  web/
    src/
      pages/           # route-level presentation views
      components/      # reusable visual components
      data/            # data loading, display labels, indexing, selectors
      graphRenderer/   # custom graph scene layout and drawing model
      hooks/           # reusable UI hooks
      types/           # typed JSON contracts
      styles/          # global tokens/reset/layout CSS

  docs/
    visualization/     # presentation app design and data contract

  improvements/
    items/             # durable improvement records

  examples/
    site/              # checked-in GitHub Pages static output
```

The visualization is intended for readers exploring a concept collection, not for exposing implementation internals. Pipeline/run metadata is kept as supporting data, while the main UI emphasizes concepts, dependency links, evidence, and paper-level context.
