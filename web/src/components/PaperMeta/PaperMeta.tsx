import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";
import type { PaperSummary } from "../../types/analysis";
import type { Paper } from "../../types/graph";
import { RichText } from "../RichText/RichText";
import styles from "./PaperMeta.module.css";

interface PaperMetaProps {
  paper: Paper;
  summary?: PaperSummary;
  label?: string;
  compact?: boolean;
  action?: ReactNode;
  className?: string;
}

export function formatPaperByline(paper: Paper): string {
  const venue = [paper.journal, paper.year].filter(Boolean).join(", ");
  const msc = paper.primary_msc ? `MSC ${paper.primary_msc}` : "";
  return [venue, msc].filter(Boolean).join(" | ");
}

function volumeIssue(paper: Paper): string {
  if (paper.volume && paper.number) return `${paper.volume}(${paper.number})`;
  return paper.volume || paper.number || "";
}

function compactList(values: Array<string | number | undefined>): string[] {
  return values.filter((value): value is string | number => value !== undefined && value !== "").map(String);
}

function Metric({ label, value }: { label: string; value?: string | number }) {
  if (value === undefined || value === "") return null;
  return (
    <span className={styles.metric}>
      <span>{label}</span>
      <strong>{value}</strong>
    </span>
  );
}

export function PaperMeta({ paper, summary, label = "Selected paper", compact = false, action, className }: PaperMetaProps) {
  const authors = paper.authors?.join(", ");
  const venue = compactList([paper.journal, volumeIssue(paper), paper.pages, paper.year]).join(" | ");
  const msc = compactList([paper.primary_msc, paper.primary_msc_description]).join(" | ");
  const doiUrl = paper.doi_url || (paper.doi ? `https://doi.org/${paper.doi}` : "");
  const classes = [styles.paperMeta, compact ? styles.compact : "", className || ""].filter(Boolean).join(" ");

  return (
    <section className={classes} aria-label={label}>
      <div className={styles.header}>
        <div className={styles.titleBlock}>
          <span className={styles.eyebrow}>{label}</span>
          <h3>
            <RichText text={paper.title || paper.id} inline />
          </h3>
          {authors ? (
            <p className={styles.authors}>
              <RichText text={authors} inline />
            </p>
          ) : null}
        </div>
        {action ? <div className={styles.action}>{action}</div> : null}
      </div>
      <div className={styles.detailGrid}>
        {venue ? <MetaLine label="Published in" value={venue} /> : null}
        {msc ? <MetaLine label="Primary MSC" value={msc} /> : null}
        {paper.mrnumber ? <MetaLine label="MR" value={`MR${paper.mrnumber}`} /> : null}
        {paper.doi ? (
          <MetaLine
            label="DOI"
            value={
              doiUrl ? (
                <a href={doiUrl} target="_blank" rel="noreferrer">
                  {paper.doi}
                  <ExternalLink size={13} />
                </a>
              ) : (
                paper.doi
              )
            }
          />
        ) : null}
      </div>
      {summary || paper.citation_count !== undefined || paper.page_count_estimate !== undefined ? (
        <div className={styles.metrics}>
          {summary ? (
            <>
              <Metric label="Concepts" value={summary.concepts} />
              <Metric label="Unique" value={summary.unique_concepts} />
              <Metric label="Links" value={summary.dependency_links} />
            </>
          ) : null}
          <Metric label="Citations" value={paper.citation_count} />
          <Metric label="Pages" value={paper.page_count_estimate} />
        </div>
      ) : null}
    </section>
  );
}

function MetaLine({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className={styles.metaLine}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
