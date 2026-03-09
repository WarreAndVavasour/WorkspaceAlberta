# E2B Template: workspace-alberta-foundation
# Profile: foundation
# Description: Core tools for any small business

FROM e2b/code-interpreter:latest

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js MCP servers
RUN npm install -g @anthropic-ai/claude-code \
    @modelcontextprotocol/server-filesystem \
    @anthropic/mcp-server-brave-search

# Install Python dependencies
RUN pip3 install mcp pandas openpyxl

# Copy MCP configuration
COPY .mcp.json /root/.mcp.json

# Copy setup script
COPY setup.sh /workspace/setup.sh
RUN chmod +x /workspace/setup.sh

# Set working directory
WORKDIR /workspace

# Default command
CMD ["bash"]
