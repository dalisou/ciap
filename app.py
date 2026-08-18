from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import os

ROOT = Path(__file__).parent


class SiteHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            directory=str(ROOT),
            **kwargs
        )

    def log_message(self, format, *args):
        print(f"[site] {self.address_string()} - {format % args}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))

    print(f"CIAP-PB disponível na porta {port}")

    server = ThreadingHTTPServer(
        ("0.0.0.0", port),
        SiteHandler
    )

    server.serve_forever()
