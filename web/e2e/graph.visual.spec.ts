import { expect, test } from "@playwright/test";

const COLLECTION_ID = "top4-geometric-analysis-narrow-v1";
const COLLECTION_TITLE = /Top-4 Geometric Analysis \(Narrow\)/i;

test("graph page renders a dependency-oriented map", async ({ page }, testInfo) => {
  const consoleMessages: string[] = [];
  page.on("console", (message) => consoleMessages.push(message.text()));
  await page.goto(`/#/${COLLECTION_ID}/graph`);
  await expect(page.getByRole("heading", { name: COLLECTION_TITLE })).toBeVisible();
  await expect(page.getByLabel("Concept map filters")).toBeVisible();
  await expect(page.getByText("prerequisite -> dependent")).toBeVisible();
  await expect(page.getByLabel("Minimum references")).toHaveValue("2");
  await expect(page.getByText("More filters")).toBeVisible();
  await expect(page.getByLabel("Relation type")).toBeHidden();

  const svg = page.getByLabel("Concept dependency graph");
  await expect(svg).toBeVisible();
  const expected = await page.evaluate(async () => {
    const graph = await fetch("./graph.json").then((response) => response.json());
    const counts = new Map(graph.nodes.map((node: { id: string; paper_ids?: string[] }) => [node.id, 0]));
    graph.edges.forEach((edge: { relation: string; prerequisite: string; dependent: string; paper_ids?: string[] }) => {
      if (edge.relation === "belongs_to_topic") return;
      const weight = Math.max(1, edge.paper_ids?.length || 0);
      counts.set(edge.prerequisite, (counts.get(edge.prerequisite) || 0) + weight);
      counts.set(edge.dependent, (counts.get(edge.dependent) || 0) + weight);
    });
    graph.nodes.forEach((node: { id: string; paper_ids?: string[] }) => {
      const paperCount = node.paper_ids?.length || 0;
      if (paperCount > (counts.get(node.id) || 0)) counts.set(node.id, paperCount);
    });
    const visibleIds = new Set(graph.nodes.filter((node: { id: string }) => (counts.get(node.id) || 0) >= 2).map((node: { id: string }) => node.id));
    return {
      nodes: visibleIds.size,
      dependencyEdges: graph.edges.filter(
        (edge: { relation: string; prerequisite: string; dependent: string }) =>
          edge.relation !== "belongs_to_topic" && visibleIds.has(edge.prerequisite) && visibleIds.has(edge.dependent)
      ).length
    };
  });
  const nodeCount = await page.locator("[data-node]").count();
  const edgeCount = Number(await page.locator("[data-edge-count]").getAttribute("data-edge-count"));
  expect(nodeCount).toBe(expected.nodes);
  expect(edgeCount).toBe(expected.dependencyEdges);
  await expect(page.locator("[data-edge]")).toHaveCount(0);

  const radii = await page.locator("[data-node-circle='true']").evaluateAll((circles) =>
    circles.map((circle) => Number(circle.getAttribute("r") || "0")).filter((radius) => radius > 0)
  );
  expect(Math.max(...radii) - Math.min(...radii)).toBeGreaterThan(5);
  const columnsAreWeightSorted = await page.locator("[data-node]").evaluateAll((nodeGroups) => {
    const columns = new Map<string, Array<{ y: number; degree: number }>>();
    nodeGroups.forEach((node) => {
      const transform = node.getAttribute("transform") || "";
      const match = transform.match(/translate\(([-\d.]+),\s*([-\d.]+)\)/);
      if (!match) return;
      const x = Math.round(Number(match[1])).toString();
      const y = Number(match[2]);
      const degree = Number(node.getAttribute("data-degree") || "0");
      columns.set(x, [...(columns.get(x) || []), { y, degree }]);
    });
    return [...columns.values()].every((column) => {
      const sorted = column.sort((left, right) => left.y - right.y);
      return sorted.every((item, index) => index === 0 || item.degree <= sorted[index - 1].degree);
    });
  });
  expect(columnsAreWeightSorted).toBe(true);
  await expect(page.locator('[aria-label="Concept dependency graph"] svg text')).toHaveCount(expected.nodes);

  await page.screenshot({ path: testInfo.outputPath("graph-page.png"), fullPage: true });
  await page.getByRole("button", { name: /enter full screen graph/i }).click();
  await expect(page.getByLabel("Concept dependency graph")).toHaveClass(/fullscreen/);
  await page.screenshot({ path: testInfo.outputPath("graph-fullscreen.png"), fullPage: true });
  await page.keyboard.press("Escape");
  await expect(page.getByLabel("Concept dependency graph")).not.toHaveClass(/fullscreen/);
  const graphBox = await page.getByLabel("Concept dependency graph").boundingBox();
  expect(graphBox).not.toBeNull();
  if (graphBox && testInfo.project.name.includes("desktop")) {
    await page.mouse.move(graphBox.x + graphBox.width / 2, graphBox.y + graphBox.height / 2);
    await page.mouse.wheel(0, 160);
    const beforeDrag = await page.locator("[data-graph-content='true']").getAttribute("transform");
    await page.mouse.down();
    await page.mouse.move(graphBox.x + graphBox.width / 2 - 120, graphBox.y + graphBox.height / 2 - 20);
    await page.mouse.up();
    await expect(page.locator("[data-graph-content='true']")).not.toHaveAttribute("transform", beforeDrag || "");
  }
  expect(consoleMessages.some((text) => text.includes("Unable to preventDefault inside passive event listener"))).toBe(false);
  await page.getByText("More filters").click();
  await expect(page.getByLabel("Relation type")).toBeVisible();
});

test("node selection opens details without changing the visible map", async ({ page }, testInfo) => {
  await page.goto(`/#/${COLLECTION_ID}/graph`);
  await page.getByLabel("Concept dependency graph").scrollIntoViewIfNeeded();
  const baselineNodeCount = await page.locator("[data-node]").count();
  const baselineEdgeCount = await page.locator("[data-edge-count]").getAttribute("data-edge-count");
  const baselineLabelCount = await page.locator('[aria-label="Concept dependency graph"] svg text').count();
  const conceptDetails = page.locator('aside[aria-label="Concept details"]');
  const visibleNodeIds = await page.locator("[data-node]").evaluateAll((nodes) => {
    const graphBox = document.querySelector('[aria-label="Concept dependency graph"]')?.getBoundingClientRect();
    return nodes
      .filter((node) => {
        const circle = node.querySelector('[data-node-circle="true"]');
        const box = circle?.getBoundingClientRect();
        if (!box) return false;
        return (
          box.width > 3 &&
          box.height > 3 &&
          box.left > 0 &&
          box.top > 0 &&
          box.right < window.innerWidth &&
          box.bottom < window.innerHeight &&
          (!graphBox || (box.left > graphBox.left + 20 && box.top > graphBox.top + 90))
        );
      })
      .slice(0, 3)
      .map((node) => node.getAttribute("data-node") || "")
      .filter(Boolean);
  });
  expect(visibleNodeIds.length).toBeGreaterThan(1);

  for (const [index, nodeId] of visibleNodeIds.entries()) {
    const escapedNodeId = nodeId.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
    await page.locator(`[data-node="${escapedNodeId}"] [data-node-circle="true"]`).click();
    await expect(page).toHaveURL(/node=/);
    await expect(conceptDetails).toBeVisible();
    await expect(page.getByRole("button", { name: /clear selection/i })).toHaveCount(0);
    await expect(page.locator("[data-node]")).toHaveCount(baselineNodeCount);
    await expect(page.locator("[data-edge-count]")).toHaveAttribute("data-edge-count", baselineEdgeCount || "");
    await expect(page.locator('[aria-label="Concept dependency graph"] svg text')).toHaveCount(baselineLabelCount);
    if (index === 0) {
      await page.screenshot({ path: testInfo.outputPath("selected-node.png"), fullPage: true });
    }
    if (index === 0) {
      await page.getByText("Read dependencies from left to right.").click();
      await expect(page).not.toHaveURL(/node=/);
      await expect(conceptDetails).toHaveCount(0);
    } else if (index < visibleNodeIds.length - 1) {
      await page.getByRole("button", { name: /close concept details/i }).click();
      await expect(page).not.toHaveURL(/node=/);
      await expect(conceptDetails).toHaveCount(0);
    }
  }

  await page.getByRole("button", { name: /close concept details/i }).click();
  await expect(page).not.toHaveURL(/node=/);
  await expect(conceptDetails).toHaveCount(0);
});

test("paper links filter the graph while preserving the selected node", async ({ page }) => {
  await page.goto(`/#/${COLLECTION_ID}/graph`);
  await page.waitForSelector('[aria-label="Concept dependency graph"] [data-node]');
  await page.locator('[data-node] [data-node-circle="true"]').first().click();
  await page.waitForSelector('aside[aria-label="Concept details"]');

  const paperLink = page.locator('aside[aria-label="Concept details"] a', { hasText: "Filter graph" }).first();
  await expect(paperLink).toBeVisible();
  await paperLink.click();

  await expect(page).toHaveURL(new RegExp(`#/${COLLECTION_ID}/graph\\?[^#]*paper=[^&]+`));
  await expect(page).toHaveURL(/node=/);
  await expect(page.locator('aside[aria-label="Concept details"]')).toBeVisible();
  const selectedPaper = page.locator('section[aria-label="Selected paper"]');
  await expect(selectedPaper).toBeVisible();
  await expect(selectedPaper).toContainText(/Published in|Primary MSC|DOI/);
});
