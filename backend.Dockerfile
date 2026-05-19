# Use official slim Python image
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy backend-only dependencies manifest. Do not install the ML/Streamlit stack
# into the API container; it makes free builds much slower and heavier.
COPY requirements-backend.txt .

# Install dependencies (disable pip cache to keep image small)
RUN pip install --no-cache-dir -r requirements-backend.txt

# Copy backend source code and database migrations
COPY ./backend /app/backend
COPY ./database /app/database

# Expose FastAPI default port
EXPOSE 8000

# Run FastAPI app using uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
