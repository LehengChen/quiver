import type { EvidenceSpan } from "../../types/graph";
import { RichText } from "../RichText/RichText";
import styles from "./EvidenceList.module.css";

interface EvidenceListProps {
  evidence?: EvidenceSpan[];
  limit?: number;
}

export function EvidenceList({ evidence = [], limit = 4 }: EvidenceListProps) {
  if (!evidence.length) {
    return <p className={styles.empty}>No evidence span is attached.</p>;
  }
  return (
    <ul className={styles.list}>
      {evidence.slice(0, limit).map((item, index) => (
        <li key={`${item.quote}-${index}`}>
          <q>
            <RichText text={item.quote} inline />
          </q>
          {item.section ? (
            <span className={styles.section}>
              <RichText text={item.section} inline />
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
