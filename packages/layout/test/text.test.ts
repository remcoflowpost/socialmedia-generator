import { describe, expect, it } from "vitest";
import { fitText, wrapText } from "../src/text";
import { fakeMeasure } from "./helpers";

const font = { family: "sans-serif", weight: 400, letterSpacing: 0 };
const base = { font, lineHeight: 1, width: 500, height: 200, minFontSize: 20, maxFontSize: 100, maxLines: 3 };

describe("wrapText", () => {
  it("breekt op woordgrenzen", () => {
    expect(wrapText("aaaa bbbb cccc", font, 10, 50, fakeMeasure)).toEqual(["aaaa bbbb", "cccc"]);
  });

  it("respecteert harde regeleinden", () => {
    expect(wrapText("a\nb", font, 10, 500, fakeMeasure)).toEqual(["a", "b"]);
  });
});

describe("fitText", () => {
  it("kiest de maximale grootte als korte tekst past", () => {
    expect(fitText({ ...base, text: "Kort" }, fakeMeasure)).toMatchObject({ fontSize: 100, overflow: false, lines: ["Kort"] });
  });

  it("verkleint lange tekst tot hij past", () => {
    const result = fitText({ ...base, text: "Een behoorlijk lange titel voor een aankondiging" }, fakeMeasure);
    expect(result.overflow).toBe(false);
    expect(result.fontSize).toBeLessThan(100);
    expect(result.fontSize).toBeGreaterThanOrEqual(20);
    expect(result.lines.length).toBeLessThanOrEqual(3);
    expect(result.textHeight).toBeLessThanOrEqual(200);
  });

  it("meldt overflow in plaats van stil af te kappen", () => {
    const text = "woord ".repeat(80).trim();
    const result = fitText({ ...base, text }, fakeMeasure);
    expect(result.overflow).toBe(true);
    expect(result.fontSize).toBe(20);
    expect(result.lines.join(" ")).toBe(text);
  });

  it("telt letterspacing mee", () => {
    const spaced = fitText({ ...base, text: "Kort", font: { ...font, letterSpacing: 0.5 } }, fakeMeasure);
    const plain = fitText({ ...base, text: "Kort" }, fakeMeasure);
    expect(spaced.textWidth).toBeGreaterThan(plain.textWidth * 0.99);
  });
});
