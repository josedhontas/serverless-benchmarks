// Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
const AWS = require("aws-sdk");

class nosql {
  static get_instance(table_name) {
    if (process.env.NOSQL_STORAGE_TYPE !== "scylladb") {
      throw new Error(`Unsupported NoSQL storage type: ${process.env.NOSQL_STORAGE_TYPE}!`);
    }
    if (nosql.instance === undefined) {
      nosql.instance = new nosql();
    }
    return nosql.instance.get_table(table_name);
  }

  constructor() {
    this.client = new AWS.DynamoDB.DocumentClient({
      endpoint: `http://${process.env.NOSQL_STORAGE_ENDPOINT}`,
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
    if (env_name in process.env) {
      return process.env[env_name];
    }
    return table_name;
  }
}

module.exports = { nosql };
