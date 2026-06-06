# Use an official NVIDIA CUDA runtime base image with Python 3.10
FROM nvidia/cuda:12.1.1-runtime-ubuntu22.04

# Set environment variables to prevent Python from writing pyc files & buffering stdout
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/models/huggingface

# Install system dependencies required for Python, PIL, and Git
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-dev \
    git \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to leverage Docker cache layers
COPY requirements.txt .

# Install Python dependencies
# We explicitly point to the stable CUDA 12.1 wheel index for PyTorch
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cu121

# Copy the rest of your application code
COPY . .

# Expose Gradio's default port
EXPOSE 7860

# Set Gradio environment variables so it listens on all interfaces inside Docker
ENV GRADIO_SERVER_NAME="0.0.0.0"

# Command to run your app
CMD ["python3", "app.py"]
