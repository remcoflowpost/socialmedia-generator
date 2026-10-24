import { describe, expect, it } from "vitest";
import { boxToRect, placeImage, safeAreaRect } from "../src/geometry";
import { format } from "./helpers";

const square = format("instagram/feed-square");
const story = format("instagram/story");

describe("safeAreaRect", () => {
  it("haalt de safe zones van het canvas af", () => {
    expect(safeAreaRect(story)).toEqual({ x: 65, y: 269, width: 950, height: 979 });
  });
});

describe("boxToRect", () => {
  const box = { anchor: "top-left" as const, x: 0, y: 0, width: 50, height: 10, bleed: false };

  it("plaatst top-left in de safe area", () => {
    expect(boxToRect(box, square)).toEqual({ x: 54, y: 54, width: 486, height: 97.2 });
  });

  it("meet offsets bij bottom-right vanaf de rechteronderhoek naar binnen", () => {
    const rect = boxToRect({ ...box, anchor: "bottom-right", x: 10, y: 10 }, square);
    expect(rect.x + rect.width).toBeCloseTo(1080 - 54 - 97.2);
    expect(rect.y + rect.height).toBeCloseTo(1080 - 54 - 97.2);
  });

  it("centreert op het midden", () => {
    const rect = boxToRect({ ...box, anchor: "center" }, story);
    expect(rect.x + rect.width / 2).toBeCloseTo(65 + 950 / 2);
    expect(rect.y + rect.height / 2).toBeCloseTo(269 + 979 / 2);
  });

  it("gebruikt het hele canvas bij bleed", () => {
    expect(boxToRect({ ...box, width: 100, height: 100, bleed: true }, story)).toEqual({ x: 0, y: 0, width: 1080, height: 1920 });
  });
});

describe("placeImage", () => {
  const rect = { x: 0, y: 0, width: 1080, height: 1920 };

  it("vult bij cover en houdt het focuspunt in beeld", () => {
    const placement = placeImage(4000, 2250, rect, "cover", { x: 0.8, y: 0.5 });
    expect(placement.height).toBeCloseTo(1920);
    // Focuspunt op 80% van de breedte moet in het midden van het canvas uitkomen.
    expect(placement.x + 0.8 * placement.width).toBeCloseTo(540);
  });

  it("klemt het beeld zodat er geen lege rand ontstaat", () => {
    const placement = placeImage(4000, 2250, rect, "cover", { x: 1, y: 0.5 });
    expect(placement.x).toBeCloseTo(1080 - placement.width);
  });

  it("lijnt bij contain uit volgens het focuspunt", () => {
    const placement = placeImage(400, 100, { x: 0, y: 0, width: 300, height: 300 }, "contain", { x: 0, y: 1 });
    expect(placement).toMatchObject({ x: 0, y: 225, width: 300, height: 75 });
  });
});
