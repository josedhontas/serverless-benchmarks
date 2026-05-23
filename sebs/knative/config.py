# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
"""Configuration for Knative deployments."""

from __future__ import annotations

from typing import Any, Dict, Optional, cast

from sebs.cache import Cache
from sebs.faas.config import Config, Credentials, Resources
from sebs.storage.resources import SelfHostedResources
from sebs.utils import LoggingHandlers


class KnativeCredentials(Credentials):
    """Knative uses the active ``kubectl`` context for authentication."""

    @staticmethod
    def deserialize(
        config: Dict[str, Any], cache: Cache, handlers: LoggingHandlers
    ) -> Credentials:
        return KnativeCredentials()

    def serialize(self) -> Dict[str, Any]:
        return {}


class KnativeResources(SelfHostedResources):
    """Docker registry and self-hosted storage settings for Knative."""

    def __init__(
        self,
        registry: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        registry_updated: bool = False,
    ) -> None:
        super().__init__(name="knative")
        self._docker_registry = registry if registry != "" else None
        self._docker_username = username if username != "" else None
        self._docker_password = password if password != "" else None
        self._registry_updated = registry_updated

    @staticmethod
    def typename() -> str:
        return "Knative.Resources"

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
        ret = cast(KnativeResources, res)
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
        cached_config = cache.get_config("knative")
        ret = KnativeResources()
        if cached_config:
            super(KnativeResources, KnativeResources).initialize(
                ret, cached_config["resources"]
            )

        ret._deserialize(ret, config, cached_config or {})
        ret.logging_handlers = handlers

        if "docker_registry" in config:
            KnativeResources.initialize(ret, config["docker_registry"])
            ret.logging.info("Using user-provided Docker registry for Knative.")
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
            KnativeResources.initialize(ret, cached_config["resources"]["docker"])
            ret.logging.info("Using cached Docker registry for Knative.")
        else:
            ret.logging.info("Using default Docker registry for Knative.")
            ret._registry_updated = True

        return ret

    def update_cache(self, cache: Cache) -> None:
        super().update_cache(cache)
        cache.update_config(
            val=self.docker_registry,
            keys=["knative", "resources", "docker", "registry"],
        )
        cache.update_config(
            val=self.docker_username,
            keys=["knative", "resources", "docker", "username"],
        )
        cache.update_config(
            val=self.docker_password,
            keys=["knative", "resources", "docker", "password"],
        )

    def serialize(self) -> Dict[str, Any]:
        return {
            **super().serialize(),
            "docker_registry": self.docker_registry,
            "docker_username": self.docker_username,
            "docker_password": self.docker_password,
        }


class KnativeConfig(Config):
    """Knative deployment settings."""

    gateway: str
    url_template: str
    host_template: str
    namespace: str
    kubectl_cli: str
    service_port: int
    dockerhub_repository: Optional[str]
    shutdownStorage: bool
    experimentalManifest: bool

    def __init__(
        self,
        resources: KnativeResources,
        credentials: KnativeCredentials,
        cache: Cache,
    ) -> None:
        super().__init__(name="knative")
        self._resources = resources
        self._credentials = credentials
        self.cache = cache

    @property
    def credentials(self) -> KnativeCredentials:
        return self._credentials

    @property
    def resources(self) -> KnativeResources:
        return self._resources

    @staticmethod
    def initialize(cfg: Config, dct: Dict[str, Any]) -> None:
        config = cast(KnativeConfig, cfg)
        config.gateway = dct.get("gateway", "http://127.0.0.1:8080")
        config.url_template = dct.get("urlTemplate", "{gateway}/{name}")
        config.host_template = dct.get("hostTemplate", "")
        config.namespace = dct.get("namespace", "default")
        config.kubectl_cli = dct.get("kubectlCli", "kubectl")
        config.service_port = int(dct.get("servicePort", 8080))
        config.shutdownStorage = dct.get("shutdownStorage", False)
        config.experimentalManifest = dct.get("experimentalManifest", False)
        config.dockerhub_repository = dct.get("dockerhubRepository")

    @staticmethod
    def deserialize(
        config: Dict[str, Any], cache: Cache, handlers: LoggingHandlers
    ) -> Config:
        resources = cast(
            KnativeResources, KnativeResources.deserialize(config, cache, handlers)
        )
        res = KnativeConfig(resources, KnativeCredentials(), cache)
        res.logging_handlers = handlers

        cached_config = cache.get_config("knative")
        if cached_config:
            res.logging.info("Loading cached config for Knative")
            KnativeConfig.initialize(res, cached_config)
            KnativeConfig.initialize(res, config)
        else:
            res.logging.info("Using user-provided config for Knative")
            KnativeConfig.initialize(res, config)

        return res

    def serialize(self) -> Dict[str, Any]:
        return {
            "name": "knative",
            "gateway": self.gateway,
            "urlTemplate": self.url_template,
            "hostTemplate": self.host_template,
            "namespace": self.namespace,
            "kubectlCli": self.kubectl_cli,
            "servicePort": self.service_port,
            "shutdownStorage": self.shutdownStorage,
            "experimentalManifest": self.experimentalManifest,
            "dockerhubRepository": self.dockerhub_repository,
            "credentials": self.credentials.serialize(),
            "resources": self.resources.serialize(),
        }

    def update_cache(self, cache: Cache) -> None:
        cache.update_config(val=self.gateway, keys=["knative", "gateway"])
        cache.update_config(val=self.url_template, keys=["knative", "urlTemplate"])
        cache.update_config(val=self.host_template, keys=["knative", "hostTemplate"])
        cache.update_config(val=self.namespace, keys=["knative", "namespace"])
        cache.update_config(val=self.kubectl_cli, keys=["knative", "kubectlCli"])
        cache.update_config(val=self.service_port, keys=["knative", "servicePort"])
        cache.update_config(
            val=self.shutdownStorage, keys=["knative", "shutdownStorage"]
        )
        cache.update_config(
            val=self.experimentalManifest, keys=["knative", "experimentalManifest"]
        )
        cache.update_config(
            val=self.dockerhub_repository, keys=["knative", "dockerhubRepository"]
        )
        self.resources.update_cache(cache)
