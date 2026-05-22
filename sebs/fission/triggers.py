# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
"""Fission trigger implementations."""

import concurrent.futures
from typing import Any, Dict

from sebs.faas.function import ExecutionResult, Trigger


class HTTPTrigger(Trigger):
    def __init__(self, fname: str, url: str) -> None:
        super().__init__()
        self.fname = fname
        self.url = url

    @staticmethod
    def typename() -> str:
        return "Fission.HTTPTrigger"

    @staticmethod
    def trigger_type() -> Trigger.TriggerType:
        return Trigger.TriggerType.HTTP

    def sync_invoke(self, payload: Dict[str, Any]) -> ExecutionResult:
        self.logging.debug(f"Invoke Fission function {self.url}")
        return self._http_invoke(payload, self.url, False)

    def async_invoke(self, payload: Dict[str, Any]) -> concurrent.futures.Future:
        pool = concurrent.futures.ThreadPoolExecutor()
        return pool.submit(self.sync_invoke, payload)

    def serialize(self) -> Dict[str, str]:
        return {"type": "HTTP", "name": self.fname, "url": self.url}

    @staticmethod
    def deserialize(obj: Dict[str, str]) -> Trigger:
        return HTTPTrigger(obj["name"], obj["url"])
