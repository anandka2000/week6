import React from "react";
import { Composition } from "remotion";
import { Hello } from "./compositions/Hello";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Hello"
      component={Hello}
      durationInFrames={150}
      fps={30}
      width={1080}
      height={1920}
    />
  );
};
