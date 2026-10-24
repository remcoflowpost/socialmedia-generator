import type { ComputedFrame, ComputedLayer } from "@flow/layout";
import type { CSSProperties, ReactNode } from "react";

export type ImageRenderer = (props: { src: string; style: CSSProperties }) => ReactNode;

const defaultImage: ImageRenderer = ({ src, style }) => <img src={src} style={style} alt="" />;

function rectStyle(layer: ComputedLayer): CSSProperties {
  return {
    position: "absolute",
    left: layer.rect.x,
    top: layer.rect.y,
    width: layer.rect.width,
    height: layer.rect.height,
    zIndex: layer.z,
  };
}

function Layer({ layer, renderImage }: { layer: ComputedLayer; renderImage: ImageRenderer }) {
  if (layer.kind === "shape") {
    return <div style={{ ...rectStyle(layer), background: layer.background, opacity: layer.opacity, borderRadius: layer.radius }} />;
  }

  if (layer.kind === "image") {
    if (!layer.src || !layer.placement) {
      return (
        <div
          style={{
            ...rectStyle(layer),
            background: "repeating-linear-gradient(45deg, #3a3a3a 0 24px, #444 24px 48px)",
            color: "#ddd",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "sans-serif",
            fontSize: Math.max(14, Math.min(layer.rect.height / 6, 36)),
          }}
        >
          {layer.placeholder}
        </div>
      );
    }
    const p = layer.placement;
    return (
      <div style={{ ...rectStyle(layer), overflow: "hidden" }}>
        {renderImage({
          src: layer.src,
          style: { position: "absolute", left: p.x, top: p.y, width: p.width, height: p.height, maxWidth: "none" },
        })}
      </div>
    );
  }

  const lineHeightPx = layer.fontSize * layer.lineHeight;
  return (
    <div
      style={{
        position: "absolute",
        left: layer.textRect.x,
        top: layer.textRect.y,
        width: layer.textRect.width,
        height: layer.textRect.height,
        zIndex: layer.z,
        color: layer.color,
        fontFamily: layer.font.family,
        fontWeight: layer.font.weight,
        fontSize: layer.fontSize,
        letterSpacing: `${layer.font.letterSpacing}em`,
        lineHeight: `${lineHeightPx}px`,
        textAlign: layer.align,
        // Overflow wordt gemeld, niet verborgen: de editor moet het zien.
        outline: layer.overflow ? "4px dashed #ff3b30" : undefined,
      }}
    >
      {layer.lines.map((line, index) => (
        <div key={index} style={{ whiteSpace: "pre", height: lineHeightPx }}>
          {line}
        </div>
      ))}
    </div>
  );
}

function SafeZoneOverlay({ frame }: { frame: ComputedFrame }) {
  const s = frame.safeArea;
  const shade = "rgba(255, 59, 48, 0.28)";
  const band = (style: CSSProperties) => <div style={{ position: "absolute", background: shade, zIndex: 10_000, ...style }} />;
  return (
    <>
      {band({ left: 0, top: 0, width: frame.width, height: s.y })}
      {band({ left: 0, top: s.y + s.height, width: frame.width, height: frame.height - s.y - s.height })}
      {band({ left: 0, top: s.y, width: s.x, height: s.height })}
      {band({ left: s.x + s.width, top: s.y, width: frame.width - s.x - s.width, height: s.height })}
      <div style={{ position: "absolute", left: s.x, top: s.y, width: s.width, height: s.height, outline: "2px dashed rgba(255,59,48,0.9)", zIndex: 10_001 }} />
    </>
  );
}

export interface PostFrameProps {
  frame: ComputedFrame;
  hideText?: boolean;
  showSafeZones?: boolean;
  renderImage?: ImageRenderer;
}

/** Pure weergave van een berekende frame. Geen Remotion-afhankelijkheid. */
export function PostFrame({ frame, hideText = false, showSafeZones = false, renderImage = defaultImage }: PostFrameProps) {
  const layers = hideText ? frame.layers.filter((layer) => layer.kind !== "text") : frame.layers;
  return (
    <div style={{ position: "relative", width: frame.width, height: frame.height, overflow: "hidden", background: "#000" }}>
      {layers.map((layer) => (
        <Layer key={layer.id} layer={layer} renderImage={renderImage} />
      ))}
      {showSafeZones && <SafeZoneOverlay frame={frame} />}
    </div>
  );
}
