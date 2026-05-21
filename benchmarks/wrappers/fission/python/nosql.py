# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
from os import environ

import boto3


class nosql:
    @staticmethod
    def get_instance(table_name):
        if not hasattr(nosql, "instance"):
            if environ["NOSQL_STORAGE_TYPE"] != "scylladb":
                raise RuntimeError(
                    f"Unsupported NoSQL storage type: {environ['NOSQL_STORAGE_TYPE']}!"
                )
            nosql.instance = nosql()
        return nosql.instance.get_table(table_name)

    def __init__(self):
        self._client = boto3.resource(
            "dynamodb",
            endpoint_url=f"http://{environ['NOSQL_STORAGE_ENDPOINT']}",
            region_name="None",
            aws_access_key_id="None",
            aws_secret_access_key="None",
        )
        self._tables = {}

    def get_table(self, table_name):
        if table_name not in self._tables:
            self._tables[table_name] = self._client.Table(self._table_name(table_name))
        return self._tables[table_name]

    def _table_name(self, table_name):
        env_name = f"NOSQL_STORAGE_TABLE_{table_name}"
        return environ.get(env_name, table_name)
