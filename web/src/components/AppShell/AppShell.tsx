import { NavLink, useLocation, useNavigate } from "react-router-dom";
import type { SiteCollection } from "../../data/loadSiteData";
import { collectionPath } from "../../hooks/useCollectionPath";
import type { ReactNode } from "react";
import type { SiteManifest } from "../../types/manifest";
import { RichText } from "../RichText/RichText";
import styles from "./AppShell.module.css";

interface AppShellProps {
  manifest: SiteManifest;
  siteTitle: string;
  collections: SiteCollection[];
  activeCollectionId: string;
  children: ReactNode;
}

export function AppShell({ manifest, siteTitle, collections, activeCollectionId, children }: AppShellProps) {
  const navigate = useNavigate();
  const location = useLocation();

  function switchCollection(collectionId: string) {
    const [, , ...rest] = location.pathname.split("/");
    const page = rest.join("/");
    navigate(collectionPath(collectionId, page));
  }

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div>
          <p className={styles.kicker}>{collections.length > 1 ? siteTitle : "Quiver concept collection"}</p>
          <h1>
            <RichText text={manifest.title || "Concept Map"} inline />
          </h1>
        </div>
        {collections.length > 1 ? (
          <label className={styles.collectionPicker}>
            <span>Collection</span>
            <select value={activeCollectionId} onChange={(event) => switchCollection(event.target.value)}>
              {collections.map((collection) => (
                <option key={collection.id} value={collection.id}>
                  {collection.title}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <nav className={styles.nav} aria-label="Primary">
          <NavLink to={collectionPath(activeCollectionId)} end>
            Overview
          </NavLink>
          <NavLink to={collectionPath(activeCollectionId, "graph")}>Graph</NavLink>
          <NavLink to={collectionPath(activeCollectionId, "review")}>Review</NavLink>
          <NavLink to={collectionPath(activeCollectionId, "papers")}>Papers</NavLink>
        </nav>
      </header>
      <main className={styles.main}>
        {children}
      </main>
    </div>
  );
}
