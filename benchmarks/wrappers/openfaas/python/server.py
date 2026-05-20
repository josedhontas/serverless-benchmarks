# Copyright 2020-2025 ETH Zurich and the SeBS authors. All rights reserved.
import datetime
import json
import os
import sys
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

CODE_LOCATION = "/function"
sys.path.append(CODE_LOCATION)
sys.path.append(os.path.join(CODE_LOCATION, ".python_packages/lib/site-packages/"))


class Handler(BaseHTTPRequestHandler):
    def _write_json(self, status, payload):
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == "/alive":
            self._write_json(200, {"result": "ok"})
        else:
            self._write_json(404, {"error": "not found"})

    def do_POST(self):
        begin = datetime.datetime.now()
        request_id = str(uuid.uuid4())
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")

            from function import handler

            ret = handler(payload)
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
