# Container image for hosting pure-mpg-mcp as a remote Streamable-HTTP MCP server.
# The MCP endpoint is served at /mcp on $PORT.
FROM python:3.12-slim

# Install uv for fast, reproducible installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src

RUN uv pip install --system --no-cache .

ENV MCP_TRANSPORT=http \
    HOST=0.0.0.0 \
    PORT=8000
EXPOSE 8000

CMD ["pure-mpg-mcp"]
