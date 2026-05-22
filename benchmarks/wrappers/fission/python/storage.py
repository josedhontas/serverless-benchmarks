# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
import os
import minio


def _config_value(key):
    if key in os.environ:
        return os.environ[key]

    configs_dir = "/configs"
    if os.path.isdir(configs_dir):
        for root, _, files in os.walk(configs_dir):
            if key in files:
                with open(os.path.join(root, key), "r") as f:
                    return f.read().strip()
    return None


class storage:
    @staticmethod
    def get_instance():
        if not hasattr(storage, "instance"):
            address = _config_value("MINIO_ADDRESS")
            access_key = _config_value("MINIO_ACCESS_KEY")
            secret_key = _config_value("MINIO_SECRET_KEY")
            if address and access_key and secret_key:
                storage.instance = storage(address, access_key, secret_key)
            else:
                raise RuntimeError("Could not create storage, no configuration found!")
        return storage.instance

    def __init__(self, address, access_key, secret_key):
        self.client = minio.Minio(
            address,
            access_key=access_key,
            secret_key=secret_key,
            secure=False,
        )

    def download(self, bucket, key, filepath):
        return self.client.fget_object(bucket, key, filepath)

    def upload(self, bucket, key, filepath):
        self.client.fput_object(bucket, key, filepath)

    def list_keys(self, bucket):
        return [obj.object_name for obj in self.client.list_objects(bucket)]
