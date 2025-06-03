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
from fastapi.responses import FileResponse, Response
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

# Add CORS middleware with proper video file support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "*",
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Range",  # Important for video streaming
        "Authorization",
        "Cache-Control",
        "Pragma"
    ],
    expose_headers=[
        "Content-Range",
        "Accept-Ranges", 
        "Content-Length",
        "Content-Type"
    ]
)

# Serve the HTML client
@app.get("/")
async def serve_client():
    return FileResponse("mcp_client.html")

# Serve video files from output directory
@app.get("/video/{filename}")
async def serve_video(filename: str):
    """Serve video files from the output directory with proper CORS headers"""
    import mimetypes
    from fastapi.responses import StreamingResponse
    from fastapi import Request
    
    # Clean the filename to prevent path traversal
    filename = os.path.basename(filename)
    
    # Try multiple possible locations for the video file
    possible_paths = [
        os.path.join("output", filename),
        os.path.join("output", f"{filename}.mp4") if not filename.endswith('.mp4') else os.path.join("output", filename),
    ]
    
    video_path = None
    for path in possible_paths:
        if os.path.exists(path) and os.path.isfile(path):
            video_path = path
            break
    
    if not video_path:
        # Also check in subdirectories of output
        output_dir = "output"
        if os.path.exists(output_dir):
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    if (file == filename or file == f"{filename}.mp4") and file.endswith('.mp4'):
                        video_path = os.path.join(root, file)
                        break
                if video_path:
                    break
    
    if not video_path or not os.path.exists(video_path):
        print(f"Video file not found: {filename}")
        print(f"Checked paths: {possible_paths}")
        print(f"Output directory contents: {os.listdir('output') if os.path.exists('output') else 'Output dir not found'}")
        raise HTTPException(status_code=404, detail=f"Video file not found: {filename}")
    
    print(f"Serving video file: {video_path}")
    
    # Get MIME type
    mime_type, _ = mimetypes.guess_type(video_path)
    if not mime_type:
        mime_type = "video/mp4"
    
    return FileResponse(
        video_path, 
        media_type=mime_type,
        headers={
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Content-Type, Authorization",
            "Access-Control-Expose-Headers": "Content-Length, Content-Range, Accept-Ranges",
            "Cache-Control": "public, max-age=3600"
        }
    )

# Serve files from output directory with better path handling
@app.get("/output/{file_path:path}")
async def serve_output_file(file_path: str):
    """Serve any file from the output directory with proper CORS headers"""
    import mimetypes
    
    # Clean the file path to prevent path traversal
    file_path = os.path.normpath(file_path).lstrip('/')
    full_path = os.path.join("output", file_path)
    
    # Security check
    if not full_path.startswith(os.path.abspath("output")):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    # Get MIME type
    mime_type, _ = mimetypes.guess_type(full_path)
    if not mime_type:
        if file_path.endswith('.mp4'):
            mime_type = "video/mp4"
        elif file_path.endswith('.png'):
            mime_type = "image/png"
        elif file_path.endswith('.gif'):
            mime_type = "image/gif"
        else:
            mime_type = "application/octet-stream"
    
    return FileResponse(
        full_path,
        media_type=mime_type,
        headers={
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Content-Type",
            "Cache-Control": "public, max-age=3600"
        }
    )

# Handle OPTIONS preflight requests for CORS
@app.options("/{path:path}")
async def options_handler(path: str):
    """Handle OPTIONS preflight requests for CORS"""
    return {
        "message": "OK",
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Range, Content-Type, Authorization, Accept",
            "Access-Control-Max-Age": "86400"
        }
    }

# Debug endpoint to list available videos
@app.get("/debug/videos")
async def list_available_videos():
    """List all available video files for debugging"""
    videos = []
    output_dir = "output"
    
    if os.path.exists(output_dir):
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                if file.endswith(('.mp4', '.png', '.gif')):
                    rel_path = os.path.relpath(os.path.join(root, file), output_dir)
                    videos.append({
                        "filename": file,
                        "relative_path": rel_path,
                        "full_path": os.path.join(root, file),
                        "video_url": f"/video/{file}",
                        "output_url": f"/output/{rel_path}"
                    })
    
    return {
        "total_files": len(videos),
        "files": videos,
        "output_directory": os.path.abspath(output_dir) if os.path.exists(output_dir) else "Not found"
    }

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
