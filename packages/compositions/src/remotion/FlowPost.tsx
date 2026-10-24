import { computeLayout } from "@flow/layout";
import type { LayoutReport, RenderInput } from "@flow/schema";
import { useEffect, useMemo, useState } from "react";
import { cancelRender, continueRender, delayRender, getRemotionEnvironment, Img } from "remotion";
import { loadBrandFonts } from "../fonts";
import { canvasMeasure } from "../measure";
import { PostFrame } from "../PostFrame";

/** Markering waarmee de render-service het layoutrapport uit de browserlog haalt. */
export const REPORT_MARKER = "__FLOW_LAYOUT_REPORT__";

export type FlowPostProps = RenderInput & {
  /** Alleen in de browser-preview: ontvangt het layoutrapport na elke berekening. */
  onReport?: (report: LayoutReport) => void;
};

function fontsKey(input: RenderInput): string {
  return JSON.stringify([input.brand.fonts, input.brand.fonts.heading.files.map((f) => input.assets[f.assetId]?.src)]);
}

export function FlowPost(props: FlowPostProps) {
  const { onReport, ...input } = props;
  const key = fontsKey(input);
  const [readyKey, setReadyKey] = useState<string | null>(null);

  useEffect(() => {
    const handle = delayRender("merkfonts laden");
    let cancelled = false;
    loadBrandFonts(input)
      .then(() => {
        if (!cancelled) setReadyKey(key);
        continueRender(handle);
      })
      .catch((error) => {
        // Een export met een fallback-font is een merkfout: render afbreken in plaats van
        // stil doorgaan. In de preview tonen we het wel, met de fallback.
        if (getRemotionEnvironment().isRendering) {
          cancelRender(new Error(`merkfonts laden mislukt: ${String(error)}`));
          return;
        }
        console.error("merkfonts laden mislukt", error);
        if (!cancelled) setReadyKey(key);
        continueRender(handle);
      });
    return () => {
      cancelled = true;
    };
    // De sleutel vat alle font-invoer samen.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const fontsReady = readyKey === key;
  // Op inhoud memoizen, niet op objectidentiteit: de preview geeft bij elke render een
  // nieuw props-object mee en onReport mag geen render-lus veroorzaken.
  const inputKey = JSON.stringify(input);
  const frame = useMemo(
    () => (fontsReady ? computeLayout(JSON.parse(inputKey) as RenderInput, canvasMeasure) : null),
    [fontsReady, inputKey],
  );

  useEffect(() => {
    if (!frame) return;
    onReport?.(frame.report);
    if (getRemotionEnvironment().isRendering) {
      console.log(REPORT_MARKER + JSON.stringify(frame.report));
    }
    // onReport bewust niet als dependency: alleen een nieuwe frame telt.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [frame]);

  if (!frame) return null;
  return (
    <PostFrame
      frame={frame}
      hideText={input.options.hideText}
      showSafeZones={input.options.showSafeZones}
      renderImage={({ src, style }) => <Img src={src} style={style} />}
    />
  );
}
