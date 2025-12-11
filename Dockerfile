FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY app.py .
COPY gateway_client.py .
COPY llm.py .
COPY model_config.py .
COPY styles.css .

# Copy assets directory
COPY assets/ ./assets/

# Copy Streamlit configuration
COPY .streamlit/ .streamlit/

# Set environment variables for Streamlit
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# HuggingFace Spaces provides $PORT environment variable
# Expose port (will be set by Hugging Face Spaces)
EXPOSE 7860

# Health check (uses PORT env var)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail http://localhost:${PORT:-7860}/_stcore/health || exit 1

# Run Streamlit app using PORT env var from Hugging Face Spaces
# HuggingFace sets $PORT, don't override it. Default to 7860 if not set.
# Try the main app now
CMD ["bash", "-c", "PORT=${PORT:-7860} && echo Using PORT=$PORT && streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT"]
