import { FlowPost } from "@flow/compositions";
import type { LayoutReport, RenderInput } from "@flow/schema";
import { Player } from "@remotion/player";
import type { ComponentType } from "react";

// Remotion verwacht props met een index-signature.
const Component = FlowPost as unknown as ComponentType<Record<string, unknown>>;

export function Preview({
  input,
  onReport,
  maxHeight = "68vh",
}: {
  input: RenderInput;
  onReport?: (report: LayoutReport) => void;
  maxHeight?: string;
}) {
  const { width, height } = input.format;
  return (
    <div className="mx-auto overflow-hidden rounded shadow-lg" style={{ aspectRatio: `${width} / ${height}`, maxHeight, maxWidth: "100%", height: maxHeight }}>
      <Player
        component={Component}
        inputProps={{ ...input, onReport } as unknown as Record<string, unknown>}
        compositionWidth={width}
        compositionHeight={height}
        durationInFrames={1}
        fps={30}
        style={{ width: "100%", height: "100%" }}
        controls={false}
        acknowledgeRemotionLicense
      />
    </div>
  );
}
