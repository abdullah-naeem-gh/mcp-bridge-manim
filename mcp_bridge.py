#!/usr/bin/env python3
"""
HTTP Bridge for MCP Server - Allows web clients to communicate with stdio MCP servers
"""

import json
import subprocess
import asyncio
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uuid
import os

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    global mcp_process
    if mcp_process:
        mcp_process.terminate()
        mcp_process.wait()

app = FastAPI(
    title="MCP HTTP Bridge", 
    description="HTTP bridge for Manim MCP Server",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the HTML client
@app.get("/")
async def serve_client():
    return FileResponse("mcp_client.html")

# Serve video files from output directory
@app.get("/video/{filename}")
async def serve_video(filename: str):
    """Serve video files from the output directory"""
    video_path = os.path.join("output", filename)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(video_path, media_type="video/mp4")

# Mount static files
app.mount("/static", StaticFiles(directory="."), name="static")

class MCPRequest(BaseModel):
    method: str
    params: Optional[Dict[str, Any]] = None

class MCPToolCall(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = {}

# Global MCP server process
mcp_process = None
request_id_counter = 0

async def start_mcp_server():
    """Start the MCP server process"""
    global mcp_process
    if mcp_process is None:
        print("Starting MCP server subprocess...")
        try:
            mcp_process = subprocess.Popen(
                [sys.executable, "manim_mcp_server.py"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,
                cwd="/Users/abdullahnaeem/Projects/manim-mcp"
            )
            
            print("MCP server process started, initializing...")
            
            # Initialize the server
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "http-bridge",
                        "version": "1.0.0"
                    }
                }
            }
            
            request_str = json.dumps(init_request) + "\n"
            print(f"Sending init request: {request_str.strip()}")
            mcp_process.stdin.write(request_str)
            mcp_process.stdin.flush()
            
            # Read initialization response
            response = mcp_process.stdout.readline()
            if response:
                print(f"MCP Server initialized: {response.strip()}")
                # Parse and validate the response
                try:
                    init_response = json.loads(response)
                    if "result" in init_response:
                        print("Initialization successful")
                        
                        # Send initialized notification to complete handshake
                        initialized_notification = {
                            "jsonrpc": "2.0",
                            "method": "notifications/initialized"
                        }
                        notif_str = json.dumps(initialized_notification) + "\n"
                        print(f"Sending initialized notification: {notif_str.strip()}")
                        mcp_process.stdin.write(notif_str)
                        mcp_process.stdin.flush()
                        
                    else:
                        print(f"Initialization failed: {init_response}")
                        return False
                except json.JSONDecodeError as e:
                    print(f"Failed to parse init response: {e}")
                    return False
            else:
                print("No response from MCP server during initialization")
                # Check for errors
                stderr_line = mcp_process.stderr.readline()
                if stderr_line:
                    print(f"MCP Server error: {stderr_line.strip()}")
                return False
                    
        except Exception as e:
            print(f"Error starting MCP server: {e}")
            import traceback
            traceback.print_exc()
            return False
    return True

async def send_mcp_request(method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Send a request to the MCP server"""
    global request_id_counter, mcp_process
    
    if mcp_process is None:
        success = await start_mcp_server()
        if not success:
            return {"error": "Failed to start MCP server"}
    
    if mcp_process is None:
        return {"error": "Failed to start MCP server"}
    
    request_id_counter += 1
    request = {
        "jsonrpc": "2.0",
        "id": request_id_counter,
        "method": method,
        "params": params or {}
    }
    
    request_str = json.dumps(request) + "\n"
    print(f"Sending MCP request: {request_str.strip()}")
    
    try:
        mcp_process.stdin.write(request_str)
        mcp_process.stdin.flush()
        
        # Read response
        response_str = mcp_process.stdout.readline()
        print(f"MCP response: {response_str.strip() if response_str else 'No response'}")
        
        if response_str:
            try:
                return json.loads(response_str)
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON response: {response_str}"
                print(f"JSON decode error: {error_msg}")
                return {"error": error_msg}
        else:
            # Check for errors in stderr
            stderr_line = mcp_process.stderr.readline()
            if stderr_line:
                error_msg = f"MCP server error: {stderr_line.strip()}"
                print(error_msg)
                return {"error": error_msg}
            else:
                return {"error": "No response from MCP server"}
                
    except Exception as e:
        error_msg = f"Error communicating with MCP server: {e}"
        print(error_msg)
        return {"error": error_msg}

@app.post("/mcp/tools/list")
async def list_tools():
    """List available MCP tools"""
    response = await send_mcp_request("tools/list")
    return response

@app.post("/mcp/tools/call")
async def call_tool(tool_call: MCPToolCall):
    """Call an MCP tool"""
    response = await send_mcp_request("tools/call", {
        "name": tool_call.tool_name,
        "arguments": tool_call.arguments
    })
    return response

@app.post("/mcp/request")
async def generic_mcp_request(request: MCPRequest):
    """Send a generic MCP request"""
    response = await send_mcp_request(request.method, request.params)
    return response

# Convenience endpoints for the HTML client
@app.post("/tools/write_manim_script")
async def write_manim_script(content: str, filename: str = "ai_generated_manim_script.py"):
    """Write a Manim script"""
    return await call_tool(MCPToolCall(
        tool_name="write_manim_script",
        arguments={"content": content, "filename": filename}
    ))

@app.post("/tools/render_manim_animation")
async def render_manim_animation(
    scene_name: str,
    filepath: str = None,
    quality: str = "low_quality"
):
    """Render a Manim animation"""
    args = {"scene_name": scene_name, "quality": quality}
    if filepath:
        args["filepath"] = filepath
    
    return await call_tool(MCPToolCall(
        tool_name="render_manim_animation",
        arguments=args
    ))

@app.post("/tools/get_animation_result")
async def get_animation_result(job_id: str):
    """Get animation result"""
    return await call_tool(MCPToolCall(
        tool_name="get_animation_result",
        arguments={"job_id": job_id}
    ))

@app.post("/tools/list_directories")
async def list_directories(directory: str = "/", recursive: bool = False):
    """List directories"""
    return await call_tool(MCPToolCall(
        tool_name="list_directories",
        arguments={"directory": directory, "recursive": recursive}
    ))



if __name__ == "__main__":
    import uvicorn
    import logging
    
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    try:
        print("Starting MCP HTTP Bridge on http://localhost:8002")
        print("Open your browser and go to http://localhost:8002 to use the web client")
        logger.info("Starting uvicorn server...")
        uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
    except Exception as e:
        print(f"Error starting server: {e}")
        import traceback
        traceback.print_exc()
