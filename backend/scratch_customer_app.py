from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()

# 1. The Customer's Auth API (What Leaka Orchestrator will call)
@app.post("/api/login")
def login(payload: dict):
    # Returns a token
    return {"status": "success", "data": {"access_token": "super-secret-enterprise-jwt"}}

# 2. The Customer's Frontend App (What the Leaka Agent will see)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return """
    <html>
        <head>
            <title>Customer Dashboard</title>
        </head>
        <body>
            <div id="content">Loading...</div>
            <script>
                // Simulate an SPA checking local storage for auth
                const token = localStorage.getItem("token");
                const contentDiv = document.getElementById("content");
                if (token === "super-secret-enterprise-jwt") {
                    contentDiv.innerHTML = "<h1>Welcome Admin!</h1><p id='invoice-amount'>Invoice Total: $5,200.00</p>";
                } else {
                    contentDiv.innerHTML = "<h1>401 Unauthorized</h1><p>Please log in.</p>";
                }
            </script>
        </body>
    </html>
    """

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
