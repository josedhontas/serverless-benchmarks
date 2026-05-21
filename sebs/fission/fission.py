# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
"""Fission platform implementation for SeBS."""

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
from sebs.fission.config import FissionConfig
from sebs.fission.container import FissionContainer
from sebs.fission.function import FissionFunction, FissionFunctionConfig
from sebs.fission.triggers import HTTPTrigger
from sebs.sebs_types import Language
from sebs.storage.minio import Minio
from sebs.storage.resources import SelfHostedSystemResources
from sebs.storage.scylladb import ScyllaDB
from sebs.utils import LoggingHandlers


class Fission(System):
    _config: FissionConfig

    def __init__(
        self,
        system_config: SeBSConfig,
        config: FissionConfig,
        cache_client: Cache,
        docker_client: docker.client.DockerClient,
        logger_handlers: LoggingHandlers,
    ) -> None:
        super().__init__(
            system_config,
            cache_client,
            docker_client,
            SelfHostedSystemResources(
                "fission", config, cache_client, docker_client, logger_handlers
            ),
        )
        self._config = config
        self.logging_handlers = logger_handlers
        self._container_client = FissionContainer(
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
    def config(self) -> FissionConfig:
        return self._config

    @property
    def container_client(self) -> FissionContainer:
        return self._container_client

    @staticmethod
    def name() -> str:
        return "fission"

    @staticmethod
    def typename() -> str:
        return "Fission"

    @staticmethod
    def function_type() -> "Type[Function]":
        return FissionFunction

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
        router_url = self.config.router_url.rstrip("/")
        return f"{router_url}/{name}"

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

    def _run_command(
        self,
        cli: str,
        args: List[str],
        input_data: Optional[bytes] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        try:
            cli_cmd = shlex.split(cli, posix=os.name != "nt")
            return subprocess.run(
                [*cli_cmd, *args],
                input=input_data,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=check,
            )
        except FileNotFoundError as e:
            raise RuntimeError(f"Could not execute CLI '{cli}'.") from e
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode("utf-8", errors="replace")
            stdout = e.stdout.decode("utf-8", errors="replace")
            self.logging.error(f"CLI command failed: {stderr or stdout}")
            raise RuntimeError(e) from e

    def _run_fission_cli(
        self, args: List[str], check: bool = True
    ) -> subprocess.CompletedProcess:
        return self._run_command(self.config.fission_cli, args, check=check)

    def _run_kubectl(
        self,
        args: List[str],
        input_data: Optional[bytes] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        return self._run_command(
            self.config.kubectl_cli, args, input_data=input_data, check=check
        )

    def _function_manifest(
        self, function: FissionFunction, code_package: Benchmark
    ) -> Dict[str, Any]:
        env = [
            {"name": key, "value": value}
            for key, value in sorted(self._envs(code_package).items())
        ]
        return {
            "apiVersion": "fission.io/v1",
            "kind": "Function",
            "metadata": {
                "name": function.name,
                "namespace": self.config.namespace,
            },
            "spec": {
                "InvokeStrategy": {
                    "ExecutionStrategy": {
                        "ExecutorType": "container",
                        "MaxScale": 1,
                        "MinScale": 1,
                        "SpecializationTimeout": 120,
                        "TargetCPUPercent": 80,
                    },
                    "StrategyType": "execution",
                },
                "environment": {"name": "", "namespace": ""},
                "functionTimeout": code_package.benchmark_config.timeout,
                "idletimeout": 120,
                "package": {"packageref": {"name": "", "namespace": ""}},
                "podspec": {
                    "containers": [
                        {
                            "image": function.config.image,
                            "name": function.name,
                            "ports": [
                                {
                                    "containerPort": self.config.function_port,
                                    "name": "http-env",
                                }
                            ],
                            "env": env,
                            "resources": {},
                        }
                    ]
                },
                "resources": {},
            },
        }

    def _apply_function(
        self, function: FissionFunction, code_package: Benchmark
    ) -> None:
        envs = self._envs(code_package)
        if envs:
            manifest = self._function_manifest(function, code_package)
            payload = json.dumps(manifest).encode("utf-8")
            self._run_kubectl(["apply", "-f", "-"], input_data=payload)
            return

        get_result = self._run_fission_cli(
            [
                "function",
                "get",
                "--name",
                function.name,
                "--namespace",
                self.config.namespace,
            ],
            check=False,
        )
        if get_result.returncode == 0:
            args = [
                "function",
                "update-container",
                "--name",
                function.name,
                "--image",
                function.config.image,
                "--port",
                str(self.config.function_port),
                "--namespace",
                self.config.namespace,
            ]
        else:
            args = [
                "function",
                "run-container",
                "--name",
                function.name,
                "--image",
                function.config.image,
                "--port",
                str(self.config.function_port),
                "--namespace",
                self.config.namespace,
            ]
        self._run_fission_cli(args)

    def _route_path(self, function_name: str) -> str:
        return f"/{function_name}"

    def _apply_route(self, function_name: str) -> None:
        self._run_fission_cli(
            [
                "httptrigger",
                "delete",
                "--name",
                function_name,
                "--namespace",
                self.config.namespace,
            ],
            check=False,
        )
        self._run_fission_cli(
            [
                "httptrigger",
                "create",
                "--name",
                function_name,
                "--function",
                function_name,
                "--url",
                self._route_path(function_name),
                "--method",
                "POST",
                "--namespace",
                self.config.namespace,
            ]
        )

    def _wait_function_ready(self, function_name: str, timeout: int) -> None:
        wait_timeout = max(timeout, 180)
        result = self._run_kubectl(
            [
                "wait",
                "--for=condition=ready",
                "pod",
                "-l",
                f"functionName={function_name}",
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
                f"Timed out waiting for Fission function pod {function_name}: "
                f"{stderr or stdout}"
            )

    def _deploy(self, function: FissionFunction, code_package: Benchmark) -> None:
        self._apply_function(function, code_package)
        self._apply_route(function.name)
        self._wait_function_ready(function.name, code_package.benchmark_config.timeout)

    def create_function(
        self,
        code_package: Benchmark,
        func_name: str,
        system_variant: SystemVariant,
        container_uri: str | None,
    ) -> FissionFunction:
        if not system_variant.is_container:
            raise RuntimeError("Fission supports only container deployments in SeBS.")
        if container_uri is None:
            raise RuntimeError("Fission deployment requires a container image URI.")

        cfg = FissionFunctionConfig.from_benchmark(code_package)
        cfg.image = container_uri
        cfg.router_url = self.config.router_url
        cfg.namespace = self.config.namespace
        cfg.function_port = self.config.function_port
        if code_package.uses_storage:
            cfg.object_storage = cast(Minio, self.system_resources.get_storage()).config
        if code_package.uses_nosql:
            cfg.nosql_storage = cast(
                ScyllaDB, self.system_resources.get_nosql_storage()
            ).config

        function = FissionFunction(
            func_name, code_package.benchmark, code_package.hash, cfg
        )
        self.logging.info(f"Deploying Fission function {func_name}.")
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
            raise RuntimeError("Fission supports only container deployments in SeBS.")
        if container_uri is None:
            raise RuntimeError("Fission deployment requires a container image URI.")
        fission_function = cast(FissionFunction, function)
        fission_function.config.image = container_uri
        self.logging.info(f"Updating Fission function {function.name}.")
        self._deploy(fission_function, code_package)

    def update_function_configuration(
        self, function: Function, code_package: Benchmark
    ) -> None:
        self.logging.info(f"Updating Fission function configuration {function.name}.")
        self._deploy(cast(FissionFunction, function), code_package)

    def is_configuration_changed(
        self, cached_function: Function, benchmark: Benchmark
    ) -> bool:
        changed = super().is_configuration_changed(cached_function, benchmark)
        function = cast(FissionFunction, cached_function)

        if function.config.router_url != self.config.router_url:
            function.config.router_url = self.config.router_url
            changed = True
        if function.config.namespace != self.config.namespace:
            function.config.namespace = self.config.namespace
            changed = True
        if function.config.function_port != self.config.function_port:
            function.config.function_port = self.config.function_port
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
        func = cast(FissionFunction, function)
        for trigger in func.triggers(Trigger.TriggerType.HTTP):
            http_trigger = cast(HTTPTrigger, trigger)
            http_trigger.url = self._function_url(func.name)
            http_trigger.logging_handlers = self.logging_handlers

    def create_trigger(
        self, function: Function, trigger_type: Trigger.TriggerType
    ) -> Trigger:
        if trigger_type != Trigger.TriggerType.HTTP:
            raise RuntimeError("Fission supports only HTTP triggers.")
        self._apply_route(function.name)
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
        self._run_fission_cli(
            [
                "httptrigger",
                "delete",
                "--name",
                func_name,
                "--namespace",
                self.config.namespace,
            ],
            check=False,
        )
        self._run_fission_cli(
            [
                "function",
                "delete",
                "--name",
                func_name,
                "--namespace",
                self.config.namespace,
            ],
            check=False,
        )

    def shutdown(self) -> None:
        if self.config.shutdownStorage:
            if hasattr(self, "storage"):
                self.storage.stop()
        super().shutdown()
