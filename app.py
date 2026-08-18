from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).parent

class SiteHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, format, *args):
        print(f"[site] {self.address_string()} - {format % args}")

if __name__ == "__main__":
    port = 8000
    print(f"CIAP-PB disponível em http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), SiteHandler).serve_forever()
