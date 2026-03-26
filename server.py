"""Web entry point for tk-live."""

from api.app import create_app

app = create_app()


def main():
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
