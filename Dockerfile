FROM python:3.12-slim

# Print logs immediately and don't write .pyc files
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Install Python build tool
RUN pip install --no-cache-dir hatchling

# Copy project files
COPY pyproject.toml pyproject.toml
COPY src src
COPY README.md README.md
COPY .env.example .env.example

# Install the package and runtime dependencies (all available as prebuilt wheels,
# so no compiler toolchain is needed)
RUN pip install --no-cache-dir .

# Run as an unprivileged user; installed code stays root-owned and read-only to it
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER app

# Run the MCP server; transport is selected by MCP_TRANSPORT (default: stdio)
CMD ["python", "src/intervals_mcp_server/server.py"]
