import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";

export const Hello: React.FC = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 30], [0, 1], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div style={{ color: "white", fontSize: 96, fontWeight: 700, opacity }}>
        ShortStack
      </div>
    </AbsoluteFill>
  );
};
