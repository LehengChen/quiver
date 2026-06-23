import { RichText } from "../RichText/RichText";
import styles from "./ReviewTable.module.css";

export interface ReviewTableRow {
  id: string;
  title: string;
  subtitle?: string;
  metric?: string | number;
  tags?: string[];
}

interface ReviewTableProps {
  rows: ReviewTableRow[];
  onSelect?: (id: string) => void;
}

export function ReviewTable({ rows, onSelect }: ReviewTableProps) {
  if (!rows.length) {
    return <p className={styles.empty}>No items in this view.</p>;
  }
  return (
    <div className={styles.table}>
      {rows.map((row) =>
        onSelect ? (
          <button key={row.id} className={`${styles.row} ${styles.interactive}`} type="button" onClick={() => onSelect(row.id)}>
            <RowContent row={row} />
          </button>
        ) : (
          <div key={row.id} className={styles.row}>
            <RowContent row={row} />
          </div>
        )
      )}
    </div>
  );
}

function RowContent({ row }: { row: ReviewTableRow }) {
  return (
    <>
      <span className={styles.main}>
        <strong className={styles.title}>
          <RichText text={row.title} inline />
        </strong>
        {row.subtitle ? (
          <span className={styles.subtitle}>
            <RichText text={row.subtitle} inline />
          </span>
        ) : null}
      </span>
      {row.tags?.length ? (
        <span className={styles.tags}>
          {row.tags.slice(0, 3).map((tag) => (
            <em key={tag}>{tag}</em>
          ))}
        </span>
      ) : null}
      {row.metric !== undefined ? <span className={styles.metric}>{row.metric}</span> : null}
    </>
  );
}
