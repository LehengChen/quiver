import type { SiteAnalysis } from "../../types/analysis";
import styles from "./StatsBar.module.css";

interface StatsBarProps {
  analysis: SiteAnalysis;
}

export function StatsBar({ analysis }: StatsBarProps) {
  const stats = [
    ["Papers", analysis.summary.papers],
    ["Concepts", analysis.summary.concepts],
    ["Dependency links", analysis.summary.dependencies],
    ["Need background", analysis.summary.concepts_needing_context],
    ["Reused concepts", analysis.summary.reused_concepts],
    ["Evidence gaps", analysis.summary.evidence_warnings]
  ];

  return (
    <dl className={styles.stats}>
      {stats.map(([label, value]) => (
        <div key={label} className={styles.item}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
