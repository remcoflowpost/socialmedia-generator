import { fontFaceName, type FontRole } from "@flow/layout";
import type { RenderInput } from "@flow/schema";

const loaded = new Map<string, Promise<void>>();
let activeKey = "";

/**
 * Registreert de merkfonts als FontFace onder vaste namen (flow-heading, flow-body).
 * Het resultaat is gecachet per bestand, zodat de preview niet bij elke toetsaanslag laadt.
 * Bij een merkwissel binnen dezelfde pagina worden de oude faces eerst verwijderd.
 */
export async function loadBrandFonts(input: RenderInput): Promise<void> {
  const jobs: Promise<void>[] = [];
  const brandKey = JSON.stringify(input.brand.fonts);
  if (brandKey !== activeKey) {
    // Ander merk: oude faces weg, anders blijven fonts van het vorige merk actief.
    for (const face of Array.from(document.fonts)) {
      if (face.family.replace(/"/g, "").startsWith("flow-")) document.fonts.delete(face);
    }
    loaded.clear();
    activeKey = brandKey;
  }
  for (const role of ["heading", "body"] as FontRole[]) {
    const family = fontFaceName(role);
    const files = input.brand.fonts[role].files;
    for (const file of files) {
      const asset = input.assets[file.assetId];
      if (!asset) continue;
      // Met maar een bestand per rol dekt dat bestand alle gewichten, zodat de browser
      // geen nep-vet synthetiseert als een template een ander gewicht vraagt.
      const weight = files.length === 1 ? "1 1000" : String(file.weight);
      const cacheKey = `${family}|${asset.src}|${weight}|${file.style}`;
      if (!loaded.has(cacheKey)) {
        loaded.set(cacheKey, registerFace(family, asset.src, weight, file.style));
      }
      jobs.push(loaded.get(cacheKey)!);
    }
  }
  await Promise.all(jobs);
}

async function registerFace(family: string, src: string, weight: string, style: string): Promise<void> {
  const face = new FontFace(family, `url(${JSON.stringify(src)})`, { weight, style });
  await face.load();
  document.fonts.add(face);
}
