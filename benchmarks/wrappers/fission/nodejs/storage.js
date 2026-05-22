// Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
const Minio = require("minio");
const fs = require("fs");
const path = require("path");

function configValue(key) {
  if (key in process.env) {
    return process.env[key];
  }

  const configsDir = "/configs";
  if (!fs.existsSync(configsDir)) {
    return undefined;
  }

  const stack = [configsDir];
  while (stack.length > 0) {
    const current = stack.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const entryPath = path.join(current, entry.name);
      if (entry.isDirectory()) {
        stack.push(entryPath);
      } else if (entry.name === key) {
        return fs.readFileSync(entryPath, "utf8").trim();
      }
    }
  }
  return undefined;
}

class storage {
  static get_instance() {
    if (storage.instance === undefined) {
      let address = configValue("MINIO_ADDRESS");
      let access_key = configValue("MINIO_ACCESS_KEY");
      let secret_key = configValue("MINIO_SECRET_KEY");
      if (address === undefined || access_key === undefined || secret_key === undefined) {
        throw new Error("Could not create storage, no configuration found!");
      }
      storage.instance = new storage(address, access_key, secret_key);
    }
    return storage.instance;
  }

  constructor(address, access_key, secret_key) {
    let [endPoint, port] = address.split(":");
    this.client = new Minio.Client({
      endPoint,
      port: Number(port),
      useSSL: false,
      accessKey: access_key,
      secretKey: secret_key,
    });
  }

  async download(bucket, key, filepath) {
    await this.client.fGetObject(bucket, key, filepath);
  }

  async upload(bucket, key, filepath) {
    await this.client.fPutObject(bucket, key, filepath);
  }

  async list_keys(bucket) {
    const objects = [];
    const stream = this.client.listObjects(bucket, "", true);
    return await new Promise((resolve, reject) => {
      stream.on("data", (obj) => objects.push(obj.name));
      stream.on("error", reject);
      stream.on("end", () => resolve(objects));
    });
  }
}

module.exports = { storage };
