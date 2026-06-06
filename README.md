# Local VRAM Social Content Studio

An automated, self-hosted pipeline that takes text blueprints, generates images locally with FLUX.1-schnell, stamps clean text overlays with Pillow, and prepares scheduling workflows for Google Drive and Meta.

## Key Features

- **Local image generation**: Runs FLUX.1-schnell on your own NVIDIA GPU.
- **16GB VRAM friendly**: Uses Diffusers CPU offload for a 16GB GPU / 32GB RAM setup.
- **Programmatic text overlays**: Uses Pillow for crisp text boxes and button-style overlays.
- **Gradio interface**: Provides a local browser UI at `http://localhost:7860`.
- **Local-first output**: Saves every generated image to your local drive before any upload or posting step.
- **Optional scheduling pipeline**: Lets you choose whether to upload generated images to Google Drive and whether to send scheduling requests to Meta.

## Recommended Local PC Specs

| Component | Recommended |
| :--- | :--- |
| GPU | NVIDIA GPU with 16GB VRAM |
| System RAM | 32GB |
| Storage | At least 40GB free for model files, Docker layers, and generated images |
| OS | Windows with Docker Desktop and WSL2 backend |

## Step-by-Step Local Setup

### 1. Install Required Software

Install these first:

- [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
- Latest NVIDIA GPU driver
- NVIDIA Container Toolkit support through Docker Desktop / WSL2

After installing Docker Desktop, open PowerShell in this project folder:

```powershell
cd D:\Projects\py-imagen
```

Check Docker:

```powershell
docker --version
docker compose version
```

Check that Windows can see your GPU:

```powershell
nvidia-smi
```

You should see your NVIDIA GPU and available VRAM.

### 2. Create a Hugging Face Account

1. Go to https://huggingface.co/
2. Select **Sign Up** if you do not already have an account.
3. Verify your email address.
4. Sign in to your Hugging Face account.

### 3. Request Access to FLUX.1-schnell

`black-forest-labs/FLUX.1-schnell` is a gated Hugging Face model. The app cannot download it until your Hugging Face account has access.

1. Open https://huggingface.co/black-forest-labs/FLUX.1-schnell
2. Sign in if Hugging Face asks you to.
3. Read and accept the model license / access terms.
4. Wait until the page shows that you have access.

If you skip this step, the app will fail with a `401 Unauthorized` or `GatedRepoError`.

### 4. Create a Hugging Face Access Token

1. Open https://huggingface.co/settings/tokens
2. Select **New token**.
3. Give it a name, for example:

```text
py-imagen-local
```

4. Choose a token type that allows reading model files. A read-only token is enough.
5. Create the token.
6. Copy the token immediately. It will look similar to:

```text
hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Keep this token private. Do not paste it into GitHub, chat, screenshots, or commits.

### 5. Create Your Local `.env` File

In PowerShell, copy the example env file:

```powershell
Copy-Item .env.example .env
```

Open it:

```powershell
notepad .env
```

Replace the placeholder token with your real Hugging Face token:

```env
HF_TOKEN=hf_your_real_token_here
FLUX_MODEL_ID=black-forest-labs/FLUX.1-schnell
```

Save and close Notepad.

The `.env` file is ignored by Git so your token does not get committed.

### 6. Build and Start the App

Run:

```powershell
docker compose up --build
```

The first run can take a long time because Docker builds the image. The Gradio page should open before the model is loaded. The FLUX model downloads and loads the first time you click **Generate Image**.

The model is large, so it is stored in a persistent Docker volume instead of inside the container image.

```text
huggingface_model_cache
```

Inside the container, that volume is mounted at:

```text
/models/huggingface
```

Docker rebuilds and normal `docker compose down` commands keep this volume, so the model should not download again every time you restart. The first generation after starting the app can still take a while because the model must be loaded from disk into RAM/VRAM.

After the model finishes loading, open:

```text
http://localhost:7860
```

Generated images are saved locally in:

```text
D:\Projects\py-imagen\outputs
```

Because the project folder is mounted into Docker, the container path `/app/outputs` maps back to this Windows folder.

### 7. Generate Locally, Upload, or Post

The app always saves the generated PNG locally first. The two checkboxes control what happens after local save:

- **Auto save to Google Drive**: Uploads the saved PNG to your Google Drive.
- **Post to social media page**: Schedules the image through the Meta API. This also uploads to Google Drive automatically because Meta needs a reachable image URL.

Leave both unchecked when you only want to test local image generation.

### 8. Run in the Background

After you confirm the app works, you can run it detached:

```powershell
docker compose up --build -d
```

View logs:

```powershell
docker compose logs -f
```

Stop the app:

```powershell
docker compose down
```

This stops and removes the container, but keeps the downloaded model volume.

Restart after changing `.env`:

```powershell
docker compose down
docker compose up --build
```

Check the model cache volume:

```powershell
docker volume ls
docker volume inspect py-imagen_huggingface_model_cache
```

Only delete the model cache if you intentionally want to free disk space and are okay downloading FLUX again:

```powershell
docker compose down
docker volume rm py-imagen_huggingface_model_cache
```

## Optional Google Drive Setup

The image-generation UI can run without Google Drive. You only need Google setup when you enable **Auto save to Google Drive** or **Post to social media page**.

1. Create a Google Cloud project.
2. Enable the Google Drive API.
3. Create OAuth client credentials for a desktop app.
4. Download the credentials JSON file.
5. Rename it to:

```text
credentials.json
```

6. Put it in the project root:

```text
D:\Projects\py-imagen\credentials.json
```

The first time the app uploads to Drive, it will create `token.json`. Both `credentials.json` and `token.json` are ignored by Git.

## Optional Meta Setup

You only need Meta setup when you enable **Post to social media page**. To schedule posts through Meta, update these values in `app.py`:

```python
META_ACCESS_TOKEN = "your-meta-page-access-token"
FACEBOOK_PAGE_ID = "your-facebook-page-id"
```

You need a valid Meta Graph API page access token with the permissions required to create and schedule photo posts.

## Troubleshooting

### `401 Unauthorized` or `GatedRepoError`

This means Hugging Face authentication is missing or your account has not been approved for the model.

Check:

- You accepted access at https://huggingface.co/black-forest-labs/FLUX.1-schnell
- `.env` exists in `D:\Projects\py-imagen`
- `.env` contains a real `HF_TOKEN`
- You restarted Docker Compose after editing `.env`

### CUDA out of memory

Your 16GB GPU should work with CPU offload, but VRAM can still run out if other apps are using the GPU.

Try:

- Close games, video editors, and extra browser tabs.
- Generate one image at a time.
- Reduce image size in `app.py`, for example from `896x1120` to `768x960`.
- Keep `pipe.enable_model_cpu_offload()` enabled.

### Docker cannot access the GPU

Run:

```powershell
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.1.1-runtime-ubuntu22.04 nvidia-smi
```

If the Docker command fails, check Docker Desktop, WSL2, NVIDIA drivers, and GPU container support.

### Model downloads again after restart

The model should stay in the Docker volume named `py-imagen_huggingface_model_cache`.

Check:

- You are starting the app from the same project folder.
- You did not run `docker compose down -v`.
- You did not delete the `py-imagen_huggingface_model_cache` Docker volume.
- `docker-compose.yml` still mounts `huggingface_model_cache:/models/huggingface`.

### `localhost:7860` does not open

Check that the container is running and that port `7860` is published:

```powershell
docker compose ps
docker compose logs -f
```

The Gradio UI should launch before FLUX loads. If the page is open but the first generation takes a long time, that usually means the model is downloading or loading from the Docker volume.

## Project Structure

```text
.
|-- app.py
|-- Dockerfile
|-- docker-compose.yml
|-- requirements.txt
|-- .env.example
|-- .gitignore
|-- outputs/
`-- README.md
```
