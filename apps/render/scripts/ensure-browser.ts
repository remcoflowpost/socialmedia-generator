// Downloadt Chrome Headless Shell tijdens de Docker-build, zodat de eerste render niet wacht.
import { ensureBrowser } from "@remotion/renderer";

await ensureBrowser({ logLevel: "info" });
console.log("Chrome Headless Shell aanwezig.");
