#!/usr/bin/env python3
# 使い方: sink.py <port> <出力先.jsonl>
# POST された本文を 1 行ずつ追記する。Mod の $.http.fetch が届くかを確かめる受け口
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

port, out = int(sys.argv[1]), sys.argv[2]


class Sink(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length", 0)))
        with open(out, "ab") as f:
            f.write(body.rstrip(b"\n") + b"\n")
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):
        pass


HTTPServer(("127.0.0.1", port), Sink).serve_forever()
