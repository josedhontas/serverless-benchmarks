// Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
const Minio = require("minio");

class storage {
  static get_instance() {
    if (storage.instance === undefined) {
      let address = process.env.MINIO_ADDRESS;
      let access_key = process.env.MINIO_ACCESS_KEY;
      let secret_key = process.env.MINIO_SECRET_KEY;
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
