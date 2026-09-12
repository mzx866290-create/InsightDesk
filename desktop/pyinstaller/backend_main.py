import uvicorn

from backend.api_server import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(__import__("os").environ.get("SERVER_PORT", "8000")),
        log_level="info",
    )
