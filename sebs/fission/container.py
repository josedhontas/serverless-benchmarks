# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
"""Docker image naming for Fission functions."""

from typing import Tuple

import docker

from sebs.config import SeBSConfig
from sebs.faas.container import DockerContainer
from sebs.fission.config import FissionConfig


class FissionContainer(DockerContainer):
    @staticmethod
    def name() -> str:
        return "fission"

    @staticmethod
    def typename() -> str:
        return "Fission.Container"

    def __init__(
        self,
        system_config: SeBSConfig,
        config: FissionConfig,
        docker_client: docker.client.DockerClient,
        experimental_manifest: bool,
    ) -> None:
        super().__init__(system_config, docker_client, experimental_manifest)
        self.config = config

    def registry_name(
        self,
        benchmark: str,
        language_name: str,
        language_version: str,
        architecture: str,
    ) -> Tuple[str, str, str, str]:
        registry_name = self.config.resources.docker_registry
        repository_name = self.system_config.docker_repository()
        image_tag = self.system_config.benchmark_image_tag(
            self.name(), benchmark, language_name, language_version, architecture
        )

        if registry_name:
            repository_name = f"{registry_name}/{repository_name}"
        else:
            registry_name = "Docker Hub"
            if self.config.dockerhub_repository is not None:
                repository_name = self.config.dockerhub_repository

        image_uri = f"{repository_name}:{image_tag}"
        return registry_name, repository_name, image_tag, image_uri
