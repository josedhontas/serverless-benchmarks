# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
"""Configuration for Fission deployments."""

from __future__ import annotations

from typing import Any, Dict, Optional, cast

from sebs.cache import Cache
from sebs.faas.config import Config, Credentials, Resources
from sebs.storage.resources import SelfHostedResources
from sebs.utils import LoggingHandlers


class FissionCredentials(Credentials):
    """Fission uses local Kubernetes and Fission CLI configuration."""

    @staticmethod
    def deserialize(
        config: Dict[str, Any], cache: Cache, handlers: LoggingHandlers
    ) -> Credentials:
        return FissionCredentials()

    def serialize(self) -> Dict[str, Any]:
        return {}


class FissionResources(SelfHostedResources):
    """Docker registry and self-hosted storage settings for Fission."""

    def __init__(
        self,
        registry: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        registry_updated: bool = False,
    ) -> None:
        super().__init__(name="fission")
        self._docker_registry = registry if registry != "" else None
        self._docker_username = username if username != "" else None
        self._docker_password = password if password != "" else None
        self._registry_updated = registry_updated

    @staticmethod
    def typename() -> str:
        return "Fission.Resources"

    @property
    def docker_registry(self) -> Optional[str]:
        return self._docker_registry

    @property
    def docker_username(self) -> Optional[str]:
        return self._docker_username

    @property
    def docker_password(self) -> Optional[str]:
        return self._docker_password

    @property
    def registry_updated(self) -> bool:
        return self._registry_updated

    @staticmethod
    def initialize(res: Resources, dct: Dict[str, Any]) -> None:
        ret = cast(FissionResources, res)
        if "registry" in dct:
            ret._docker_registry = dct["registry"] or None
        if "username" in dct:
            ret._docker_username = dct["username"] or None
        if "password" in dct:
            ret._docker_password = dct["password"] or None

    @staticmethod
    def deserialize(
        config: Dict[str, Any], cache: Cache, handlers: LoggingHandlers
    ) -> Resources:
        cached_config = cache.get_config("fission")
        ret = FissionResources()
        if cached_config:
            super(FissionResources, FissionResources).initialize(
                ret, cached_config["resources"]
            )

        ret._deserialize(ret, config, cached_config or {})
        ret.logging_handlers = handlers

        if "docker_registry" in config:
            FissionResources.initialize(ret, config["docker_registry"])
            ret.logging.info("Using user-provided Docker registry for Fission.")
            if not (
                cached_config
                and "resources" in cached_config
                and "docker" in cached_config["resources"]
                and cached_config["resources"]["docker"] == config["docker_registry"]
            ):
                ret._registry_updated = True
        elif (
            cached_config
            and "resources" in cached_config
            and "docker" in cached_config["resources"]
        ):
            FissionResources.initialize(ret, cached_config["resources"]["docker"])
            ret.logging.info("Using cached Docker registry for Fission.")
        else:
            ret.logging.info("Using default Docker registry for Fission.")
            ret._registry_updated = True

        return ret

    def update_cache(self, cache: Cache) -> None:
        super().update_cache(cache)
        cache.update_config(
            val=self.docker_registry,
            keys=["fission", "resources", "docker", "registry"],
        )
        cache.update_config(
            val=self.docker_username,
            keys=["fission", "resources", "docker", "username"],
        )
        cache.update_config(
            val=self.docker_password,
            keys=["fission", "resources", "docker", "password"],
        )

    def serialize(self) -> Dict[str, Any]:
        return {
            **super().serialize(),
            "docker_registry": self.docker_registry,
            "docker_username": self.docker_username,
            "docker_password": self.docker_password,
        }


class FissionConfig(Config):
    """Fission deployment settings."""

    fission_cli: str
    kubectl_cli: str
    router_url: str
    namespace: str
    dockerhub_repository: Optional[str]
    shutdownStorage: bool
    experimentalManifest: bool
    function_port: int

    def __init__(
        self,
        resources: FissionResources,
        credentials: FissionCredentials,
        cache: Cache,
    ) -> None:
        super().__init__(name="fission")
        self._resources = resources
        self._credentials = credentials
        self.cache = cache

    @property
    def credentials(self) -> FissionCredentials:
        return self._credentials

    @property
    def resources(self) -> FissionResources:
        return self._resources

    @staticmethod
    def initialize(cfg: Config, dct: Dict[str, Any]) -> None:
        config = cast(FissionConfig, cfg)
        config.router_url = dct.get("routerUrl", "http://127.0.0.1:8888")
        config.namespace = dct.get("namespace", "default")
        config.fission_cli = dct.get("fissionCli", "fission")
        config.kubectl_cli = dct.get("kubectlCli", "kubectl")
        config.shutdownStorage = dct.get("shutdownStorage", False)
        config.experimentalManifest = dct.get("experimentalManifest", False)
        config.dockerhub_repository = dct.get("dockerhubRepository")
        config.function_port = int(dct.get("functionPort", 8080))

    @staticmethod
    def deserialize(
        config: Dict[str, Any], cache: Cache, handlers: LoggingHandlers
    ) -> Config:
        resources = cast(
            FissionResources, FissionResources.deserialize(config, cache, handlers)
        )
        res = FissionConfig(resources, FissionCredentials(), cache)
        res.logging_handlers = handlers

        cached_config = cache.get_config("fission")
        if cached_config:
            res.logging.info("Loading cached config for Fission")
            FissionConfig.initialize(res, cached_config)
            FissionConfig.initialize(res, config)
        else:
            res.logging.info("Using user-provided config for Fission")
            FissionConfig.initialize(res, config)

        return res

    def serialize(self) -> Dict[str, Any]:
        return {
            "name": "fission",
            "routerUrl": self.router_url,
            "namespace": self.namespace,
            "fissionCli": self.fission_cli,
            "kubectlCli": self.kubectl_cli,
            "shutdownStorage": self.shutdownStorage,
            "experimentalManifest": self.experimentalManifest,
            "dockerhubRepository": self.dockerhub_repository,
            "functionPort": self.function_port,
            "credentials": self.credentials.serialize(),
            "resources": self.resources.serialize(),
        }

    def update_cache(self, cache: Cache) -> None:
        cache.update_config(val=self.router_url, keys=["fission", "routerUrl"])
        cache.update_config(val=self.namespace, keys=["fission", "namespace"])
        cache.update_config(val=self.fission_cli, keys=["fission", "fissionCli"])
        cache.update_config(val=self.kubectl_cli, keys=["fission", "kubectlCli"])
        cache.update_config(
            val=self.shutdownStorage, keys=["fission", "shutdownStorage"]
        )
        cache.update_config(
            val=self.experimentalManifest, keys=["fission", "experimentalManifest"]
        )
        cache.update_config(
            val=self.dockerhub_repository, keys=["fission", "dockerhubRepository"]
        )
        cache.update_config(val=self.function_port, keys=["fission", "functionPort"])
        self.resources.update_cache(cache)
