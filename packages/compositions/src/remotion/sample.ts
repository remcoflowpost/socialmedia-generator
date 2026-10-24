import type { RenderInput } from "@flow/schema";
import fixtures from "../../../layout/test/fixtures.json";

/** Voorbeeldinvoer voor Remotion Studio. Placeholders, geen echte merken of beelden. */
export const sampleInput = {
  format: fixtures.formats[0],
  template: fixtures.templates.project_announcement,
  brand: {
    colors: { primary: "#14213d", secondary: "#9ad0ff", accent: "#fca311", textOnDark: "#ffffff", textOnLight: "#14213d" },
    fonts: {
      heading: { family: "Placeholder Heading", files: [], fallback: "Georgia, serif" },
      body: { family: "Placeholder Body", files: [], fallback: "Arial, sans-serif" },
    },
    logos: { logoLight: null, logoDark: null, logoIcon: null },
    styleAnchor: { description: "", referenceAssetIds: [] },
    negativePrompt: "",
    locks: ["logo", "colors", "fonts"],
  },
  post: {
    content: {
      background_image: null,
      label: "Nieuw project",
      headline: "Een nieuwe serie vol vakmanschap",
      client_or_project_name: "Placeholder Studio",
      note: "Kleurcorrectie en VFX door het hele team.",
    },
    overrides: {},
  },
  assets: {},
  options: { showSafeZones: true, hideText: false },
} as unknown as RenderInput;
