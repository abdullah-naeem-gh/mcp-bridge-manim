#!/usr/bin/env python3
"""
Standalone Manim MCP Server - A proper MCP server for creating and running Manim animations
"""

import os
import json
import stat
import datetime
import subprocess
import uuid
from pathlib import Path
from typing import Annotated
from mcp.server.fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("manim")

# Determine if running in Docker or locally
RUNNING_IN_DOCKER = os.path.exists('/.dockerenv')

# Set up base paths based on environment
if not RUNNING_IN_DOCKER:
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "."))
else:
    PROJECT_ROOT = "/"

# Define allowed base directories for security
if RUNNING_IN_DOCKER:
    ALLOWED_BASE_DIRS = ["/manim", "/app", "/media", "/usr/local", "/tmp"]
else:
    ALLOWED_BASE_DIRS = [
        PROJECT_ROOT,
        os.path.join(PROJECT_ROOT, "temp"),
        os.path.join(PROJECT_ROOT, "output"),
        os.path.join(PROJECT_ROOT, "animations"),
        "/tmp"
    ]

# Define media directory from environment variable or use default
MEDIA_DIR = os.environ.get("MEDIA_DIR", os.path.join(PROJECT_ROOT, "output"))

# Create media directory if it doesn't exist
if not os.path.exists(MEDIA_DIR):
    try:
        os.makedirs(MEDIA_DIR, exist_ok=True)
    except Exception:
        pass  # Will handle errors when actually trying to use the directory

def adjust_path(path):
    """Adjust paths for local vs Docker environment"""
    if not RUNNING_IN_DOCKER and path.startswith('/'):
        if path.startswith('/manim/temp'):
            return os.path.join(PROJECT_ROOT, 'temp', path[12:])
        elif path.startswith('/manim/output'):
            return os.path.join(PROJECT_ROOT, 'output', path[13:])
        elif path.startswith('/manim'):
            return os.path.join(PROJECT_ROOT, path[7:])
        elif path.startswith('/temp/'):
            # Handle paths that start directly with /temp/
            return os.path.join(PROJECT_ROOT, 'temp', path[6:])
        elif path.startswith('/output/'):
            # Handle paths that start directly with /output/
            return os.path.join(PROJECT_ROOT, 'output', path[8:])
    return path

def get_python_executable():
    """Get the correct Python executable (virtual env aware)"""
    import sys
    return sys.executable

@mcp.tool()
def list_directories(
    directory: Annotated[str, {"description": "Directory path to list"}] = "/",
    recursive: Annotated[bool, {"description": "Whether to list files recursively"}] = False,
    show_hidden: Annotated[bool, {"description": "Whether to show hidden files"}] = False
) -> str:
    """List files and directories in the workspace"""
    # Normalize the path
    directory = os.path.normpath(directory)
    
    # Adjust path for local environment
    directory = adjust_path(directory)
    
    # Security check: Prevent path traversal attacks
    if ".." in directory.split(os.sep):
        return "Error: Path traversal attempts are not allowed"
    
    # Security check: Ensure the directory is under an allowed base directory
    if not any(directory == base or directory.startswith(f"{base}{os.sep}") for base in ALLOWED_BASE_DIRS):
        return f"Error: Access is only allowed to these base directories: {', '.join(ALLOWED_BASE_DIRS)}"
    
    # Check if directory exists
    if not os.path.exists(directory):
        return f"Error: Directory not found: {directory}"
    
    # Check if path is a directory
    if not os.path.isdir(directory):
        return f"Error: Path is not a directory: {directory}"
    
    # List files and directories
    results = []
    
    try:
        entries = os.listdir(directory)
        
        # Filter hidden files if needed
        if not show_hidden:
            entries = [entry for entry in entries if not entry.startswith('.')]
            
        # Get file information
        for entry in entries:
            entry_path = os.path.join(directory, entry)
            is_dir = os.path.isdir(entry_path)
            results.append(f"{'📁 ' if is_dir else '📄 '}{entry}")
            
    except PermissionError:
        return f"Error: Permission denied: {directory}"
    
    # Sort results: directories first, then files alphabetically
    results.sort()
    
    # Format the output for better readability
    output = [f"Directory: {directory}"]
    output.append(f"Total items: {len(results)}")
    output.append("")
    output.extend(results)
    
    return "\n".join(output)

@mcp.tool()
def write_manim_script(
    content: Annotated[str, {"description": "The Python code for the Manim script"}],
    filename: Annotated[str, {"description": "Filename to save the script as"}] = "ai_generated_manim_script.py"
) -> str:
    """Write a Manim script to a file that can be executed"""
    
    # Ensure we're writing to the temp directory for safety
    if "/" in filename:
        return "Error: Filename should not include path separators"
    
    # Set up the filepath
    if RUNNING_IN_DOCKER:
        filepath = f"/manim/temp/{filename}"
    else:
        filepath = os.path.join(PROJECT_ROOT, "temp", filename)
    
    # Get the directory part of the path
    directory = os.path.dirname(filepath)
    
    # Create directory if it doesn't exist
    if not os.path.exists(directory):
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as e:
            return f"Error: Failed to create directory {directory}: {str(e)}"
    
    # Try to write the file
    try:
        with open(filepath, 'w') as file:
            file.write(content)
        
        return f"Successfully wrote script to {filepath}. You can now render it with the render_manim_animation tool."
    except Exception as e:
        return f"Error: Failed to write file: {str(e)}"

@mcp.tool()
def render_manim_animation(
    scene_name: Annotated[str, {"description": "Name of the scene class to render"}],
    filepath: Annotated[str, {"description": "Path to the Python file with Manim scenes"}] = None,
    quality: Annotated[str, {"description": "Quality: low_quality, medium_quality, high_quality, or production_quality"}] = "low_quality"
) -> str:
    """Render a Manim animation from a Python script"""
    
    # Use default script path if not provided
    if not filepath:
        if RUNNING_IN_DOCKER:
            filepath = "/manim/temp/ai_generated_manim_script.py"
        else:
            filepath = os.path.join(PROJECT_ROOT, "temp", "ai_generated_manim_script.py")
    else:
        # Adjust path for local environment
        filepath = adjust_path(filepath)
    
    # Check if the file exists
    if not os.path.exists(filepath):
        return f"Error: File not found: {filepath}"
    
    # Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    # Set up output file path directly
    output_file = os.path.join(MEDIA_DIR, f"{job_id}.mp4")
    
    # Get the correct Python executable (virtual env aware)
    python_executable = get_python_executable()
    
    # Check if manim is available using the correct Python
    try:
        result = subprocess.run([python_executable, "-c", "import manim; print(manim.__file__)"], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            return f"Error: Manim is not installed in the current Python environment. Please install with: pip install manim\nUsing Python: {python_executable}\nError: {result.stderr}"
    except Exception as e:
        return f"Error: Cannot check Manim installation: {str(e)}"
    
    # Create output directory if it doesn't exist
    try:
        os.makedirs(MEDIA_DIR, exist_ok=True)
    except Exception as e:
        return f"Error: Failed to create media directory {MEDIA_DIR}: {str(e)}"
    
    # Check if the directory is writable
    if not os.access(MEDIA_DIR, os.W_OK):
        return f"Error: Media directory {MEDIA_DIR} is not writable"
    
    # Create a temporary working directory (manim needs a writable current directory)
    temp_work_dir = os.path.join(MEDIA_DIR, f"temp_work_{job_id}")
    try:
        os.makedirs(temp_work_dir, exist_ok=True)
    except Exception as e:
        return f"Error: Failed to create temporary working directory: {str(e)}"
    
    # Create a media symlink in the temp directory pointing to our output directory
    media_link = os.path.join(temp_work_dir, "media")
    try:
        # First check if it exists
        if not os.path.exists(media_link):
            # Create a symlink on Unix or a directory junction on Windows
            if os.name == 'nt':  # Windows
                subprocess.run(['mklink', '/J', media_link, MEDIA_DIR], shell=True, check=False)
            else:  # Unix/Mac
                os.symlink(MEDIA_DIR, media_link)
    except Exception as e:
        # If symlink fails, try creating a real directory
        try:
            os.makedirs(media_link, exist_ok=True)
        except Exception as inner_e:
            return f"Error: Could not create media directory or symlink: {str(e)}, {str(inner_e)}"
    
    # Build the command with explicit output directory
    cmd = [python_executable, "-m", "manim"]
    
    # Explicitly set the media directory FIRST - this must come before quality flags
    cmd.append(f"--media_dir={MEDIA_DIR}")
    
    # Add quality flag AFTER media_dir
    if quality == "low_quality":
        cmd.append("-ql")
    elif quality == "medium_quality":
        cmd.append("-qm")
    elif quality == "high_quality":
        cmd.append("-qh")
    elif quality == "production_quality":
        cmd.append("-qk")
    else:
        return f"Error: Unknown quality level: {quality}"
    
    # Add the file path and scene name
    cmd.append(filepath)
    cmd.append(scene_name)
    
    # Debug: Log the exact command that will be executed
    debug_cmd = ' '.join(cmd)
    
    try:
        # Save the current directory to return to later
        original_dir = os.getcwd()
        
        # Change to our temporary working directory
        os.chdir(temp_work_dir)
        
        # Create environment variables to influence Manim's behavior
        env = os.environ.copy()
        env["MANIM_MEDIA_DIR"] = MEDIA_DIR
        env["TMPDIR"] = temp_work_dir  # Set temp directory to our writable location
        
        # Run the command with the modified environment
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            env=env
        )
        
        # Change back to the original directory
        os.chdir(original_dir)
        
        # Map quality to Manim's output directory names
        quality_map = {
            "low_quality": "480p15",
            "medium_quality": "720p30", 
            "high_quality": "1080p60",
            "production_quality": "2160p60"
        }
        quality_dir = quality_map.get(quality, "480p15")
        
        script_name = os.path.splitext(os.path.basename(filepath))[0]
        
        # Look for the rendered file in Manim's output structure
        # Now using MEDIA_DIR instead of PROJECT_ROOT/media
        manim_output_path = os.path.join(MEDIA_DIR, "videos", script_name, quality_dir, f"{scene_name}.mp4")
        
        files = []
        actual_output_file = None
        
        # Check if the expected file exists
        if os.path.exists(manim_output_path):
            # Copy the file to our output directory with the job ID
            import shutil
            try:
                shutil.copy2(manim_output_path, output_file)
                files.append(os.path.basename(output_file))
                actual_output_file = output_file
            except Exception as e:
                return f"Error copying rendered file: {str(e)}"
        else:
            # Look for any mp4 files in the media directory that might have been created
            media_videos_dir = os.path.join(MEDIA_DIR, "videos")
            if os.path.exists(media_videos_dir):
                for root, dirs, media_files in os.walk(media_videos_dir):
                    for file in media_files:
                        if file.endswith('.mp4') and scene_name in file:
                            source_path = os.path.join(root, file)
                            # Copy to our output directory
                            try:
                                import shutil
                                shutil.copy2(source_path, output_file)
                                files.append(os.path.basename(output_file))
                                actual_output_file = output_file
                                break
                            except Exception as e:
                                continue
        
        # Also check for files in main output directory with job_id in name
        if os.path.exists(MEDIA_DIR):
            main_files = [f for f in os.listdir(MEDIA_DIR) 
                         if os.path.isfile(os.path.join(MEDIA_DIR, f)) and job_id in f]
            files.extend(main_files)
        
        # Create response message
        response = [
            f"Animation rendered successfully! Job ID: {job_id}",
            f"Command used: {debug_cmd}",  # Show the debug command
            f"Working directory: {temp_work_dir}",
            f"Media directory: {MEDIA_DIR}",
            f"Scene: {scene_name}",
            f"Return code: {result.returncode}",
            ""
        ]
        
        if result.returncode == 0:
            response.append("✅ Rendering completed successfully")
            if actual_output_file and os.path.exists(actual_output_file):
                response.append(f"✅ Output file created: {actual_output_file}")
            response.append(f"Files generated: {len(files)}")
            
            # Include file info
            for file in files:
                response.append(f"- {file}")
            
            # Include stdout if available
            if result.stdout:
                response.append("")
                response.append("Manim output:")
                response.append(result.stdout[-1000:])  # Last 1000 chars
        else:
            response.append("❌ Rendering failed")
            if result.stderr:
                response.append("")
                response.append("Error details:")
                response.append(result.stderr[-1000:])  # Last 1000 chars
        
        response.append("")
        response.append(f"To view your animation, use the get_animation_result tool with job_id: {job_id}")
        
        return "\n".join(response)
    
    except subprocess.TimeoutExpired:
        return f"Error: Rendering timed out after 5 minutes. The animation may be too complex."
    except subprocess.CalledProcessError as e:
        return f"""Error rendering animation:
Command: {' '.join(cmd)}
Return code: {e.returncode}
Error output:
{e.stderr}

Make sure the scene name exists in the file and check your Manim code for errors."""
    except Exception as e:
        return f"Unexpected error during rendering: {str(e)}"

@mcp.tool()
def get_animation_result(
    job_id: Annotated[str, {"description": "The job ID returned from the render_manim_animation function"}]
) -> str:
    """Get the animation results for a specific job ID"""
    
    # Define the output directories to check
    if RUNNING_IN_DOCKER:
        job_output_dir = f"/manim/output/{job_id}"
        main_output_dir = "/manim/output"
    else:
        job_output_dir = os.path.join(PROJECT_ROOT, "output", job_id)
        main_output_dir = os.path.join(PROJECT_ROOT, "output")
    
    files = []
    
    # Check in the job-specific output directory
    if os.path.exists(job_output_dir):
        dir_files = [f for f in os.listdir(job_output_dir) if os.path.isfile(os.path.join(job_output_dir, f))]
        for file in dir_files:
            files.append(("job_dir", file, os.path.join(job_output_dir, file)))
    
    # Check in the main output directory for files with job_id in the name
    if os.path.exists(main_output_dir):
        main_files = [f for f in os.listdir(main_output_dir) 
                     if os.path.isfile(os.path.join(main_output_dir, f)) and job_id in f]
        for file in main_files:
            files.append(("main_dir", file, os.path.join(main_output_dir, file)))
    
    if not files:
        return f"No animation files found for job ID: {job_id}"
    
    # Create response message
    response = [
        f"Animation results for job ID: {job_id}",
        f"Files found: {len(files)}",
        ""
    ]
    
    # Include file info
    for location, file, file_path in files:
        location_desc = "job directory" if location == "job_dir" else "output directory"
        response.append(f"- {file} (in {location_desc}: {file_path})")
    
    return "\n".join(response)

@mcp.tool()
def read_file(
    filepath: Annotated[str, {"description": "Path to the file to read"}]
) -> str:
    """Read the contents of a file"""
    
    # Adjust path for local environment
    filepath = adjust_path(filepath)
    
    # Security check: Prevent path traversal attacks
    if ".." in filepath.split(os.sep):
        return "Error: Path traversal attempts are not allowed"
    
    # Security check: Ensure the file is under an allowed base directory
    if not any(filepath == base or filepath.startswith(f"{base}{os.sep}") for base in ALLOWED_BASE_DIRS):
        return f"Error: Access is only allowed to these base directories: {', '.join(ALLOWED_BASE_DIRS)}"
    
    # Check if the file exists
    if not os.path.exists(filepath):
        return f"Error: File not found: {filepath}"
    
    # Check if the path is a file
    if not os.path.isfile(filepath):
        return f"Error: Path is not a file: {filepath}"
    
    # Try to read the file
    try:
        with open(filepath, 'r') as file:
            content = file.read()
        
        if len(content) > 100000:  # Limit large files
            content = content[:100000] + "\n... (content truncated, file too large)"
        
        return f"File: {filepath}\n\n{content}"
    except Exception as e:
        return f"Error reading file {filepath}: {str(e)}"

@mcp.tool()
def get_manim_help() -> str:
    """Get help information about using Manim with this MCP server"""
    
    return """# Manim MCP Server Help

This server allows you to create and run mathematical animations using Manim.

## Available Tools

1. **list_directories**: Browse files in the workspace
2. **write_manim_script**: Save a Manim Python script to a file
3. **render_manim_animation**: Run Manim to generate animations
4. **get_animation_result**: View generated animation files for a specific job
5. **read_file**: Read the contents of a file
6. **get_manim_help**: Show this help information

## Typical Workflow

1. Write a Manim script using `write_manim_script`
2. Render the animation using `render_manim_animation`
3. View the results using `get_animation_result`

## Example Manim Script

```python
from manim import *

class ExampleScene(Scene):
    def construct(self):
        # Create a circle
        circle = Circle(radius=2.0, color=BLUE)
        
        # Add the circle to the scene
        self.play(Create(circle))
        
        # Wait for a moment
        self.wait(1)
        
        # Transform the circle into a square
        square = Square(side_length=4.0, color=RED)
        self.play(Transform(circle, square))
        
        # Wait for another moment
        self.wait(1)
        
        # Add some text
        text = Text("Hello, Manim!", font_size=36)
        self.play(Write(text))
        
        # Final pause
        self.wait(2)
```

For more information about Manim, visit: https://www.manim.community/
"""

@mcp.tool()
def get_video_url(
    job_id: Annotated[str, {"description": "The job ID returned from the render_manim_animation function"}]
) -> str:
    """Get the direct URL to access a rendered video file"""
    
    # Define the output directories to check
    if RUNNING_IN_DOCKER:
        main_output_dir = "/manim/output"
    else:
        main_output_dir = os.path.join(PROJECT_ROOT, "output")
    
    video_file = None
    
    # Check for the video file with job_id in the name
    if os.path.exists(main_output_dir):
        main_files = [f for f in os.listdir(main_output_dir) 
                     if os.path.isfile(os.path.join(main_output_dir, f)) and job_id in f and f.endswith('.mp4')]
        if main_files:
            video_file = main_files[0]
    
    if video_file:
        # Return the HTTP URL that can be used to access the video
        video_url = f"http://localhost:8002/video/{video_file}"
        return f"Video URL: {video_url}\nDirect file path: {os.path.join(main_output_dir, video_file)}"
    else:
        return f"No video file found for job ID: {job_id}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
