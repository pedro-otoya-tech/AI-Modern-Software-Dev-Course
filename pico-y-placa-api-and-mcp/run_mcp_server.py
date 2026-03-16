import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from mcp_server.server import mcp
mcp.run()
