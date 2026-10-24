import { describe, expect, it } from "vitest";
import { computeLayout } from "../src/compute";
import { announcementInput, brand, fakeMeasure, format, formats, templates } from "./helpers";

const errorsOf = (issues: { severity: string; code: string }[]) => issues.filter((i) => i.severity === "error");

describe("computeLayout project_announcement", () => {
  it.each(formats.map((f) => `${f.platform}/${f.id}`))("geeft geen fouten en houdt tekst in de safe zone op %s", (key) => {
    const frame = computeLayout(announcementInput(format(key)), fakeMeasure);
    expect(errorsOf(frame.report.issues)).toEqual([]);
    for (const layer of frame.layers) {
      if (layer.kind !== "text") continue;
      expect(layer.textRect.x).toBeGreaterThanOrEqual(frame.safeArea.x - 0.5);
      expect(layer.textRect.y).toBeGreaterThanOrEqual(frame.safeArea.y - 0.5);
      expect(layer.textRect.x + layer.textRect.width).toBeLessThanOrEqual(frame.safeArea.x + frame.safeArea.width + 0.5);
      expect(layer.textRect.y + layer.textRect.height).toBeLessThanOrEqual(frame.safeArea.y + frame.safeArea.height + 0.5);
    }
  });

  it("verbergt de notitie op liggende formaten", () => {
    const frame = computeLayout(announcementInput(format("linkedin/landscape")), fakeMeasure);
    expect(frame.layers.find((l) => l.id === "note")).toBeUndefined();
    expect(frame.report.layers.find((l) => l.id === "note")?.hidden).toBe(true);
  });

  it("waarschuwt bij een licht te kleine foto en geeft een fout bij een veel te kleine", () => {
    const story = format("instagram/story");
    const slightly = computeLayout(announcementInput(story, { width: 3000, height: 1700 }), fakeMeasure);
    expect(slightly.report.issues.map((i) => i.code)).toContain("resolution_low");

    const tiny = computeLayout(announcementInput(story, { width: 800, height: 450 }), fakeMeasure);
    expect(errorsOf(tiny.report.issues).map((i) => i.code)).toContain("resolution_too_low");
  });

  it("meldt overflow bij een te lange titel", () => {
    const input = announcementInput(format("linkedin/landscape"));
    input.post.content["headline"] = "Een veel te lange titel ".repeat(8);
    const frame = computeLayout(input, fakeMeasure);
    expect(frame.report.issues.map((i) => i.code)).toContain("text_overflow");
  });

  it("meldt ontbrekende verplichte velden", () => {
    const input = announcementInput(format("instagram/feed-square"));
    input.post.content["headline"] = "";
    const codes = computeLayout(input, fakeMeasure).report.issues.map((i) => i.code);
    expect(codes).toContain("missing_required_field");
  });

  it("kleedt dezelfde template aan met de kleuren van een ander bedrijf", () => {
    const input = announcementInput(format("instagram/feed-square"));
    input.brand = brand({ textOnDark: "#fefae0", accent: "#e63946" });
    const frame = computeLayout(input, fakeMeasure);
    const headline = frame.layers.find((l) => l.id === "headline");
    const label = frame.layers.find((l) => l.id === "label");
    expect(headline?.kind === "text" && headline.color).toBe("#fefae0");
    expect(label?.kind === "text" && label.color).toBe("#e63946");
  });

  it("honoreert een focus-override van de editor", () => {
    const input = announcementInput(format("instagram/story"));
    input.post.overrides["photo"] = { focus: { x: 0, y: 0.5 }, assetId: null, hidden: null };
    const photo = computeLayout(input, fakeMeasure).layers.find((l) => l.id === "photo");
    expect(photo?.kind === "image" && photo.placement?.x).toBe(0);
  });
});

describe("computeLayout team_member", () => {
  it.each(formats.map((f) => `${f.platform}/${f.id}`))("geeft geen fouten op %s", (key) => {
    const input = announcementInput(format(key));
    input.template = templates["team_member"]!;
    input.post.content = { portrait: "photo", label: "Nieuw in het team", person_name: "Sam Voorbeeld", person_role: "Compositor", quote: "Elke shot is een puzzel." };
    expect(errorsOf(computeLayout(input, fakeMeasure).report.issues)).toEqual([]);
  });
});
