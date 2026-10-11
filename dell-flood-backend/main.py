import warnings
warnings.filterwarnings("ignore")
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Aegis — Multimodal 4D Flood Detection, U-RNN Nowcasting & Autonomous MCP Response System",
    description="FastAPI service for SegFormer MiT-B2 SAR+Optical fusion, U-RNN 3-Scale ConvGRU 4D depth nowcasting, Formal MCP Server, and 6-Agent LangGraph orchestration.",
    version="2.0.0",
)

raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:8081,http://localhost:19006,http://localhost:3000,http://127.0.0.1:8081,*",
)
allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

from app.api.endpoints import router as api_router
from app.mcp.aegis_mcp_server import mcp_router

app.include_router(api_router, prefix="/api")
app.include_router(mcp_router)


@app.get("/")
def read_root():
    return {
        "status": "ONLINE",
        "service": "Aegis 4D Flood Detection, U-RNN Nowcasting & Formal MCP Response API",
        "version": "2.0.0",
        "mcp_endpoint": "/api/mcp/tools",
        "documentation": "/docs",
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"Starting Aegis server on http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
