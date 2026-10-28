import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from xml.sax.saxutils import escape

from ingest.domain.feed import FeedItem


@dataclass
class FeedServer:
    base_url: str
    bodies: dict[str, bytes] = field(default_factory=dict)
    requested_paths: list[str] = field(default_factory=list)

    def serve(self, path: str, body: bytes) -> str:
        self.bodies[path] = body
        return f"{self.base_url}{path}"


@contextmanager
def feed_server() -> Iterator[FeedServer]:
    state = FeedServer(base_url="")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state.requested_paths.append(self.path)
            body = state.bodies.get(self.path)
            if body is None:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/rss+xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state.base_url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()


def rss(items: list[FeedItem]) -> bytes:
    entries = "".join(_rss_item(item) for item in items)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel><title>Feed</title>'
        f"<link>https://example.com/</link>{entries}</channel></rss>"
    ).encode()


def _rss_item(item: FeedItem) -> str:
    published = (
        f"<pubDate>{_rfc822(item.published_at)}</pubDate>" if item.published_at else ""
    )
    return (
        f"<item><title>{escape(item.title)}</title>"
        f"<link>{escape(item.link)}</link>{published}</item>"
    )


def _rfc822(at: datetime) -> str:
    return format_datetime(at)
