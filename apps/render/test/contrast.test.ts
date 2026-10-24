import type { LayoutReport } from "@flow/schema";
import { describe, expect, it } from "vitest";
import { contrastIssues, type RawImage } from "../src/contrast";

function solid(width: number, height: number, rgb: [number, number, number]): RawImage {
  const data = new Uint8Array(width * height * 3);
  for (let i = 0; i < width * height; i++) data.set(rgb, i * 3);
  return { data, width, height, channels: 3 };
}

function report(color: string, fontSize = 30): LayoutReport {
  return {
    formatKey: "instagram/feed-square",
    width: 1080,
    height: 1080,
    issues: [],
    layers: [
      {
        id: "headline",
        type: "text",
        hidden: false,
        box: { x: 10, y: 10, width: 200, height: 50 },
        fontSize,
        lines: ["x"],
        color,
        sourceScale: null,
      },
    ],
  };
}

describe("contrastIssues", () => {
  it("geeft niets bij wit op zwart", () => {
    expect(contrastIssues(report("#ffffff"), solid(300, 100, [0, 0, 0]))).toEqual([]);
  });

  it("waarschuwt bij grijs op grijs", () => {
    const issues = contrastIssues(report("#888888"), solid(300, 100, [120, 120, 120]));
    expect(issues).toHaveLength(1);
    expect(issues[0]).toMatchObject({ code: "contrast_low", severity: "warning", layerId: "headline" });
  });

  it("hanteert 3:1 voor grote tekst", () => {
    // #5f5f5f op zwart is ongeveer 3,3:1: te weinig voor normale tekst, genoeg voor grote.
    expect(contrastIssues(report("#5f5f5f", 30), solid(300, 100, [0, 0, 0]))).toHaveLength(1);
    expect(contrastIssues(report("#5f5f5f", 60), solid(300, 100, [0, 0, 0]))).toEqual([]);
  });

  it("kijkt naar het slechtste deel van een gemengde achtergrond", () => {
    const image = solid(300, 100, [0, 0, 0]);
    // Rechterhelft van de tekstbox wit maken.
    for (let y = 10; y < 60; y++) {
      for (let x = 110; x < 210; x++) image.data.set([255, 255, 255], (y * 300 + x) * 3);
    }
    expect(contrastIssues(report("#ffffff"), image)).toHaveLength(1);
  });
});
