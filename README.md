# 🤖 Local VRAM Social Content Studio

An automated, self-hosted pipeline that takes text blueprints, generates high-fidelity images completely locally using an open-source AI engine, stamps programmatic UI text overlays, and seamlessly handles scheduling workflows to Google Drive and Meta (Facebook/Instagram).

---

## ⚡ Key Features

* **100% Free Image Generation:** Powered by **FLUX.1-schnell** running completely locally on your hardware (Zero API generation costs).
* **VRAM Optimization:** Configured natively for a 16GB GPU / 32GB System RAM setup using intelligent CPU offloading to prevent Out-Of-Memory (OOM) crashes.
* **Programmatic UI Stamping:** Bypasses AI text rendering limitations by using Pillow to cleanly overlay crisp text rectangles and multiple choice quiz buttons.
* **Automated Scheduling:** Uploads final outputs directly to Google Drive and interfaces with the Meta Graph API to queue up scheduled posts.
* **Interactive Control Board:** Features a built-in Gradio web application for ad-hoc manual prompt creation, live canvas previewing, and scheduling controls.

---

## 🖥️ System Requirements & Architecture

| Component | Minimum Recommended Specs |
| :--- | :--- |
| **GPU VRAM** | 16 GB (NVIDIA card with CUDA capability) |
| **System RAM** | 32 GB (Required for model layer offloading) |
| **Storage Space** | ~30 GB free space (to store local AI weights and runtime caches) |
| :--- | :--- |

---

## 🐳 Docker Setup

### Prerequisites
- **NVIDIA GPU** with CUDA 12.1+ support
- **Docker Engine** installed
- **NVIDIA Container Toolkit** (`nvidia-docker2`) installed for GPU passthrough

### Quick Start with Docker Compose

```bash
# Build and start the container with GPU access
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
```

The service will be available at **http://localhost:7860**

### Docker Compose Configuration Details

The `docker-compose.yml` handles:
- **GPU Passthrough**: Automatic NVIDIA GPU reservation for CUDA acceleration
- **Model Caching**: Mounts `~/.cache/huggingface` from host to persist FLUX model weights (~24GB)
- **Live Reload**: Source code mounted for development iteration
- **Auto-restart**: Container restarts unless explicitly stopped

### Manual Docker Build & Run

```bash
# Build the image
docker build -t local-ai-studio .

# Run with GPU access
docker run -d \
  --name ai_automation_studio \
  --gpus all \
  -p 7860:7860 \
  -v $(pwd):/app \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  --restart unless-stopped \
  local-ai-studio
```

### Important Notes
- **First run** downloads ~24GB FLUX.1-schnell model weights (cached for future runs)
- **Google Drive Auth**: Requires `credentials.json` in project root for OAuth flow
- **Meta API**: Update `META_ACCESS_TOKEN` and `FACEBOOK_PAGE_ID` in `app.py` before deployment

---

## 📂 Project Structure

```text
├── app.py                  # Main Python application (Gradio UI + Processing Pipeline)
├── Dockerfile              # Docker instructions containerizing CUDA/PyTorch environment
├── docker-compose.yml      # Service architecture config for hardware GPU passthrough
├── requirements.txt        # Python external dependencies manifest
└── README.md               # Project documentation