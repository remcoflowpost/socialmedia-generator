import type { Format } from "@flow/schema";
import type { ComponentType } from "react";
import { Composition } from "remotion";
import { FlowPost } from "./FlowPost";
import { sampleInput } from "./sample";

export const COMPOSITION_ID = "flow-post";

// Remotion verwacht props met een index-signature; de gegenereerde interfaces hebben die niet.
type LooseProps = Record<string, unknown>;

export function Root() {
  return (
    <Composition
      id={COMPOSITION_ID}
      component={FlowPost as unknown as ComponentType<LooseProps>}
      width={1080}
      height={1080}
      fps={30}
      durationInFrames={1}
      defaultProps={sampleInput as unknown as LooseProps}
      calculateMetadata={({ props }) => {
        const format = props.format as Format;
        return { width: format.width, height: format.height };
      }}
    />
  );
}
