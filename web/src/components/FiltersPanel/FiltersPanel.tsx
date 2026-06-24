import { RotateCcw } from "lucide-react";
import type { SiteAnalysis } from "../../types/analysis";
import type { GraphFilters } from "../../types/filters";
import type { ConceptGraph } from "../../types/graph";
import { adequacyLabel, confidenceLabel, relationLabel, roleLabel } from "../../data/displayLabels";
import { nodeReferenceCounts } from "../../data/selectors";
import styles from "./FiltersPanel.module.css";

interface FiltersPanelProps {
  graph: ConceptGraph;
  analysis: SiteAnalysis;
  filters: GraphFilters;
  onChange: (filters: GraphFilters) => void;
  onReset: () => void;
}

function unique(values: Array<string | undefined>): string[] {
  return [...new Set(values.filter(Boolean) as string[])].sort((left, right) => left.localeCompare(right));
}

export function FiltersPanel({ graph, analysis, filters, onChange, onReset }: FiltersPanelProps) {
  const roles = unique(graph.nodes.map((node) => node.local_role));
  const adequacy = unique(graph.nodes.map((node) => node.adequacy));
  const confidence = unique(graph.nodes.map((node) => node.confidence));
  const relations = analysis.counts.relations.map((item) => item.key);
  const referenceCounts = nodeReferenceCounts(graph);
  const maxReferences = Math.max(2, ...referenceCounts.values());

  function update<K extends keyof GraphFilters>(key: K, value: GraphFilters[K]) {
    onChange({ ...filters, [key]: value });
  }

  function updateMinReferences(value: string) {
    const parsed = Number(value);
    const next = Number.isFinite(parsed) ? Math.max(0, Math.min(maxReferences, Math.round(parsed))) : 0;
    update("minReferences", next);
  }

  return (
    <section className={styles.panel} aria-label="Concept map filters">
      <details className={styles.filterShell} open>
        <summary className={styles.summary}>
          <span>
            <strong>Concept Map</strong>
            <span>Read dependencies from left to right.</span>
          </span>
        </summary>
        <div className={styles.controls}>
          <label className={styles.field}>
            <span>Search concepts</span>
            <input value={filters.query} onChange={(event) => update("query", event.target.value)} placeholder="Name, alias, summary" />
          </label>
          <label className={styles.field}>
            <span>Scope</span>
            <select value={filters.paperId} onChange={(event) => update("paperId", event.target.value)}>
              <option value="">All papers</option>
              {graph.papers.map((paper) => (
                <option key={paper.id} value={paper.id}>
                  {paper.title || paper.id}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.field}>
            <span>Minimum references</span>
            <input
              type="number"
              min="0"
              max={maxReferences}
              step="1"
              value={filters.minReferences}
              onChange={(event) => updateMinReferences(event.target.value)}
            />
          </label>
          <div className={styles.actions}>
            <button type="button" onClick={onReset}>
              <RotateCcw size={15} />
              <span>Reset filters</span>
            </button>
          </div>
        </div>
        <details className={styles.advanced}>
          <summary>More filters</summary>
          <div className={styles.advancedGrid}>
            <label className={styles.field}>
              <span>Relation type</span>
              <select value={filters.relation} onChange={(event) => update("relation", event.target.value)}>
                <option value="">All dependency links</option>
                {relations.map((relation) => (
                  <option key={relation} value={relation}>
                    {relationLabel(relation)}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.field}>
              <span>Concept role</span>
              <select value={filters.role} onChange={(event) => update("role", event.target.value)}>
                <option value="">All</option>
                {roles.map((role) => (
                  <option key={role} value={role}>
                    {roleLabel(role)}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.field}>
              <span>Background</span>
              <select value={filters.adequacy} onChange={(event) => update("adequacy", event.target.value)}>
                <option value="">All</option>
                {adequacy.map((item) => (
                  <option key={item} value={item}>
                    {adequacyLabel(item)}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.field}>
              <span>Confidence</span>
              <select value={filters.confidence} onChange={(event) => update("confidence", event.target.value)}>
                <option value="">All</option>
                {confidence.map((item) => (
                  <option key={item} value={item}>
                    {confidenceLabel(item)}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.toggle}>
              <input type="checkbox" checked={filters.showTopical} onChange={(event) => update("showTopical", event.target.checked)} />
              <span>Show topic grouping links</span>
            </label>
          </div>
        </details>
      </details>
    </section>
  );
}
