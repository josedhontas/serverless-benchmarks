# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
import datetime
import importlib
import json
import os
import sys
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

CODE_LOCATION = "/function"
CODE_PARENT = os.path.dirname(CODE_LOCATION)
sys.path.append(CODE_LOCATION)
sys.path.append(CODE_PARENT)
sys.path.append(os.path.join(CODE_LOCATION, ".python_packages/lib/site-packages/"))


def _handler():
    try:
        return importlib.import_module("function.function").handler
    except ModuleNotFoundError:
        return importlib.import_module("function").handler


class Handler(BaseHTTPRequestHandler):
    def _read_body(self):
        length = self.headers.get("Content-Length")
        if length is not None:
            return self.rfile.read(int(length))

        if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
            chunks = []
            while True:
                size_line = self.rfile.readline().strip()
                if not size_line:
                    continue
                size = int(size_line.split(b";", 1)[0], 16)
                if size == 0:
                    self.rfile.readline()
                    break
                chunks.append(self.rfile.read(size))
                self.rfile.readline()
            return b"".join(chunks)

        return b"{}"

    def _write_json(self, status, payload):
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path in ("/alive", "/_/health"):
            self._write_json(200, {"result": "ok"})
        else:
            self._write_json(404, {"error": "not found"})

    def do_POST(self):
        begin = datetime.datetime.now()
        request_id = str(uuid.uuid4())
        try:
            payload = json.loads(self._read_body() or b"{}")

            ret = _handler()(payload)
            end = datetime.datetime.now()
            is_cold = False
            cold_file = "/tmp/sebs-cold-run"
            if not os.path.exists(cold_file):
                is_cold = True
                open(cold_file, "a").close()

            self._write_json(
                200,
                {
                    "begin": begin.strftime("%s.%f"),
                    "end": end.strftime("%s.%f"),
                    "request_id": request_id,
                    "is_cold": is_cold,
                    "result": ret,
                },
            )
        except Exception as e:
            end = datetime.datetime.now()
            self._write_json(
                500,
                {
                    "begin": begin.strftime("%s.%f"),
                    "end": end.strftime("%s.%f"),
                    "request_id": request_id,
                    "result": f"Error - invocation failed! Reason: {e}",
                },
            )

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
