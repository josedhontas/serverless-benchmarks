# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
"""Knative trigger implementations."""

import concurrent.futures
import json
from datetime import datetime
from io import BytesIO
from typing import Any, Dict

from sebs.faas.function import ExecutionResult, Trigger


class HTTPTrigger(Trigger):
    def __init__(self, fname: str, url: str, host: str = "") -> None:
        super().__init__()
        self.fname = fname
        self.url = url
        self.host = host

    @staticmethod
    def typename() -> str:
        return "Knative.HTTPTrigger"

    @staticmethod
    def trigger_type() -> Trigger.TriggerType:
        return Trigger.TriggerType.HTTP

    def sync_invoke(self, payload: Dict[str, Any]) -> ExecutionResult:
        self.logging.debug(f"Invoke Knative service {self.url}")
        if self.host:
            return self._http_invoke_with_host(payload, self.url, self.host)
        return self._http_invoke(payload, self.url, False)

    def _http_invoke_with_host(
        self, payload: Dict[str, Any], url: str, host: str
    ) -> ExecutionResult:
        import pycurl

        c = pycurl.Curl()
        c.setopt(
            pycurl.HTTPHEADER,
            ["Content-Type: application/json", f"Host: {host}"],
        )
        c.setopt(pycurl.POST, 1)
        c.setopt(pycurl.URL, url)
        c.setopt(pycurl.SSL_VERIFYHOST, 0)
        c.setopt(pycurl.SSL_VERIFYPEER, 0)
        data = BytesIO()
        c.setopt(pycurl.WRITEFUNCTION, data.write)
        c.setopt(pycurl.POSTFIELDS, json.dumps(payload))

        begin = datetime.now()
        c.perform()
        end = datetime.now()
        status_code = c.getinfo(pycurl.RESPONSE_CODE)
        try:
            output = json.loads(data.getvalue())
            if status_code != 200:
                self.logging.error(f"Invocation on URL {url} failed!")
                self.logging.error(f"Output: {output}")
                raise RuntimeError(f"Failed invocation of function! Output: {output}")

            result = ExecutionResult.from_times(begin, end)
            result.times.http_startup = c.getinfo(pycurl.PRETRANSFER_TIME)
            result.times.http_first_byte_return = c.getinfo(pycurl.STARTTRANSFER_TIME)
            if "request_id" not in output:
                raise RuntimeError(f"Cannot process allocation with output: {output}")
            result.request_id = output["request_id"]
            result.parse_benchmark_output(output)
            return result
        except json.decoder.JSONDecodeError:
            self.logging.error(f"Invocation on URL {url} failed!")
            if len(data.getvalue()) > 0:
                self.logging.error(f"Output: {data.getvalue().decode()}")
            else:
                self.logging.error("No output provided!")
            raise RuntimeError(
                f"Failed invocation of function! Output: {data.getvalue().decode()}"
            ) from None

    def async_invoke(self, payload: Dict[str, Any]) -> concurrent.futures.Future:
        pool = concurrent.futures.ThreadPoolExecutor()
        return pool.submit(self.sync_invoke, payload)

    def serialize(self) -> Dict[str, str]:
        return {"type": "HTTP", "name": self.fname, "url": self.url, "host": self.host}

    @staticmethod
    def deserialize(obj: Dict[str, str]) -> Trigger:
        return HTTPTrigger(obj["name"], obj["url"], obj.get("host", ""))
