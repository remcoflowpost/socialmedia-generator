import type { BrandKitData, Format, RenderInput, TemplateDefinition } from "@flow/schema";
import fixtures from "./fixtures.json";
import type { TextMeasurer } from "../src/text";

export const formats = fixtures.formats as Format[];
export const templates = fixtures.templates as unknown as Record<string, TemplateDefinition>;

/** Deterministische meter: elk teken is 0,55 em breed. */
export const fakeMeasure: TextMeasurer = (text, _font, size) => text.length * size * 0.55;

export function brand(overrides: Partial<BrandKitData["colors"]> = {}): BrandKitData {
  const font = (family: string) => ({ family, fallback: "sans-serif", files: [{ assetId: `${family}-font`, weight: 400, style: "normal" as const }] });
  return {
    colors: {
      primary: "#101820",
      secondary: "#9ad0ff",
      accent: "#ffb000",
      textOnDark: "#ffffff",
      textOnLight: "#101820",
      ...overrides,
    },
    fonts: { heading: font("Heading"), body: font("Body") },
    logos: { logoLight: "logo", logoDark: null, logoIcon: null },
    styleAnchor: { description: "", referenceAssetIds: [] },
    negativePrompt: "",
    locks: ["logo", "colors", "fonts"],
  };
}

export function format(key: string): Format {
  const found = formats.find((f) => `${f.platform}/${f.id}` === key);
  if (!found) throw new Error(`onbekend formaat ${key}`);
  return found;
}

export function announcementInput(fmt: Format, photo = { width: 4000, height: 2250 }): RenderInput {
  return {
    format: fmt,
    template: templates["project_announcement"]!,
    brand: brand(),
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
      photo: { src: "photo.jpg", mime: "image/jpeg", ...photo },
      logo: { src: "logo.svg", mime: "image/svg+xml", width: 400, height: 120 },
    },
    options: { showSafeZones: false, hideText: false },
  };
}
