// Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
const Minio = require("minio");
const fs = require("fs");
const path = require("path");
const stream = require("stream");
const { v4: uuidv4 } = require("uuid");

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

  uniqueName(file) {
    const parsed = path.parse(file);
    const uuidName = uuidv4().split("-")[0];
    return path.join(parsed.dir, `${parsed.name}.${uuidName}${parsed.ext}`);
  }

  async download(bucket, key, filepath) {
    fs.mkdirSync(path.dirname(filepath), { recursive: true });
    await this.client.fGetObject(bucket, key, filepath);
  }

  upload(bucket, key, filepath) {
    const uniqueName = this.uniqueName(key);
    return [uniqueName, this.client.fPutObject(bucket, uniqueName, filepath)];
  }

  async downloadDirectory(bucket, prefix, downloadPath) {
    const objectStream = this.client.listObjects(bucket, prefix, true);
    const downloads = [];
    return await new Promise((resolve, reject) => {
      objectStream.on("data", (obj) => {
        const fileName = obj.name;
        const outputPath = path.join(downloadPath, fileName);
        fs.mkdirSync(path.dirname(outputPath), { recursive: true });
        downloads.push(this.client.fGetObject(bucket, fileName, outputPath));
      });
      objectStream.on("error", reject);
      objectStream.on("end", () => Promise.all(downloads).then(resolve).catch(reject));
    });
  }

  uploadStream(bucket, key) {
    const writeStream = new stream.PassThrough();
    const uniqueName = this.uniqueName(key);
    const promise = this.client.putObject(bucket, uniqueName, writeStream, writeStream.size);
    return [writeStream, promise, uniqueName];
  }

  downloadStream(bucket, key) {
    return this.client.getObject(bucket, key);
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
