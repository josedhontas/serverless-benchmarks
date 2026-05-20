# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
"""OpenFaaS platform implementation for SeBS."""

from __future__ import annotations

import re
import shlex
import subprocess
import uuid
import os
from typing import Dict, List, Optional, Type, cast

import docker

from sebs.benchmark import Benchmark
from sebs.cache import Cache
from sebs.experiments.config import SystemVariant
from sebs.faas import System
from sebs.faas.config import Resources
from sebs.faas.function import ExecutionResult, Function, Trigger
from sebs.openfaas.config import OpenFaaSConfig
from sebs.openfaas.container import OpenFaaSContainer
from sebs.openfaas.function import OpenFaaSFunction, OpenFaaSFunctionConfig
from sebs.openfaas.triggers import HTTPTrigger
from sebs.sebs_types import Language
from sebs.storage.minio import Minio
from sebs.storage.resources import SelfHostedSystemResources
from sebs.storage.scylladb import ScyllaDB
from sebs.utils import LoggingHandlers
from sebs.config import SeBSConfig


class OpenFaaS(System):
    _config: OpenFaaSConfig

    def __init__(
        self,
        system_config: SeBSConfig,
        config: OpenFaaSConfig,
        cache_client: Cache,
        docker_client: docker.client.DockerClient,
        logger_handlers: LoggingHandlers,
    ) -> None:
        super().__init__(
            system_config,
            cache_client,
            docker_client,
            SelfHostedSystemResources(
                "openfaas", config, cache_client, docker_client, logger_handlers
            ),
        )
        self._config = config
        self.logging_handlers = logger_handlers
        self._container_client = OpenFaaSContainer(
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
    def config(self) -> OpenFaaSConfig:
        return self._config

    @property
    def container_client(self) -> OpenFaaSContainer:
        return self._container_client

    @staticmethod
    def name() -> str:
        return "openfaas"

    @staticmethod
    def typename() -> str:
        return "OpenFaaS"

    @staticmethod
    def function_type() -> "Type[Function]":
        return OpenFaaSFunction

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
        return f"{gateway}/function/{name}"

    def _env_arguments(self, code_package: Benchmark) -> List[str]:
        args: List[str] = []

        if self.config.resources.storage_config:
            for key, value in self.config.resources.storage_config.envs().items():
                args.extend(["--env", f"{key}={value}"])

        if code_package.uses_nosql:
            nosql_storage = self.system_resources.get_nosql_storage()
            for key, value in nosql_storage.envs().items():
                args.extend(["--env", f"{key}={value}"])
            for original_name, actual_name in nosql_storage.get_tables(
                code_package.benchmark
            ).items():
                args.extend(
                    ["--env", f"NOSQL_STORAGE_TABLE_{original_name}={actual_name}"]
                )

        return args

    def _run_faas_cli(self, args: List[str]) -> subprocess.CompletedProcess:
        try:
            cli_cmd = shlex.split(self.config.faas_cli, posix=os.name != "nt")
            return subprocess.run(
                [*cli_cmd, *args],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except FileNotFoundError as e:
            raise RuntimeError(
                f"Could not execute OpenFaaS CLI '{self.config.faas_cli}'."
            ) from e
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace")
            stdout = e.stdout.decode("utf-8", errors="replace")
            self.logging.error(f"faas-cli failed: {stderr or stdout}")
            raise RuntimeError(e) from e

    def _deploy(self, function: OpenFaaSFunction, code_package: Benchmark) -> None:
        args = [
            "deploy",
            "--name",
            function.name,
            "--image",
            function.config.image,
            "--gateway",
            self.config.gateway,
            "--namespace",
            self.config.namespace,
            "--annotation",
            "com.openfaas.health.http.path=/alive",
            "--env",
            "write_debug=false",
            "--env",
            f"read_timeout={code_package.benchmark_config.timeout}s",
            "--env",
            f"write_timeout={code_package.benchmark_config.timeout}s",
            *self._env_arguments(code_package),
        ]
        self._run_faas_cli(args)

    def create_function(
        self,
        code_package: Benchmark,
        func_name: str,
        system_variant: SystemVariant,
        container_uri: str | None,
    ) -> OpenFaaSFunction:
        if not system_variant.is_container:
            raise RuntimeError("OpenFaaS supports only container deployments in SeBS.")
        if container_uri is None:
            raise RuntimeError("OpenFaaS deployment requires a container image URI.")

        cfg = OpenFaaSFunctionConfig.from_benchmark(code_package)
        cfg.image = container_uri
        cfg.gateway = self.config.gateway
        cfg.namespace = self.config.namespace
        if code_package.uses_storage:
            cfg.object_storage = cast(Minio, self.system_resources.get_storage()).config
        if code_package.uses_nosql:
            cfg.nosql_storage = cast(
                ScyllaDB, self.system_resources.get_nosql_storage()
            ).config

        function = OpenFaaSFunction(
            func_name, code_package.benchmark, code_package.hash, cfg
        )
        self.logging.info(f"Deploying OpenFaaS function {func_name}.")
        self._deploy(function, code_package)
        trigger = HTTPTrigger(func_name, self._function_url(func_name))
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
            raise RuntimeError("OpenFaaS supports only container deployments in SeBS.")
        if container_uri is None:
            raise RuntimeError("OpenFaaS deployment requires a container image URI.")
        openfaas_function = cast(OpenFaaSFunction, function)
        openfaas_function.config.image = container_uri
        self.logging.info(f"Updating OpenFaaS function {function.name}.")
        self._deploy(openfaas_function, code_package)

    def update_function_configuration(
        self, function: Function, code_package: Benchmark
    ) -> None:
        self.logging.info(f"Updating OpenFaaS function configuration {function.name}.")
        self._deploy(cast(OpenFaaSFunction, function), code_package)

    def is_configuration_changed(
        self, cached_function: Function, benchmark: Benchmark
    ) -> bool:
        changed = super().is_configuration_changed(cached_function, benchmark)
        function = cast(OpenFaaSFunction, cached_function)

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
        func = cast(OpenFaaSFunction, function)
        for trigger in func.triggers(Trigger.TriggerType.HTTP):
            http_trigger = cast(HTTPTrigger, trigger)
            http_trigger.url = self._function_url(func.name)
            http_trigger.logging_handlers = self.logging_handlers

    def create_trigger(
        self, function: Function, trigger_type: Trigger.TriggerType
    ) -> Trigger:
        if trigger_type != Trigger.TriggerType.HTTP:
            raise RuntimeError("OpenFaaS supports only HTTP triggers.")
        trigger = HTTPTrigger(function.name, self._function_url(function.name))
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
        self._run_faas_cli(
            [
                "remove",
                "--name",
                func_name,
                "--gateway",
                self.config.gateway,
                "--namespace",
                self.config.namespace,
            ]
        )

    def shutdown(self) -> None:
        if self.config.shutdownStorage:
            if hasattr(self, "storage"):
                self.storage.stop()
        super().shutdown()
