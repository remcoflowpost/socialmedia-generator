import { COMPOSITION_ID, REPORT_MARKER } from "@flow/compositions";
import type { LayoutReport, RenderInput } from "@flow/schema";
import { bundle } from "@remotion/bundler";
import { openBrowser, renderStill, selectComposition, type HeadlessBrowser } from "@remotion/renderer";
import sharp from "sharp";
import { config } from "./config";
import { contrastIssues } from "./contrast";

let serveUrlPromise: Promise<string> | null = null;
let browserPromise: Promise<HeadlessBrowser> | null = null;

/** Bundelt de composities eenmalig per proces. */
function getServeUrl(): Promise<string> {
  serveUrlPromise ??= bundle({ entryPoint: config.entryPoint, onProgress: () => undefined });
  return serveUrlPromise;
}

function getBrowser(): Promise<HeadlessBrowser> {
  browserPromise ??= openBrowser("chrome", { browserExecutable: config.browserExecutable });
  return browserPromise;
}

export async function warmUp(): Promise<void> {
  await Promise.all([getServeUrl(), getBrowser()]);
}

interface StillResult {
  png: Buffer;
  report: LayoutReport | null;
}

async function renderPng(input: RenderInput): Promise<StillResult> {
  const [serveUrl, browser] = await Promise.all([getServeUrl(), getBrowser()]);
  const inputProps = input as unknown as Record<string, unknown>;
  const composition = await selectComposition({ serveUrl, id: COMPOSITION_ID, inputProps, puppeteerInstance: browser });

  let report: LayoutReport | null = null;
  const { buffer } = await renderStill({
    serveUrl,
    composition,
    inputProps,
    imageFormat: "png",
    puppeteerInstance: browser,
    output: null,
    licenseKey: config.licenseKey,
    logLevel: "warn",
    isProduction: config.isProduction,
    onBrowserLog: (log) => {
      if (!log.text.startsWith(REPORT_MARKER)) return;
      report = JSON.parse(log.text.slice(REPORT_MARKER.length)) as LayoutReport;
    },
  });
  if (!buffer) throw new Error("render leverde geen beeld op");
  return { png: buffer, report };
}

export interface RenderResult {
  image: Buffer;
  report: LayoutReport;
}

/**
 * Rendert een formaat en analyseert het. Twee renders: de volledige post, en dezelfde post
 * zonder tekst voor de contrastcheck op de achterliggende pixels.
 */
export async function renderAndAnalyze(input: RenderInput, type: "jpeg" | "png"): Promise<RenderResult> {
  const full = await renderPng({ ...input, options: { ...input.options, hideText: false } });
  if (!full.report) throw new Error("compositie gaf geen layoutrapport terug");

  const background = await renderPng({ ...input, options: { showSafeZones: false, hideText: true } });
  const raw = await sharp(background.png).removeAlpha().raw().toBuffer({ resolveWithObject: true });
  const report: LayoutReport = {
    ...full.report,
    issues: [...full.report.issues, ...contrastIssues(full.report, { data: raw.data, width: raw.info.width, height: raw.info.height, channels: raw.info.channels })],
  };

  // Chromium levert sRGB-pixels zonder profiel; we embedden expliciet sRGB.
  const pipeline = sharp(full.png).withIccProfile("srgb");
  const image = type === "jpeg"
    ? await pipeline.flatten({ background: "#000000" }).jpeg({ quality: 90, chromaSubsampling: "4:4:4", mozjpeg: true }).toBuffer()
    : await pipeline.png({ compressionLevel: 9 }).toBuffer();
  return { image, report };
}
