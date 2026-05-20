# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
"""Configuration for OpenFaaS deployments."""

from __future__ import annotations

from typing import Any, Dict, Optional, cast

from sebs.cache import Cache
from sebs.faas.config import Config, Credentials, Resources
from sebs.storage.resources import SelfHostedResources
from sebs.utils import LoggingHandlers


class OpenFaaSCredentials(Credentials):
    """OpenFaaS uses ``faas-cli`` configuration for authentication."""

    @staticmethod
    def deserialize(
        config: Dict[str, Any], cache: Cache, handlers: LoggingHandlers
    ) -> Credentials:
        return OpenFaaSCredentials()

    def serialize(self) -> Dict[str, Any]:
        return {}


class OpenFaaSResources(SelfHostedResources):
    """Docker registry and self-hosted storage settings for OpenFaaS."""

    def __init__(
        self,
        registry: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        registry_updated: bool = False,
    ) -> None:
        super().__init__(name="openfaas")
        self._docker_registry = registry if registry != "" else None
        self._docker_username = username if username != "" else None
        self._docker_password = password if password != "" else None
        self._registry_updated = registry_updated

    @staticmethod
    def typename() -> str:
        return "OpenFaaS.Resources"

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
        ret = cast(OpenFaaSResources, res)
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
        cached_config = cache.get_config("openfaas")
        ret = OpenFaaSResources()
        if cached_config:
            super(OpenFaaSResources, OpenFaaSResources).initialize(
                ret, cached_config["resources"]
            )

        ret._deserialize(ret, config, cached_config or {})
        ret.logging_handlers = handlers

        if "docker_registry" in config:
            OpenFaaSResources.initialize(ret, config["docker_registry"])
            ret.logging.info("Using user-provided Docker registry for OpenFaaS.")
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
            OpenFaaSResources.initialize(ret, cached_config["resources"]["docker"])
            ret.logging.info("Using cached Docker registry for OpenFaaS.")
        else:
            ret.logging.info("Using default Docker registry for OpenFaaS.")
            ret._registry_updated = True

        return ret

    def update_cache(self, cache: Cache) -> None:
        super().update_cache(cache)
        cache.update_config(
            val=self.docker_registry,
            keys=["openfaas", "resources", "docker", "registry"],
        )
        cache.update_config(
            val=self.docker_username,
            keys=["openfaas", "resources", "docker", "username"],
        )
        cache.update_config(
            val=self.docker_password,
            keys=["openfaas", "resources", "docker", "password"],
        )

    def serialize(self) -> Dict[str, Any]:
        return {
            **super().serialize(),
            "docker_registry": self.docker_registry,
            "docker_username": self.docker_username,
            "docker_password": self.docker_password,
        }


class OpenFaaSConfig(Config):
    """OpenFaaS deployment settings."""

    faas_cli: str
    gateway: str
    namespace: str
    dockerhub_repository: Optional[str]
    shutdownStorage: bool
    experimentalManifest: bool

    def __init__(
        self,
        resources: OpenFaaSResources,
        credentials: OpenFaaSCredentials,
        cache: Cache,
    ) -> None:
        super().__init__(name="openfaas")
        self._resources = resources
        self._credentials = credentials
        self.cache = cache

    @property
    def credentials(self) -> OpenFaaSCredentials:
        return self._credentials

    @property
    def resources(self) -> OpenFaaSResources:
        return self._resources

    @staticmethod
    def initialize(cfg: Config, dct: Dict[str, Any]) -> None:
        config = cast(OpenFaaSConfig, cfg)
        config.gateway = dct.get("gateway", "http://127.0.0.1:8080")
        config.namespace = dct.get("namespace", "openfaas-fn")
        config.faas_cli = dct.get("faasCli", "faas-cli")
        config.shutdownStorage = dct.get("shutdownStorage", False)
        config.experimentalManifest = dct.get("experimentalManifest", False)
        config.dockerhub_repository = dct.get("dockerhubRepository")

    @staticmethod
    def deserialize(
        config: Dict[str, Any], cache: Cache, handlers: LoggingHandlers
    ) -> Config:
        resources = cast(
            OpenFaaSResources, OpenFaaSResources.deserialize(config, cache, handlers)
        )
        res = OpenFaaSConfig(resources, OpenFaaSCredentials(), cache)
        res.logging_handlers = handlers

        cached_config = cache.get_config("openfaas")
        if cached_config:
            res.logging.info("Loading cached config for OpenFaaS")
            OpenFaaSConfig.initialize(res, cached_config)
            OpenFaaSConfig.initialize(res, config)
        else:
            res.logging.info("Using user-provided config for OpenFaaS")
            OpenFaaSConfig.initialize(res, config)

        return res

    def serialize(self) -> Dict[str, Any]:
        return {
            "name": "openfaas",
            "gateway": self.gateway,
            "namespace": self.namespace,
            "faasCli": self.faas_cli,
            "shutdownStorage": self.shutdownStorage,
            "experimentalManifest": self.experimentalManifest,
            "dockerhubRepository": self.dockerhub_repository,
            "credentials": self.credentials.serialize(),
            "resources": self.resources.serialize(),
        }

    def update_cache(self, cache: Cache) -> None:
        cache.update_config(val=self.gateway, keys=["openfaas", "gateway"])
        cache.update_config(val=self.namespace, keys=["openfaas", "namespace"])
        cache.update_config(val=self.faas_cli, keys=["openfaas", "faasCli"])
        cache.update_config(
            val=self.shutdownStorage, keys=["openfaas", "shutdownStorage"]
        )
        cache.update_config(
            val=self.experimentalManifest, keys=["openfaas", "experimentalManifest"]
        )
        cache.update_config(
            val=self.dockerhub_repository, keys=["openfaas", "dockerhubRepository"]
        )
        self.resources.update_cache(cache)
