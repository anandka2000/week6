import express, { type Request, type Response } from "express";

const app = express();
app.use(express.json({ limit: "10mb" }));

const PORT = Number(process.env.PORT ?? 8787);

app.get("/health", (_req: Request, res: Response) => {
  res.json({ status: "ok" });
});

app.post("/render", (_req: Request, res: Response) => {
  res.status(501).json({ error: "render not implemented yet (Phase 4)" });
});

app.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`[render] listening on :${PORT}`);
});
