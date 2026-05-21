# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
"""Fission function metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, cast

from sebs.benchmark import Benchmark
from sebs.faas.function import Function, FunctionConfig, Runtime, Trigger
from sebs.storage.config import MinioConfig, ScyllaDBConfig


@dataclass
class FissionFunctionConfig(FunctionConfig):
    image: str = ""
    router_url: str = ""
    namespace: str = ""
    function_port: int = 8080
    object_storage: Optional[MinioConfig] = None
    nosql_storage: Optional[ScyllaDBConfig] = None

    @staticmethod
    def from_benchmark(benchmark: Benchmark) -> "FissionFunctionConfig":
        return super(FissionFunctionConfig, FissionFunctionConfig)._from_benchmark(
            benchmark, FissionFunctionConfig
        )

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> "FissionFunctionConfig":
        keys = list(FissionFunctionConfig.__dataclass_fields__.keys())
        data = {k: v for k, v in data.items() if k in keys}
        data["runtime"] = Runtime.deserialize(data["runtime"])
        if data["object_storage"] is not None:
            data["object_storage"] = MinioConfig.deserialize(data["object_storage"])
        if data["nosql_storage"] is not None:
            data["nosql_storage"] = ScyllaDBConfig.deserialize(data["nosql_storage"])
        return FissionFunctionConfig(**data)

    def serialize(self) -> Dict[str, Any]:
        return self.__dict__


class FissionFunction(Function):
    def __init__(
        self,
        name: str,
        benchmark: str,
        code_package_hash: str,
        cfg: FissionFunctionConfig,
    ) -> None:
        super().__init__(benchmark, name, code_package_hash, cfg)

    @property
    def config(self) -> FissionFunctionConfig:
        return cast(FissionFunctionConfig, self._cfg)

    @staticmethod
    def typename() -> str:
        return "Fission.Function"

    def serialize(self) -> Dict[str, Any]:
        return {**super().serialize(), "config": self._cfg.serialize()}

    @staticmethod
    def deserialize(cached_config: Dict[str, Any]) -> "FissionFunction":
        from sebs.fission.triggers import HTTPTrigger

        cfg = FissionFunctionConfig.deserialize(cached_config["config"])
        ret = FissionFunction(
            cached_config["name"],
            cached_config["benchmark"],
            cached_config["hash"],
            cfg,
        )
        for trigger in cached_config["triggers"]:
            trigger_type = cast(Trigger, {"HTTP": HTTPTrigger}.get(trigger["type"]))
            assert trigger_type, "Unknown trigger type {}".format(trigger["type"])
            ret.add_trigger(trigger_type.deserialize(trigger))
        return ret
