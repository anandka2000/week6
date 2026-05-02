import React from "react";
import { Composition } from "remotion";
import { Hello } from "./compositions/Hello";
import { Vertical, type VerticalProps } from "./compositions/Vertical";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Hello"
        component={Hello}
        durationInFrames={150}
        fps={30}
        width={1080}
        height={1920}
      />
      <Composition<typeof Vertical, VerticalProps>
        id="Vertical"
        component={Vertical}
        fps={30}
        width={1080}
        height={1920}
        durationInFrames={150}
        defaultProps={{
          scenes: [],
          audio_url: "",
          captions: [],
          cta: "",
          total_duration_sec: 5,
        }}
        calculateMetadata={async ({ props }) => ({
          durationInFrames: Math.max(
            30,
            Math.round(props.total_duration_sec * 30),
          ),
        })}
      />
    </>
  );
};
