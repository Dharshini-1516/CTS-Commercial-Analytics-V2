# Base Python Image
FROM python:3.11-slim

# System Dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set Working Directory
WORKDIR /app

# Copy Requirements
COPY requirements.txt .

# Install Python Packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy Source Code & Assets
COPY . .

# Expose Streamlit (8501) and FastAPI (8000)
EXPOSE 8501 8000

# Start Streamlit Dashboard & FastAPI Server in Parallel
CMD python api_server.py & python -m streamlit run app.py --server.port=8501 --server.address=0.0.0.0
