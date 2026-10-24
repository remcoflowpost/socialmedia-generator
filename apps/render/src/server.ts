import fs from "node:fs/promises";
import path from "node:path";
import type { RenderInput } from "@flow/schema";
import express, { type NextFunction, type Request, type Response } from "express";
import { config } from "./config";
import { renderAndAnalyze, warmUp } from "./renderer";

const app = express();
app.use(express.json({ limit: "10mb" }));

// Chromium haalt assets via deze route op; alleen-lezen. CORS is nodig voor fonts, omdat
// de Remotion-bundle op een andere poort draait.
app.use("/storage", (_req, res, next) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  next();
});
app.use("/storage", express.static(config.storageRoot, { fallthrough: false, dotfiles: "deny" }));

app.get("/health", (_req, res) => {
  res.json({ ok: true, licensed: Boolean(config.licenseKey) });
});

let active = 0;
const waiting: (() => void)[] = [];

async function withSlot<T>(task: () => Promise<T>): Promise<T> {
  if (active >= config.concurrency) await new Promise<void>((resolve) => waiting.push(resolve));
  active += 1;
  try {
    return await task();
  } finally {
    active -= 1;
    waiting.shift()?.();
  }
}

function resolveOutput(relative: string): string {
  const target = path.resolve(config.storageRoot, relative);
  if (!target.startsWith(config.storageRoot + path.sep)) throw new Error("output buiten storage");
  return target;
}

interface RenderBody {
  input: RenderInput;
  type: "jpeg" | "png";
  /** Pad relatief aan storage. Zonder output alleen analyse. */
  output?: string;
}

app.post("/render", async (req: Request<unknown, unknown, RenderBody>, res: Response) => {
  const { input, type = "jpeg", output } = req.body;
  if (!input?.format) {
    res.status(400).json({ error: "input.format ontbreekt" });
    return;
  }
  const started = Date.now();
  const result = await withSlot(() => renderAndAnalyze(input, type));
  if (output) {
    const target = resolveOutput(output);
    await fs.mkdir(path.dirname(target), { recursive: true });
    await fs.writeFile(target, result.image);
  }
  res.json({ report: result.report, bytes: result.image.length, output: output ?? null, ms: Date.now() - started });
});

app.use((error: Error, _req: Request, res: Response, _next: NextFunction) => {
  console.error(error);
  res.status(500).json({ error: error.message });
});

app.listen(config.port, () => {
  console.log(`render-service luistert op :${config.port}, storage ${config.storageRoot}`);
  if (!config.licenseKey) console.log("Geen REMOTION_LICENSE_KEY gezet: evaluatiemodus.");
  warmUp()
    .then(() => console.log("bundle en browser klaar"))
    .catch((error) => console.error("opwarmen mislukt", error));
});
