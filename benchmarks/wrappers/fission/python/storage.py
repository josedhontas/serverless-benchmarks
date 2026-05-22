# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
import io
import os
import uuid

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

    @staticmethod
    def unique_name(name):
        name, extension = os.path.splitext(name)
        return "{name}.{random}{extension}".format(
            name=name, extension=extension, random=str(uuid.uuid4()).split("-")[0]
        )

    def download(self, bucket, key, filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        self.client.fget_object(bucket, key, filepath)

    def upload(self, bucket, key, filepath):
        key_name = storage.unique_name(key)
        self.client.fput_object(bucket, key_name, filepath)
        return key_name

    def download_directory(self, bucket, prefix, path):
        objects = self.client.list_objects(bucket, prefix=prefix, recursive=True)
        for obj in objects:
            file_name = obj.object_name
            self.download(bucket, file_name, os.path.join(path, file_name))

    def upload_stream(self, bucket, key, bytes_data):
        key_name = storage.unique_name(key)
        if isinstance(bytes_data, bytes):
            bytes_data = io.BytesIO(bytes_data)
        self.client.put_object(
            bucket, key_name, bytes_data, bytes_data.getbuffer().nbytes
        )
        return key_name

    def download_stream(self, bucket, key):
        data = self.client.get_object(bucket, key)
        return data.read()

    def list_keys(self, bucket):
        return [obj.object_name for obj in self.client.list_objects(bucket)]
