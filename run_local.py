import argparse
import hashlib
import json
import socket
import threading
import urllib.request
import webbrowser
from pathlib import Path

from waitress import serve

from app import create_app
from vision import MAX_FILE_BYTES


ROOT = Path(__file__).resolve().parent


def verify_model():
    manifest = json.loads((ROOT / "models" / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest.items():
        path = ROOT / "models" / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Restore the original model file: models/{name}")


def main():
    parser = argparse.ArgumentParser(description="Run Python Workshop on this computer.")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    settings = json.loads((ROOT / "settings.json").read_text(encoding="utf-8"))
    port = int(settings["port"])
    if not 1024 <= port <= 65535:
        raise RuntimeError("Choose a port between 1024 and 65535 in settings.json.")
    url = f"http://127.0.0.1:{port}"
    with socket.socket() as probe:
        already_running = probe.connect_ex(("127.0.0.1", port)) == 0
    if already_running:
        try:
            with urllib.request.urlopen(url + "/health", timeout=3) as response:
                existing = json.load(response)
            if existing.get("application") != "python-workshop":
                raise ValueError("Another application is using that port.")
        except Exception as error:
            raise RuntimeError("The port is in use. Choose another port in settings.json.") from error
        print(f"Python Workshop is already running at {url}", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        return

    verify_model()
    app = create_app()
    print(f"Python Workshop: {url}", flush=True)
    print("Keep this window open. Press Ctrl+C to stop.", flush=True)
    print("Photos and results are stored locally in the instance folder.", flush=True)
    if not args.no_browser:
        timer = threading.Timer(1, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()
    serve(app, host="127.0.0.1", port=port, threads=4,
          max_request_body_size=MAX_FILE_BYTES + 128 * 1024)


if __name__ == "__main__":
    main()
