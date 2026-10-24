// Minimale storage-server voor de smoketest (de echte service serveert /storage zelf).
import express from "express";
import { config } from "../src/config";

express()
  .use("/storage", (_req, res, next) => {
    res.setHeader("Access-Control-Allow-Origin", "*");
    next();
  })
  .use("/storage", express.static(config.storageRoot))
  .listen(config.port);
