"""Start a local web server to explore RIPPLE visualizations, pitch deck, and graph."""

import http.server
import socketserver
import sys
import webbrowser
from pathlib import Path

PORT = 8000
DIRECTORY = Path(__file__).resolve().parent.parent


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)


def find_free_port(start_port: int = 8000, max_attempts: int = 20) -> int:
    import socket

    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def main():
    port = find_free_port(PORT)
    url = f"http://localhost:{port}"

    print("=" * 60)
    print("🌊 RIPPLE Localhost Explorer Server")
    print("=" * 60)
    print(f"Serving workspace: {DIRECTORY}")
    print(f"URL: {url}")
    print(f"  - Dashboard:   {url}/")
    print(f"  - Impact Map:  {url}/ripple_map.html")
    print(f"  - Pitch Deck:  {url}/docs/pitch_deck.html")
    print(f"  - Code Graph:  {url}/graphify-out/graph.html")
    print("=" * 60)
    print("Press Ctrl+C to stop the server.\n")

    # Automatically open browser
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
