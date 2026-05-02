import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type SceneInput = {
  index: number;
  image_url: string;
  duration_sec: number;
  narration: string;
  on_screen_text: string;
};

export type CaptionWord = {
  text: string;
  start: number;
  end: number;
};

export type VerticalProps = {
  scenes: SceneInput[];
  audio_url: string;
  captions: CaptionWord[];
  cta: string;
  total_duration_sec: number;
};

const KenBurnsScene: React.FC<{
  scene: SceneInput;
  durationFrames: number;
}> = ({ scene, durationFrames }) => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, durationFrames], [1.0, 1.1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const translateX = interpolate(frame, [0, durationFrames], [-20, 20], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: "#000", overflow: "hidden" }}>
      <AbsoluteFill
        style={{
          transform: `scale(${scale}) translateX(${translateX}px)`,
        }}
      >
        <Img
          src={scene.image_url}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
        />
      </AbsoluteFill>
      {scene.on_screen_text && scene.on_screen_text.trim().length > 0 ? (
        <AbsoluteFill
          style={{
            alignItems: "center",
            justifyContent: "flex-start",
            paddingTop: 200,
          }}
        >
          <div
            style={{
              color: "white",
              fontSize: 80,
              fontWeight: 900,
              textAlign: "center",
              padding: "0 60px",
              textShadow:
                "0 4px 16px rgba(0,0,0,0.9), 0 2px 6px rgba(0,0,0,0.9)",
              lineHeight: 1.1,
            }}
          >
            {scene.on_screen_text}
          </div>
        </AbsoluteFill>
      ) : null}
    </AbsoluteFill>
  );
};

const Captions: React.FC<{ captions: CaptionWord[] }> = ({ captions }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  if (!captions || captions.length === 0) {
    return null;
  }

  let activeIdx = -1;
  for (let i = 0; i < captions.length; i++) {
    const w = captions[i];
    if (t >= w.start && t < w.end) {
      activeIdx = i;
      break;
    }
  }

  // If no word is active right now, anchor on the most recent word that ended before t
  if (activeIdx === -1) {
    for (let i = captions.length - 1; i >= 0; i--) {
      if (captions[i].end <= t) {
        activeIdx = i;
        break;
      }
    }
  }

  if (activeIdx === -1) {
    activeIdx = 0;
  }

  // Sliding window of ~6 words centered on the active word.
  const windowSize = 6;
  const half = Math.floor(windowSize / 2);
  let start = Math.max(0, activeIdx - half);
  let end = Math.min(captions.length, start + windowSize);
  start = Math.max(0, end - windowSize);
  const window = captions.slice(start, end);

  const isActuallyActive = (idx: number) => {
    const w = captions[idx];
    return t >= w.start && t < w.end;
  };

  return (
    <AbsoluteFill
      style={{
        alignItems: "center",
        justifyContent: "flex-start",
        paddingTop: 1500,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          alignItems: "center",
          gap: 16,
          padding: "0 80px",
          maxWidth: 1000,
        }}
      >
        {window.map((word, i) => {
          const absoluteIdx = start + i;
          const active =
            absoluteIdx === activeIdx && isActuallyActive(absoluteIdx);
          return (
            <span
              key={`${absoluteIdx}-${word.text}-${word.start}`}
              style={{
                color: active ? "#fbbf24" : "white",
                fontSize: 72,
                fontWeight: 900,
                textShadow:
                  "0 4px 14px rgba(0,0,0,0.95), 0 2px 4px rgba(0,0,0,0.95)",
                lineHeight: 1.1,
              }}
            >
              {word.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const CtaBar: React.FC<{ cta: string; totalDurationSec: number }> = ({
  cta,
  totalDurationSec,
}) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const totalFrames = Math.round(totalDurationSec * fps);
  const fadeStart = Math.max(0, totalFrames - Math.round(3 * fps));
  const opacity = interpolate(frame, [fadeStart, totalFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  if (!cta || cta.trim().length === 0) {
    return null;
  }

  return (
    <AbsoluteFill style={{ pointerEvents: "none", opacity }}>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height: 200,
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0) 0%, rgba(0,0,0,0.92) 100%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 60px",
        }}
      >
        <div
          style={{
            color: "white",
            fontSize: 72,
            fontWeight: 900,
            textAlign: "center",
            textShadow:
              "0 4px 16px rgba(0,0,0,0.95), 0 2px 6px rgba(0,0,0,0.95)",
            lineHeight: 1.1,
          }}
        >
          {cta}
        </div>
      </div>
      {/* Reference height to silence unused destructure */}
      <div style={{ display: "none" }}>{height}</div>
    </AbsoluteFill>
  );
};

export const Vertical: React.FC<VerticalProps> = ({
  scenes,
  audio_url,
  captions,
  cta,
  total_duration_sec,
}) => {
  const { fps } = useVideoConfig();

  let cursorFrames = 0;
  const sceneSegments = scenes.map((scene) => {
    const durationFrames = Math.max(1, Math.round(scene.duration_sec * fps));
    const segment = {
      scene,
      from: cursorFrames,
      durationFrames,
    };
    cursorFrames += durationFrames;
    return segment;
  });

  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {sceneSegments.map((seg) => (
        <Sequence
          key={seg.scene.index}
          from={seg.from}
          durationInFrames={seg.durationFrames}
        >
          <KenBurnsScene
            scene={seg.scene}
            durationFrames={seg.durationFrames}
          />
        </Sequence>
      ))}

      {audio_url ? <Audio src={audio_url} /> : null}

      <Captions captions={captions} />

      <CtaBar cta={cta} totalDurationSec={total_duration_sec} />
    </AbsoluteFill>
  );
};
