"""
Launcher for Crash Out Multi-Agent POC Application (Vidu-only).
"""
import uvicorn

# Import app package early so the Windows Proactor connection-reset patch
# is installed before uvicorn opens sockets for /outputs video streaming.
import app.main  # noqa: F401

if __name__ == "__main__":
    print("=" * 65)
    print("  CRASH OUT — Multi-Agent Animation Production Studio")
    print("  Video Engine: Vidu Q4 Preview (reference2video / img2video)")
    print("=" * 65)
    print("Starting server at http://127.0.0.1:8000 ...")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
