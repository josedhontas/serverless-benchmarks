// Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
const http = require("http");
const fs = require("fs");
const crypto = require("crypto");

async function invoke(payload) {
  const begin = Date.now() / 1000;
  const requestId = crypto.randomUUID();
  const func = require("/function/function.js");
  const ret = await func.handler(payload);
  const end = Date.now() / 1000;
  const coldFile = "/tmp/sebs-cold-run";
  let isCold = false;
  if (!fs.existsSync(coldFile)) {
    isCold = true;
    fs.closeSync(fs.openSync(coldFile, "w"));
  }
  return {
    begin,
    end,
    request_id: requestId,
    is_cold: isCold,
    result: ret,
  };
}

function writeJson(res, status, payload) {
  const encoded = Buffer.from(JSON.stringify(payload));
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": encoded.length,
  });
  res.end(encoded);
}

http
  .createServer((req, res) => {
    if (req.method === "GET" && req.url === "/alive") {
      writeJson(res, 200, { result: "ok" });
      return;
    }
    if (req.method !== "POST") {
      writeJson(res, 404, { error: "not found" });
      return;
    }

    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", async () => {
      try {
        const payload = JSON.parse(Buffer.concat(chunks).toString() || "{}");
        writeJson(res, 200, await invoke(payload));
      } catch (err) {
        const now = Date.now() / 1000;
        writeJson(res, 500, {
          begin: now,
          end: now,
          request_id: crypto.randomUUID(),
          result: `Error - invocation failed! Reason: ${err}`,
        });
      }
    });
  })
  .listen(8080, "0.0.0.0");
