# E2B Template: CanadaBuys Showcase
# A minimal template demonstrating the CanadaBuys MCP server
# for searching Canadian federal government contracts

FROM e2b/code-interpreter:latest

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI and core MCP servers
RUN npm install -g @anthropic-ai/claude-code \
    @modelcontextprotocol/server-filesystem

# Create directory for custom MCP servers
RUN mkdir -p /opt/mcp-servers/canadabuys

# Copy the CanadaBuys MCP server
COPY canadabuys/ /opt/mcp-servers/canadabuys/

# Install Python dependencies for CanadaBuys
RUN pip3 install mcp

# Copy MCP configuration
COPY .mcp.json /root/.mcp.json

# Copy setup script
COPY setup.sh /workspace/setup.sh
RUN chmod +x /workspace/setup.sh

# Create data directory for CanadaBuys cache
RUN mkdir -p /root/.canadabuys

# Set working directory
WORKDIR /workspace

# Default command
CMD ["bash"]
