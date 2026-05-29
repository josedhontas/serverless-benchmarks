# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
"""Knative platform implementation for SeBS."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import uuid
from typing import Any, Dict, List, Optional, Type, cast

import docker

from sebs.benchmark import Benchmark
from sebs.cache import Cache
from sebs.config import SeBSConfig
from sebs.experiments.config import SystemVariant
from sebs.faas import System
from sebs.faas.config import Resources
from sebs.faas.function import ExecutionResult, Function, Trigger
from sebs.knative.config import KnativeConfig
from sebs.knative.container import KnativeContainer
from sebs.knative.function import KnativeFunction, KnativeFunctionConfig
from sebs.knative.triggers import HTTPTrigger
from sebs.sebs_types import Language
from sebs.storage.minio import Minio
from sebs.storage.resources import SelfHostedSystemResources
from sebs.storage.scylladb import ScyllaDB
from sebs.utils import LoggingHandlers


class Knative(System):
    _config: KnativeConfig

    def __init__(
        self,
        system_config: SeBSConfig,
        config: KnativeConfig,
        cache_client: Cache,
        docker_client: docker.client.DockerClient,
        logger_handlers: LoggingHandlers,
    ) -> None:
        super().__init__(
            system_config,
            cache_client,
            docker_client,
            SelfHostedSystemResources(
                "knative", config, cache_client, docker_client, logger_handlers
            ),
        )
        self._config = config
        self.logging_handlers = logger_handlers
        self._container_client = KnativeContainer(
            self.system_config,
            self.config,
            self.docker_client,
            self.config.experimentalManifest,
        )

        if self.config.resources.docker_username:
            self.docker_client.login(
                username=self.config.resources.docker_username,
                password=self.config.resources.docker_password,
                registry=self.config.resources.docker_registry,
            )

    @property
    def config(self) -> KnativeConfig:
        return self._config

    @property
    def container_client(self) -> KnativeContainer:
        return self._container_client

    @staticmethod
    def name() -> str:
        return "knative"

    @staticmethod
    def typename() -> str:
        return "Knative"

    @staticmethod
    def function_type() -> "Type[Function]":
        return KnativeFunction

    def initialize(
        self,
        config: Dict[str, str] = {},
        resource_prefix: Optional[str] = None,
        quiet: bool = False,
    ) -> None:
        if self.config.resources.storage_config is None:
            if not self.config.resources.has_resources_id:
                if resource_prefix is not None:
                    resource_id = f"{resource_prefix}-{str(uuid.uuid1())[0:8]}"
                else:
                    resource_id = str(uuid.uuid1())[0:8]
                self.config.resources.resources_id = resource_id
                if not quiet:
                    self.logging.info(
                        f"Generating unique resource name "
                        f"{self.config.resources.resources_id}"
                    )
            return

        self.initialize_resources(select_prefix=resource_prefix, quiet=quiet)

    def find_deployments(self) -> List[str]:
        if self.config.resources.storage_config is None:
            return []
        return super().find_deployments()

    def package_code(
        self,
        directory: str,
        language: Language,
        language_version: str,
        architecture: str,
        benchmark: str,
        is_cached: bool,
    ) -> tuple[str, float]:
        return directory, Benchmark.directory_size(directory)

    def _function_url(self, name: str) -> str:
        gateway = self.config.gateway.rstrip("/")
        return self.config.url_template.format(
            gateway=gateway,
            name=name,
            namespace=self.config.namespace,
        )

    def _function_host(self, name: str) -> str:
        if not self.config.host_template:
            return ""
        return self.config.host_template.format(
            gateway=self.config.gateway.rstrip("/"),
            name=name,
            namespace=self.config.namespace,
        )

    def _envs(self, code_package: Benchmark) -> Dict[str, str]:
        envs: Dict[str, str] = {}

        if self.config.resources.storage_config:
            envs.update(self.config.resources.storage_config.envs())

        if code_package.uses_nosql:
            nosql_storage = self.system_resources.get_nosql_storage()
            envs.update(nosql_storage.envs())
            for original_name, actual_name in nosql_storage.get_tables(
                code_package.benchmark
            ).items():
                envs[f"NOSQL_STORAGE_TABLE_{original_name}"] = actual_name

        return envs

    def _run_kubectl(
        self,
        args: List[str],
        input_data: Optional[bytes] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        try:
            cli_cmd = shlex.split(self.config.kubectl_cli, posix=os.name != "nt")
            return subprocess.run(
                [*cli_cmd, *args],
                input=input_data,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=check,
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                f"Could not execute kubectl CLI '{self.config.kubectl_cli}'."
            ) from e
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace")
            stdout = e.stdout.decode("utf-8", errors="replace")
            self.logging.error(f"kubectl failed: {stderr or stdout}")
            raise RuntimeError(e) from e

    def _service_manifest(
        self, function: KnativeFunction, code_package: Benchmark
    ) -> Dict[str, Any]:
        env = [
            {"name": key, "value": value}
            for key, value in sorted(self._envs(code_package).items())
        ]
        return {
            "apiVersion": "serving.knative.dev/v1",
            "kind": "Service",
            "metadata": {
                "name": function.name,
                "namespace": self.config.namespace,
            },
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "autoscaling.knative.dev/min-scale": "1",
                            "autoscaling.knative.dev/max-scale": "1",
                        }
                    },
                    "spec": {
                        "timeoutSeconds": code_package.benchmark_config.timeout,
                        "containers": [
                            {
                                "image": function.config.image,
                                "ports": [
                                    {
                                        "containerPort": self.config.service_port,
                                        "name": "http1",
                                    }
                                ],
                                "env": env,
                            }
                        ],
                    },
                }
            },
        }

    def _deploy(self, function: KnativeFunction, code_package: Benchmark) -> None:
        manifest = json.dumps(self._service_manifest(function, code_package)).encode(
            "utf-8"
        )
        self._run_kubectl(["apply", "-f", "-"], input_data=manifest)
        self._wait_service_ready(function.name, code_package.benchmark_config.timeout)

    def _wait_service_ready(self, function_name: str, timeout: int) -> None:
        wait_timeout = max(timeout, 180)
        result = self._run_kubectl(
            [
                "wait",
                "--for=condition=Ready",
                "ksvc",
                function_name,
                "--namespace",
                self.config.namespace,
                "--timeout",
                f"{wait_timeout}s",
            ],
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            stdout = result.stdout.decode("utf-8", errors="replace")
            self.logging.warning(
                f"Timed out waiting for Knative service {function_name}: "
                f"{stderr or stdout}"
            )

    def create_function(
        self,
        code_package: Benchmark,
        func_name: str,
        system_variant: SystemVariant,
        container_uri: str | None,
    ) -> KnativeFunction:
        if not system_variant.is_container:
            raise RuntimeError("Knative supports only container deployments in SeBS.")
        if container_uri is None:
            raise RuntimeError("Knative deployment requires a container image URI.")

        cfg = KnativeFunctionConfig.from_benchmark(code_package)
        cfg.image = container_uri
        cfg.gateway = self.config.gateway
        cfg.namespace = self.config.namespace
        if code_package.uses_storage:
            cfg.object_storage = cast(Minio, self.system_resources.get_storage()).config
        if code_package.uses_nosql:
            cfg.nosql_storage = cast(
                ScyllaDB, self.system_resources.get_nosql_storage()
            ).config

        function = KnativeFunction(
            func_name, code_package.benchmark, code_package.hash, cfg
        )
        self.logging.info(f"Deploying Knative service {func_name}.")
        self._deploy(function, code_package)
        trigger = HTTPTrigger(
            func_name, self._function_url(func_name), self._function_host(func_name)
        )
        trigger.logging_handlers = self.logging_handlers
        function.add_trigger(trigger)
        return function

    def update_function(
        self,
        function: Function,
        code_package: Benchmark,
        system_variant: SystemVariant,
        container_uri: str | None,
    ) -> None:
        if not system_variant.is_container:
            raise RuntimeError("Knative supports only container deployments in SeBS.")
        if container_uri is None:
            raise RuntimeError("Knative deployment requires a container image URI.")
        knative_function = cast(KnativeFunction, function)
        knative_function.config.image = container_uri
        self.logging.info(f"Updating Knative service {function.name}.")
        self._deploy(knative_function, code_package)

    def update_function_configuration(
        self, function: Function, code_package: Benchmark
    ) -> None:
        self.logging.info(f"Updating Knative service configuration {function.name}.")
        self._deploy(cast(KnativeFunction, function), code_package)

    def is_configuration_changed(
        self, cached_function: Function, benchmark: Benchmark
    ) -> bool:
        changed = super().is_configuration_changed(cached_function, benchmark)
        function = cast(KnativeFunction, cached_function)

        if function.config.gateway != self.config.gateway:
            function.config.gateway = self.config.gateway
            changed = True
        if function.config.namespace != self.config.namespace:
            function.config.namespace = self.config.namespace
            changed = True
        if benchmark.uses_storage:
            storage = cast(Minio, self.system_resources.get_storage())
            if function.config.object_storage != storage.config:
                function.config.object_storage = storage.config
                changed = True
        if benchmark.uses_nosql:
            nosql_storage = cast(ScyllaDB, self.system_resources.get_nosql_storage())
            if function.config.nosql_storage != nosql_storage.config:
                function.config.nosql_storage = nosql_storage.config
                changed = True
        return changed

    def cached_function(self, function: Function) -> None:
        func = cast(KnativeFunction, function)
        for trigger in func.triggers(Trigger.TriggerType.HTTP):
            http_trigger = cast(HTTPTrigger, trigger)
            http_trigger.url = self._function_url(func.name)
            http_trigger.host = self._function_host(func.name)
            http_trigger.logging_handlers = self.logging_handlers

    def create_trigger(
        self, function: Function, trigger_type: Trigger.TriggerType
    ) -> Trigger:
        if trigger_type != Trigger.TriggerType.HTTP:
            raise RuntimeError("Knative supports only HTTP triggers.")
        trigger = HTTPTrigger(
            function.name,
            self._function_url(function.name),
            self._function_host(function.name),
        )
        trigger.logging_handlers = self.logging_handlers
        function.add_trigger(trigger)
        self.cache_client.update_function(function)
        return trigger

    def download_metrics(
        self,
        function_name: str,
        start_time: int,
        end_time: int,
        requests: Dict[str, ExecutionResult],
        metrics: dict,
    ) -> None:
        pass

    def enforce_cold_start(
        self, functions: List[Function], code_package: Benchmark
    ) -> None:
        for function in functions:
            self.update_function_configuration(function, code_package)

    def default_function_name(
        self, code_package: Benchmark, resources: Optional[Resources] = None
    ) -> str:
        resource_id = (
            resources.resources_id if resources else self.config.resources.resources_id
        )
        raw = (
            f"sebs-{resource_id}-{code_package.benchmark}-"
            f"{code_package.language_name}-{code_package.language_version}"
        )
        return self.format_function_name(raw)

    @staticmethod
    def format_function_name(func_name: str) -> str:
        name = re.sub(r"[^a-z0-9-]", "-", func_name.lower())
        name = re.sub(r"-+", "-", name).strip("-")
        return name[:63]

    def delete_function(self, func_name: str, function: Dict) -> None:
        self._run_kubectl(
            [
                "delete",
                "ksvc",
                func_name,
                "--namespace",
                self.config.namespace,
                "--ignore-not-found",
            ],
            check=False,
        )

    def shutdown(self) -> None:
        if self.config.shutdownStorage:
            if hasattr(self, "storage"):
                self.storage.stop()
        super().shutdown()
