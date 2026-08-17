FROM python:3.11-slim-bookworm

# Set Python environment variables for standard production behavior
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Update package lists (required for Playwright's --with-deps to function properly)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium and ALL required system dependencies automatically
RUN playwright install --with-deps chromium

# Copy the rest of your application code
COPY . .

# Render dynamically assigns the PORT environment variable
EXPOSE 8000

# Start the FastAPI application via uvicorn
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]