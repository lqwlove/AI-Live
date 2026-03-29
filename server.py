"""Web entry point for tk-live."""

import threading
import webbrowser

import uvicorn

from api.app import create_app
from utils.paths import is_frozen

app = create_app()


def main():
    host = "0.0.0.0"
    port = 8000

    if is_frozen():
        threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
        uvicorn.run(app, host=host, port=port)
    else:
        uvicorn.run("server:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    main()
