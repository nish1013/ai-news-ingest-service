import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from xml.sax.saxutils import escape

from ingest.domain.feed import FeedItem


@dataclass(frozen=True)
class Reply:
    body: bytes = b""
    status: int = 200
    stall: bool = False
    drip_seconds: float = 0.0
    send_length: bool = True


@dataclass
class FeedServer:
    base_url: str
    replies: dict[str, Reply] = field(default_factory=dict)
    requested_paths: list[str] = field(default_factory=list)
    stopped: threading.Event = field(default_factory=threading.Event)

    def serve(self, path: str, body: bytes) -> str:
        return self.reply(path, Reply(body=body))

    def reply(self, path: str, reply: Reply) -> str:
        self.replies[path] = reply
        return f"{self.base_url}{path}"


@contextmanager
def feed_server() -> Iterator[FeedServer]:
    state = FeedServer(base_url="")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            state.requested_paths.append(self.path)
            reply = state.replies.get(self.path)
            if reply is None:
                self.send_error(404)
                return
            if reply.stall:
                state.stopped.wait()
                return
            self.send_response(reply.status)
            self.send_header("Content-Type", "application/rss+xml")
            if reply.send_length:
                self.send_header("Content-Length", str(len(reply.body)))
            self.end_headers()
            if reply.drip_seconds:
                self._drip(reply)
            else:
                self.wfile.write(reply.body)

        def log_message(self, format: str, *args: object) -> None:
            pass

        def _drip(self, reply: Reply) -> None:
            for byte in reply.body:
                if state.stopped.wait(reply.drip_seconds):
                    return
                try:
                    self.wfile.write(bytes([byte]))
                    self.wfile.flush()
                except OSError:
                    return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state.base_url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        state.stopped.set()
        server.shutdown()
        server.server_close()


def closed_port_url() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
    port = server.server_address[1]
    server.server_close()
    return f"http://127.0.0.1:{port}/feed"


def rss(items: list[FeedItem]) -> bytes:
    entries = "".join(_rss_item(item) for item in items)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel><title>Feed</title>'
        f"<link>https://example.com/</link>{entries}</channel></rss>"
    ).encode()


def empty_atom() -> bytes:
    return (
        b'<?xml version="1.0" encoding="utf-8"?>'
        b'<feed xmlns="http://www.w3.org/2005/Atom"><title>The Batch</title>'
        b"<id>urn:the-batch</id><updated>2026-10-26T09:00:00Z</updated></feed>"
    )


def html_page() -> bytes:
    return (
        b"<!doctype html><html><head><title>OpenAI blog</title></head>"
        b"<body><p>Read the blog.</p></body></html>"
    )


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
