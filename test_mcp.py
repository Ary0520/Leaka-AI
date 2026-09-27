from fastapi import FastAPI
import uvicorn
from backend.app.mcp_server import leaka_mcp

test_app = FastAPI()

# Mount the MCP SSE application natively
test_app.mount("/mcp", leaka_mcp.sse_app())

if __name__ == "__main__":
    uvicorn.run(test_app, host="127.0.0.1", port=8001)
