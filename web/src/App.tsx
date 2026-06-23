import { HashRouter, Navigate, Outlet, Route, Routes, useParams } from "react-router-dom";
import { AppShell } from "./components/AppShell/AppShell";
import type { SiteData } from "./data/loadSiteData";
import { useSiteData } from "./data/useSiteData";
import { collectionPath } from "./hooks/useCollectionPath";
import { GraphPage } from "./pages/GraphPage/GraphPage";
import { OverviewPage } from "./pages/OverviewPage/OverviewPage";
import { PapersPage } from "./pages/PapersPage/PapersPage";
import { ReviewPage } from "./pages/ReviewPage/ReviewPage";
import "./styles/tokens.css";
import "./styles/globals.css";
import "./styles/layout.css";

export function App() {
  const state = useSiteData();
  if (state.status === "loading") {
    return <div className="screen-message">Loading concept collection...</div>;
  }
  if (state.status === "error") {
    return <div className="screen-message">Unable to open this concept collection. {state.error.message}</div>;
  }
  return <ReadyApp data={state.data} />;
}

function ReadyApp({ data }: { data: SiteData }) {
  const firstCollectionId = data.collections[0]?.id || data.manifest.project_id;
  return (
    <HashRouter>
      <Routes>
        <Route index element={<Navigate to={collectionPath(firstCollectionId)} replace />} />
        <Route path=":collectionId" element={<CollectionRoute data={data} />}>
          <Route index element={<CollectionPage data={data} page="overview" />} />
          <Route path="graph" element={<CollectionPage data={data} page="graph" />} />
          <Route path="review" element={<CollectionPage data={data} page="review" />} />
          <Route path="papers" element={<CollectionPage data={data} page="papers" />} />
        </Route>
        <Route path="*" element={<Navigate to={collectionPath(firstCollectionId)} replace />} />
      </Routes>
    </HashRouter>
  );
}

function CollectionRoute({ data }: { data: SiteData }) {
  const { collectionId = "" } = useParams();
  const activeCollection = data.collections.find((collection) => collection.id === collectionId);
  const firstCollectionId = data.collections[0]?.id || data.manifest.project_id;
  if (!activeCollection) {
    return <Navigate to={collectionPath(firstCollectionId)} replace />;
  }
  return (
    <AppShell
      manifest={activeCollection.manifest}
      siteTitle={data.title}
      collections={data.collections}
      activeCollectionId={activeCollection.id}
    >
      <Outlet />
    </AppShell>
  );
}

function CollectionPage({ data, page }: { data: SiteData; page: "overview" | "graph" | "review" | "papers" }) {
  const { collectionId = "" } = useParams();
  const activeCollection = data.collections.find((collection) => collection.id === collectionId) || data.collections[0];
  const { graph, analysis } = activeCollection;
  if (page === "graph") return <GraphPage graph={graph} analysis={analysis} />;
  if (page === "review") return <ReviewPage graph={graph} analysis={analysis} />;
  if (page === "papers") return <PapersPage graph={graph} analysis={analysis} />;
  return <OverviewPage graph={graph} analysis={analysis} />;
}
