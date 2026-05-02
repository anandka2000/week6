import express, { type Request, type Response } from "express";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
app.use(express.json({ limit: "10mb" }));

const PORT = Number(process.env.PORT ?? 8787);

const S3_ENDPOINT_URL = process.env.S3_ENDPOINT_URL ?? "http://localhost:9000";
const S3_ACCESS_KEY = process.env.S3_ACCESS_KEY ?? "shortstack";
const S3_SECRET_KEY = process.env.S3_SECRET_KEY ?? "shortstack-dev-secret";
const S3_BUCKET = process.env.S3_BUCKET ?? "shortstack";
const S3_REGION = process.env.S3_REGION ?? "us-east-1";

const s3 = new S3Client({
  endpoint: S3_ENDPOINT_URL,
  region: S3_REGION,
  forcePathStyle: true,
  credentials: {
    accessKeyId: S3_ACCESS_KEY,
    secretAccessKey: S3_SECRET_KEY,
  },
});

let bundlePromise: Promise<string> | null = null;

const getServeUrl = (): Promise<string> => {
  if (!bundlePromise) {
    const entryPoint = path.resolve(__dirname, "index.ts");
    bundlePromise = bundle({ entryPoint }).catch((err) => {
      // Reset so a subsequent call can retry
      bundlePromise = null;
      throw err;
    });
  }
  return bundlePromise;
};

type SceneInput = {
  index: number;
  image_url: string;
  duration_sec: number;
  narration: string;
  on_screen_text: string;
};

type CaptionWord = { text: string; start: number; end: number };

type RenderRequestBody = {
  video_id?: string;
  scenes?: SceneInput[];
  audio_url?: string;
  captions?: CaptionWord[];
  cta?: string;
  total_duration_sec?: number;
};

app.get("/health", (_req: Request, res: Response) => {
  res.json({ status: "ok" });
});

app.post("/render", async (req: Request, res: Response) => {
  const body = req.body as RenderRequestBody;
  const missing: string[] = [];

  if (!body || typeof body !== "object") {
    res.status(400).json({ error: "request body must be JSON" });
    return;
  }
  if (!body.video_id || typeof body.video_id !== "string") {
    missing.push("video_id");
  }
  if (!Array.isArray(body.scenes)) {
    missing.push("scenes");
  }
  if (!body.audio_url || typeof body.audio_url !== "string") {
    missing.push("audio_url");
  }
  if (!Array.isArray(body.captions)) {
    missing.push("captions");
  }
  if (typeof body.cta !== "string") {
    missing.push("cta");
  }
  if (
    typeof body.total_duration_sec !== "number" ||
    !Number.isFinite(body.total_duration_sec) ||
    body.total_duration_sec <= 0
  ) {
    missing.push("total_duration_sec");
  }

  if (missing.length > 0) {
    res
      .status(400)
      .json({ error: `missing or invalid fields: ${missing.join(", ")}` });
    return;
  }

  const videoId = body.video_id as string;
  const inputProps = {
    scenes: body.scenes as SceneInput[],
    audio_url: body.audio_url as string,
    captions: body.captions as CaptionWord[],
    cta: body.cta as string,
    total_duration_sec: body.total_duration_sec as number,
  };

  const startMs = Date.now();
  const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "shortstack-render-"));
  const outputLocation = path.join(tmpDir, "output.mp4");

  try {
    const serveUrl = await getServeUrl();
    const composition = await selectComposition({
      serveUrl,
      id: "Vertical",
      inputProps,
    });

    await renderMedia({
      composition,
      serveUrl,
      codec: "h264",
      outputLocation,
      inputProps,
    });

    const bytes = await fs.readFile(outputLocation);
    const s3Key = `videos/${videoId}/output.mp4`;
    await s3.send(
      new PutObjectCommand({
        Bucket: S3_BUCKET,
        Key: s3Key,
        Body: bytes,
        ContentType: "video/mp4",
      }),
    );

    const renderMs = Date.now() - startMs;
    res.status(200).json({
      s3_key: s3Key,
      duration_sec: inputProps.total_duration_sec,
      size_bytes: bytes.length,
      render_ms: renderMs,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    // eslint-disable-next-line no-console
    console.error(`[render] failed for video_id=${videoId}: ${message}`);
    res.status(500).json({ error: message });
  } finally {
    try {
      await fs.rm(tmpDir, { recursive: true, force: true });
    } catch {
      // best-effort cleanup
    }
  }
});

app.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`[render] listening on :${PORT}`);
});
