import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "../../..");

export const config = {
  port: Number(process.env.RENDER_PORT ?? 3001),
  storageRoot: path.resolve(process.env.STORAGE_ROOT ?? path.join(repoRoot, "data/storage")),
  entryPoint: path.join(repoRoot, "packages/compositions/src/remotion/index.ts"),
  /** Leeg laten om Remotion zijn eigen chrome-headless-shell te laten gebruiken. */
  browserExecutable: process.env.REMOTION_BROWSER_EXECUTABLE || null,
  /** Remotion Company License (Automators). Leeg = evaluatie, niets wordt geteld. */
  licenseKey: process.env.REMOTION_LICENSE_KEY || null,
  isProduction: process.env.NODE_ENV === "production",
  concurrency: Number(process.env.RENDER_CONCURRENCY ?? 2),
};
