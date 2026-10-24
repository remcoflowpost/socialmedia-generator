/**
 * Dry run van de render-pijplijn zonder API of database: maakt placeholderbeelden,
 * rendert project_announcement in alle formaten en schrijft JPEG's plus rapporten weg.
 *
 *   STORAGE_ROOT=/tmp/flow-smoke pnpm --filter @flow/render exec tsx scripts/smoke.ts
 */
import fs from "node:fs/promises";
import path from "node:path";
import type { Format, RenderInput, TemplateDefinition } from "@flow/schema";
import sharp from "sharp";
import fixtures from "../../../packages/layout/test/fixtures.json";
import { config } from "../src/config";
import { renderAndAnalyze } from "../src/renderer";

const base = `http://localhost:${config.port}/storage`;

async function placeholderPhoto(name: string, width: number, height: number): Promise<void> {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
    <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2b4c7e"/><stop offset="1" stop-color="#c06c84"/></linearGradient></defs>
    <rect width="100%" height="100%" fill="url(#g)"/>
    <circle cx="${width * 0.7}" cy="${height * 0.45}" r="${height * 0.25}" fill="#f8b195" opacity="0.8"/>
  </svg>`;
  await fs.mkdir(path.join(config.storageRoot, "smoke"), { recursive: true });
  await sharp(Buffer.from(svg)).jpeg({ quality: 85 }).toFile(path.join(config.storageRoot, "smoke", name));
}

async function main(): Promise<void> {
  await placeholderPhoto("photo.jpg", 4000, 2250);
  await placeholderPhoto("small.jpg", 900, 506);
  const logo = `<svg xmlns="http://www.w3.org/2000/svg" width="400" height="120"><rect x="0" y="20" width="80" height="80" fill="#ffffff"/><rect x="100" y="45" width="280" height="30" fill="#ffffff"/></svg>`;
  await fs.writeFile(path.join(config.storageRoot, "smoke", "logo.svg"), logo);
  const fontDir = path.resolve(import.meta.dirname, "../../../seed/fonts");
  for (const font of ["space-grotesk-latin-700-normal.woff2", "inter-latin-400-normal.woff2"]) {
    await fs.copyFile(path.join(fontDir, font), path.join(config.storageRoot, "smoke", font));
  }

  const photo = process.argv.includes("--small") ? "small" : "photo";
  const out = path.join(config.storageRoot, "smoke", "out");
  await fs.mkdir(out, { recursive: true });

  for (const format of fixtures.formats as Format[]) {
    const input: RenderInput = {
      format,
      template: fixtures.templates.project_announcement as unknown as TemplateDefinition,
      brand: {
        colors: { primary: "#14213d", secondary: "#9ad0ff", accent: "#fca311", textOnDark: "#ffffff", textOnLight: "#14213d" },
        fonts: {
          heading: { family: "Space Grotesk", fallback: "sans-serif", files: [{ assetId: "fh", weight: 700, style: "normal" }] },
          body: { family: "Inter", fallback: "sans-serif", files: [{ assetId: "fb", weight: 400, style: "normal" }] },
        },
        logos: { logoLight: "logo", logoDark: null, logoIcon: null },
        styleAnchor: { description: "", referenceAssetIds: [] },
        negativePrompt: "",
        locks: ["logo", "colors", "fonts"],
      },
      post: {
        content: {
          background_image: "photo",
          label: "Nieuw project",
          headline: "Een nieuwe serie vol vakmanschap",
          client_or_project_name: "Placeholder Studio",
          note: "Kleurcorrectie en VFX door het hele team.",
        },
        overrides: {},
      },
      assets: {
        photo: { src: `${base}/smoke/${photo}.jpg`, mime: "image/jpeg", width: photo === "small" ? 900 : 4000, height: photo === "small" ? 506 : 2250 },
        logo: { src: `${base}/smoke/logo.svg`, mime: "image/svg+xml", width: 400, height: 120 },
        fh: { src: `${base}/smoke/space-grotesk-latin-700-normal.woff2`, mime: "font/woff2", width: null, height: null },
        fb: { src: `${base}/smoke/inter-latin-400-normal.woff2`, mime: "font/woff2", width: null, height: null },
      },
      options: { showSafeZones: process.argv.includes("--safe-zones"), hideText: false },
    };
    const started = Date.now();
    const result = await renderAndAnalyze(input, "jpeg");
    const name = `${format.platform}-${format.id}`;
    await fs.writeFile(path.join(out, `${name}.jpg`), result.image);
    const issues = result.report.issues.map((i) => `${i.severity}:${i.code}${i.layerId ? `(${i.layerId})` : ""}`);
    console.log(`${name.padEnd(28)} ${String(Date.now() - started).padStart(5)} ms  ${issues.join(", ") || "geen issues"}`);
  }
  process.exit(0);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
