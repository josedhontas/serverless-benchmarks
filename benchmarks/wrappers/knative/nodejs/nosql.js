// Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
const AWS = require("aws-sdk");
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

class nosql {
  static get_instance(table_name) {
    const storageType = configValue("NOSQL_STORAGE_TYPE");
    if (storageType !== "scylladb") {
      throw new Error(`Unsupported NoSQL storage type: ${storageType}!`);
    }
    if (nosql.instance === undefined) {
      nosql.instance = new nosql();
    }
    return nosql.instance.get_table(table_name);
  }

  constructor() {
    this.client = new AWS.DynamoDB.DocumentClient({
      endpoint: `http://${configValue("NOSQL_STORAGE_ENDPOINT")}`,
      region: "None",
      accessKeyId: "None",
      secretAccessKey: "None",
    });
    this._tables = {};
  }

  get_table(table_name) {
    if (!(table_name in this._tables)) {
      this._tables[table_name] = this._table_name(table_name);
    }
    return this._tables[table_name];
  }

  _table_name(table_name) {
    const env_name = `NOSQL_STORAGE_TABLE_${table_name}`;
    return configValue(env_name) || table_name;
  }
}

module.exports = { nosql };
