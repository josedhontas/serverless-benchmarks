# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
import os
import minio


class storage:
    @staticmethod
    def get_instance():
        if not hasattr(storage, "instance"):
            if "MINIO_ADDRESS" in os.environ:
                address = os.environ["MINIO_ADDRESS"]
                access_key = os.environ["MINIO_ACCESS_KEY"]
                secret_key = os.environ["MINIO_SECRET_KEY"]
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
