"use client";

const SURFACE_BG = "#0a1018";
const EXPORT_WIDTH_PX = 1280;
const EXPORT_PADDING_PX = 24;
const EXPORT_GAP_PX = 24;
const EXPORT_SCALE = 2;
/** Muted caption — matches design token on-surface-variant (#b2c4d8). */
const EXPORT_FOOTNOTE_COLOR = "#b2c4d8";
const EXPORT_FOOTNOTE_TEXT = "@fbobiano";

function appendExportFootnote(root: HTMLElement): void {
  const foot = document.createElement("div");
  foot.setAttribute("data-export-footnote", "true");
  foot.textContent = EXPORT_FOOTNOTE_TEXT;
  foot.style.cssText = [
    "flex-shrink: 0",
    "width: 100%",
    "box-sizing: border-box",
    "text-align: center",
    "padding-top: 2px",
    "font-family: Inter, ui-sans-serif, system-ui, sans-serif",
    "font-size: 11px",
    "line-height: 1.5",
    `color: ${EXPORT_FOOTNOTE_COLOR}`,
  ].join(";");
  root.appendChild(foot);
}

export async function runExportPng(nodes: HTMLElement[], filename: string): Promise<void> {
  if (typeof window === "undefined") return;
  if (nodes.length === 0) return;

  const container = document.createElement("div");
  // Fixed 1280px regardless of device viewport — exports are deterministic
  // across mobile/desktop. Off-screen positioning keeps it invisible.
  container.style.cssText = [
    "position: fixed",
    "top: 0",
    `left: -${EXPORT_WIDTH_PX + 200}px`,
    `width: ${EXPORT_WIDTH_PX}px`,
    `padding: ${EXPORT_PADDING_PX}px`,
    `background: ${SURFACE_BG}`,
    "display: flex",
    "flex-direction: column",
    `gap: ${EXPORT_GAP_PX}px`,
    "color-scheme: dark",
    "pointer-events: none",
    "z-index: 2147483647",
    "overflow: visible",
  ].join(";");
  container.setAttribute("data-export-root", "true");

  // Suppress scrollbars in the snapshot — they often render as native chrome
  // and look like grey bars across the bottom of scroll containers.
  const styleEl = document.createElement("style");
  styleEl.textContent = `
    [data-export-root] *::-webkit-scrollbar { display: none !important; width: 0 !important; height: 0 !important; }
    [data-export-root] * { scrollbar-width: none !important; -ms-overflow-style: none !important; }
  `;
  container.appendChild(styleEl);

  // Capture each live Plotly graph as a PNG data URL up-front. Cloning the DOM
  // doesn't carry canvas/WebGL pixels (so scattergl dots, layoutImages logos,
  // etc. would render blank). After cloning we swap each `.js-plotly-plot` for
  // an <img> backed by the pre-rendered PNG.
  const plotlySnapshots = await capturePlotlySnapshots(nodes);

  // Tag each scrolled element on the LIVE tree with its current scrollLeft /
  // scrollTop. cloneNode carries the attribute over, so the clone can mirror
  // the visible window onto the content (e.g. a horizontally-scrolled lane).
  const scrollMarks = markLiveScrollPositions(nodes);

  for (const node of nodes) {
    const clone = node.cloneNode(true) as HTMLElement;
    stripHiddenSubtrees(clone);
    forceEagerImages(clone);
    applyExportGridOverrides(clone);
    container.appendChild(clone);
  }

  // Restore the live tree before we touch the clone so we don't keep stray
  // attributes around if anything below throws.
  scrollMarks.forEach((el) => el.removeAttribute("data-export-scroll"));

  swapPlotlyClonesForImages(container, plotlySnapshots);
  applyScrollMarksOnClones(container);
  appendExportFootnote(container);

  document.body.appendChild(container);

  try {
    // Let the browser apply layout/paint to the cloned tree before snapshotting.
    await nextFrame();
    // Inline every <img> as a data URL up-front. This sidesteps lazy-loading,
    // intersection observers, CORS quirks and modern-screenshot's own
    // resource-fetch path — once the src is data:, the snapshot just works.
    await inlineImagesAsDataUrls(container);
    await preloadImages(container);
    const { domToPng } = await import("modern-screenshot");
    const dataUrl = await domToPng(container, {
      scale: EXPORT_SCALE,
      backgroundColor: SURFACE_BG,
      width: EXPORT_WIDTH_PX,
      height: container.scrollHeight,
    });
    if (!dataUrl || dataUrl.length < 100) {
      throw new Error(`Empty snapshot (dataUrl length=${dataUrl?.length ?? 0})`);
    }
    triggerDownload(dataUrl, filename);
  } catch (err) {
    console.error("[export] snapshot failed", err);
    throw err;
  } finally {
    container.remove();
  }
}

function stripHiddenSubtrees(root: HTMLElement): void {
  const hidden = root.querySelectorAll<HTMLElement>("[data-export-hide]");
  hidden.forEach((el) => el.remove());
}

function forceEagerImages(root: HTMLElement): void {
  const imgs = root.querySelectorAll<HTMLImageElement>("img");
  imgs.forEach((img) => {
    img.loading = "eager";
    img.decoding = "sync";
  });
}

/**
 * Honour `data-export-grid="N"` on any element in the cloned tree by forcing
 * an inline `grid-template-columns: repeat(N, minmax(0, 1fr))`. Lets pages
 * pin the export layout (e.g. rankings always 3 cols) regardless of viewport.
 */
function applyExportGridOverrides(root: HTMLElement): void {
  const targets = root.querySelectorAll<HTMLElement>("[data-export-grid]");
  targets.forEach((el) => {
    const cols = Number(el.getAttribute("data-export-grid"));
    if (!Number.isFinite(cols) || cols <= 0) return;
    el.style.display = "grid";
    el.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
  });
  // Also apply to root itself if it carries the attribute
  if (root.hasAttribute("data-export-grid")) {
    const cols = Number(root.getAttribute("data-export-grid"));
    if (Number.isFinite(cols) && cols > 0) {
      root.style.display = "grid";
      root.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
    }
  }
}

function triggerDownload(dataUrl: string, filename: string): void {
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function nextFrame(): Promise<void> {
  return new Promise((resolve) => {
    if (typeof window.requestAnimationFrame === "function") {
      window.requestAnimationFrame(() => window.requestAnimationFrame(() => resolve()));
    } else {
      setTimeout(resolve, 16);
    }
  });
}

interface PlotlySnapshot {
  dataUrl: string;
  width: number;
  height: number;
}

async function capturePlotlySnapshots(nodes: HTMLElement[]): Promise<PlotlySnapshot[]> {
  const out: PlotlySnapshot[] = [];
  const liveDivs: HTMLElement[] = [];
  for (const n of nodes) {
    n.querySelectorAll<HTMLElement>(".js-plotly-plot").forEach((d) => liveDivs.push(d));
  }
  if (liveDivs.length === 0) return out;
  if (typeof document !== "undefined" && document.fonts?.ready) {
    try {
      await document.fonts.ready;
    } catch {
      /* ignore */
    }
  }
  let Plotly: typeof import("plotly.js-basic-dist-min") | null = null;
  try {
    const mod = await import("plotly.js-basic-dist-min");
    Plotly = (mod as { default?: typeof import("plotly.js-basic-dist-min") }).default ?? mod;
  } catch (err) {
    console.warn("[export] could not load Plotly for snapshotting", err);
    return out;
  }
  for (const div of liveDivs) {
    const rect = div.getBoundingClientRect();
    const w = Math.max(1, Math.round(rect.width));
    const h = Math.max(1, Math.round(rect.height));
    try {
      const dataUrl = await (Plotly as unknown as {
        toImage: (
          gd: HTMLElement,
          opts: { format: string; width: number; height: number; scale?: number },
        ) => Promise<string>;
      }).toImage(div, { format: "png", width: w, height: h, scale: 3 });
      out.push({ dataUrl, width: w, height: h });
    } catch (err) {
      console.warn("[export] Plotly.toImage failed", err);
      out.push({ dataUrl: "", width: w, height: h });
    }
  }
  return out;
}

function markLiveScrollPositions(nodes: HTMLElement[]): HTMLElement[] {
  const marked: HTMLElement[] = [];
  for (const n of nodes) {
    const candidates = n.querySelectorAll<HTMLElement>("*");
    candidates.forEach((el) => {
      if (el.scrollLeft === 0 && el.scrollTop === 0) return;
      if (el.scrollWidth <= el.clientWidth && el.scrollHeight <= el.clientHeight) return;
      const cs = n.ownerDocument?.defaultView?.getComputedStyle(el);
      const ox = cs?.overflowX ?? "";
      const oy = cs?.overflowY ?? "";
      const scrollable =
        ox === "auto" || ox === "scroll" || oy === "auto" || oy === "scroll";
      if (!scrollable) return;
      el.setAttribute("data-export-scroll", `${el.scrollLeft},${el.scrollTop}`);
      marked.push(el);
    });
  }
  return marked;
}

function applyScrollMarksOnClones(container: HTMLElement): void {
  const marked = container.querySelectorAll<HTMLElement>("[data-export-scroll]");
  marked.forEach((el) => {
    const raw = el.getAttribute("data-export-scroll") ?? "0,0";
    const [lStr, tStr] = raw.split(",");
    const left = Number(lStr) || 0;
    const top = Number(tStr) || 0;
    el.removeAttribute("data-export-scroll");
    if (left === 0 && top === 0) return;
    // Translate every direct child by the same offset so siblings move
    // together (translating only firstElementChild leaves the others behind).
    Array.from(el.children).forEach((child) => {
      const c = child as HTMLElement;
      c.style.transform = `translate(${-left}px, ${-top}px)`;
      c.style.willChange = "transform";
    });
    el.style.overflow = "hidden";
  });
}

function swapPlotlyClonesForImages(container: HTMLElement, snapshots: PlotlySnapshot[]): void {
  if (snapshots.length === 0) return;
  const cloneDivs = Array.from(container.querySelectorAll<HTMLElement>(".js-plotly-plot"));
  cloneDivs.forEach((cloneDiv, i) => {
    const snap = snapshots[i];
    if (!snap || !snap.dataUrl) return;
    const img = document.createElement("img");
    img.src = snap.dataUrl;
    // Live capture uses viewport-sized Plotly width; the export tree is laid out
    // at EXPORT_WIDTH_PX. Fixed px here leaves a large empty band on wide exports.
    img.style.width = "100%";
    img.style.height = "auto";
    img.style.display = "block";
    img.style.maxWidth = "100%";
    img.alt = "";
    cloneDiv.replaceWith(img);
  });
}

async function inlineImagesAsDataUrls(root: HTMLElement): Promise<void> {
  const imgs = Array.from(root.querySelectorAll<HTMLImageElement>("img"));
  await Promise.all(
    imgs.map(async (img) => {
      const src = img.getAttribute("src");
      if (!src || src.startsWith("data:")) return;
      try {
        const res = await fetch(src, { credentials: "same-origin" });
        if (!res.ok) {
          console.warn("[export] image fetch failed", src, res.status);
          return;
        }
        const blob = await res.blob();
        const dataUrl = await blobToDataUrl(blob);
        img.removeAttribute("srcset");
        img.removeAttribute("crossorigin");
        // Wait until the new src is fully decoded before resolving so the
        // snapshot doesn't race ahead with a half-loaded image.
        await new Promise<void>((resolve) => {
          const done = () => {
            img.removeEventListener("load", done);
            img.removeEventListener("error", done);
            img.decode().catch(() => undefined).finally(() => resolve());
          };
          img.addEventListener("load", done);
          img.addEventListener("error", done);
          img.src = dataUrl;
        });
      } catch (err) {
        console.warn("[export] image inline error", src, err);
      }
    }),
  );
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

async function preloadImages(root: HTMLElement): Promise<void> {
  const imgs = Array.from(root.querySelectorAll("img"));
  await Promise.all(
    imgs.map((img) => {
      if (img.complete && img.naturalWidth > 0) {
        return img.decode().catch(() => undefined);
      }
      return new Promise<void>((resolve) => {
        const done = () => {
          img.removeEventListener("load", done);
          img.removeEventListener("error", done);
          // decode after load to ensure the bitmap is ready
          img.decode().catch(() => undefined).finally(() => resolve());
        };
        img.addEventListener("load", done);
        img.addEventListener("error", done);
      });
    }),
  );
}
