# Container image for hosting pure-mpg-mcp as a remote Streamable-HTTP MCP server.
# The MCP endpoint is served at /mcp on $PORT.
FROM python:3.12-slim AS base

# Install uv for fast, reproducible installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src

# ponytail: gates the image build on the test suite (excluding live-network
# tests) so a broken build never reaches Render. Not a dependency of the
# final stage's install, so it only runs via this explicit COPY --from below.
FROM base AS test
COPY tests ./tests
COPY scripts ./scripts
COPY openapi ./openapi
RUN uv pip install --system --no-cache ".[dev]" \
    && python -m pytest -m "not network" \
    && touch /tested

FROM base
RUN uv pip install --system --no-cache .
COPY --from=test /tested /tested

ENV MCP_TRANSPORT=http \
    HOST=0.0.0.0 \
    PORT=8000
EXPOSE 8000

CMD ["pure-mpg-mcp"]
