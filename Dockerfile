# Dockerfile for ScriptACC server
# Use a slim Python image for minimal size
FROM python:3.12-slim

# Set a non‑root user for security
RUN useradd -m scriptacc && \
    mkdir -p /app && chown scriptacc:scriptacc /app
USER scriptacc
WORKDIR /app

# Install runtime dependencies
COPY --chown=scriptacc:scriptacc requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code and configuration
COPY --chown=scriptacc:scriptacc server.py .
COPY --chown=scriptacc:scriptacc config.yaml .

EXPOSE 8000

# Default command runs the FastAPI server
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
