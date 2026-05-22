# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
from os import environ
import os

import boto3


def _config_value(key):
    if key in environ:
        return environ[key]

    configs_dir = "/configs"
    if os.path.isdir(configs_dir):
        for root, _, files in os.walk(configs_dir):
            if key in files:
                with open(os.path.join(root, key), "r") as f:
                    return f.read().strip()
    return None


class nosql:
    @staticmethod
    def get_instance(table_name):
        if not hasattr(nosql, "instance"):
            storage_type = _config_value("NOSQL_STORAGE_TYPE")
            if storage_type != "scylladb":
                raise RuntimeError(f"Unsupported NoSQL storage type: {storage_type}!")
            nosql.instance = nosql()
        return nosql.instance.get_table(table_name)

    def __init__(self):
        self._client = boto3.resource(
            "dynamodb",
            endpoint_url=f"http://{_config_value('NOSQL_STORAGE_ENDPOINT')}",
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
        return _config_value(env_name) or table_name
