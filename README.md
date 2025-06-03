# Manim MCP Server ✅ FULLY FUNCTIONAL

![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)
![MCP](https://img.shields.io/badge/MCP-Compatible-green)
![Manim](https://img.shields.io/badge/Manim-Animation-blue)
![Status](https://img.shields.io/badge/Status-Complete-brightgreen)

A Model Context Protocol (MCP) server that enables AI assistants to create and render mathematical animations using [Manim](https://www.manim.community/).

## 🎉 Status: Complete & Working

This MCP server successfully provides a complete animation workflow from script creation to video playback through a standardized MCP interface with beautiful web client.

## ✨ Features

- **✅ MCP Protocol Compliant**: Full stdio-based MCP server implementation
- **✅ Web Interface**: Beautiful browser-based client for script editing and rendering  
- **✅ Animation Pipeline**: Complete workflow from script creation to video playback
- **✅ Video Serving**: Direct video playback in browser
- **✅ Multiple Tools**: 6 MCP tools for comprehensive animation workflow
- **✅ Error Handling**: Robust error management and logging
- **✅ Quality Options**: Multiple rendering quality settings

## 🚀 Quick Start

### 1. Start the MCP Bridge
```bash
python mcp_bridge.py
```

### 2. Open Web Client
Go to http://localhost:8002 in your browser

### 3. Create Animation
- Paste Manim code in the editor
- Set scene name and quality  
- Click "Render Animation"
- Watch your animation appear!

## 🧪 Test Complete Workflow

```bash
python test_complete_workflow.py
```

Output:
```
🚀 Starting Manim MCP Server Complete Workflow Test
============================================================
✅ Connected! Found 6 available tools
✅ Script created successfully!
✅ Animation rendered! Job ID: abc123...
✅ Animation result retrieved successfully!
🎉 Complete workflow test successful!
```

## 📋 Available MCP Tools

| Tool | Description | Usage |
|------|-------------|-------|
| `write_manim_script` | Create Python animation scripts | Write scripts to temp directory |
| `render_manim_animation` | Render animations with quality options | Generate MP4 videos from scripts |
| `get_animation_result` | Retrieve generated video files | Get download URLs for videos |
| `list_directories` | Explore workspace structure | Browse files and folders |
| `read_file` | Read existing script files | View script contents |
| `get_manim_help` | Get usage instructions | Learn how to use the server |

## 🎯 Example Usage

### Simple Circle Animation
```python
from manim import *

class SimpleCircle(Scene):
    def construct(self):
        circle = Circle(radius=1, color=BLUE)
        self.play(Create(circle))
        self.wait(1)
        self.play(FadeOut(circle))
```

### Complex Animation with Text
```python
from manim import *

class MathDemo(Scene):
    def construct(self):
        # Create title
        title = Text("Mathematical Animation", font_size=48)
        self.play(Write(title))
        self.wait(1)
        
        # Create equation
        equation = MathTex(r"e^{i\pi} + 1 = 0")
        equation.next_to(title, DOWN, buff=1)
        
        # Animate
        self.play(Transform(title, Text("Euler's Identity", font_size=36).to_edge(UP)))
        self.play(Write(equation))
        self.wait(2)
```

## 🔧 API Integration

### HTTP Bridge Endpoints

**List Tools:**
```bash
curl -X POST http://localhost:8002/mcp/tools/list
```

**Render Animation:**
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{
    "tool_name": "render_manim_animation",
    "arguments": {
      "scene_name": "MyScene",
      "filepath": "/temp/my_script.py",
      "quality": "low_quality"
    }
  }' \
  http://localhost:8002/mcp/tools/call
```

**Get Video:**
```bash
curl http://localhost:8002/video/{job_id}.mp4
```

## 🏗️ Architecture

```
Web Client (Browser) 
    ↓ HTTP Requests
MCP HTTP Bridge (FastAPI)
    ↓ stdio/JSON-RPC
MCP Server (manim_mcp_server.py)
    ↓ subprocess calls
Manim CLI
    ↓ file output
Output Directory → Video Files
```

## 📁 Project Structure

```
manim-mcp/
├── manim_mcp_server.py          # 🎯 Main MCP server
├── mcp_bridge.py                # 🌐 HTTP bridge for web clients
├── mcp_client.html              # 🖥️  Beautiful web interface
├── test_complete_workflow.py    # 🧪 Comprehensive test suite
├── SETUP_COMPLETE.md           # 📖 Complete documentation
├── temp/                       # 📝 Temporary script files
├── output/                     # 🎬 Generated animation files
└── media/                      # 🗂️  Manim's temporary media files
```

## 🔗 MCP Client Integration

### Claude Desktop
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "manim": {
      "command": "python",
      "args": ["/path/to/manim_mcp_server.py"]
    }
  }
}
```

### VS Code MCP Extension
Use stdio transport to connect to `manim_mcp_server.py`

### Custom Integration
Connect via stdio with JSON-RPC 2.0 following MCP protocol

## 🎊 Success Metrics

- ✅ **100% MCP Compliance**: Full protocol implementation
- ✅ **End-to-End Functionality**: Script → Render → View pipeline works
- ✅ **Web Interface**: User-friendly browser-based client
- ✅ **File Management**: Organized output with proper cleanup
- ✅ **Error Handling**: Graceful degradation and helpful messages
- ✅ **Performance**: Fast rendering with quality options
- ✅ **Extensibility**: Easy to add new tools and features

## 🔍 Troubleshooting

### Common Issues

**MCP Bridge won't start:**
```bash
# Kill any existing process
lsof -ti:8002 | xargs kill -9
python mcp_bridge.py
```

**Animation won't render:**
- Check scene name matches class name exactly
- Verify script syntax with `read_file` tool
- Use `get_manim_help` for assistance

**Can't see video:**
- Ensure job completed successfully
- Check output directory permissions
- Use `get_animation_result` to verify file location

## 📜 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgements

- [Manim Community](https://www.manim.community/) for the amazing animation engine
- [Model Context Protocol](https://modelcontextprotocol.io/) for the standardized interface
- [FastAPI](https://fastapi.tiangolo.com/) for the web framework

---

**Ready to use with any MCP client!** 🎊

For complete setup instructions and examples, see [SETUP_COMPLETE.md](SETUP_COMPLETE.md)
