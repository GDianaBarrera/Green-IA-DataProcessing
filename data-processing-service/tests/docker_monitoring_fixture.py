"""Explicit synthetic HTTP source used only by Test-Docker.ps1."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlsplit(self.path).query)
        if urlsplit(self.path).path != "/api/v1/metrics/history":
            self.send_error(404)
            return
        result = {
            "metric": "node.cpu.utilization", "unit": "ratio", "aggregation": "mean_non_idle",
            "windowSeconds": 60, "start": query["start"][0], "end": query["end"][0],
            "stepSeconds": int(query["stepSeconds"][0]), "dataStatus": "partial",
            "warnings": ["Docker smoke test: synthetic fixture, not real metrics."],
            "series": [{"resource": {"type": "node", "cluster": "docker-fixture", "id": "node-1"},
                "labels": {}, "source": "fixture", "origin": "simulated", "samples": [
                    {"timestamp": query["start"][0], "value": 0, "quality": "valid"},
                    {"timestamp": query["end"][0], "value": None, "quality": "missing"},
                ]}],
        }
        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()
