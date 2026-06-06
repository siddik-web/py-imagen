import os
import json
import time
import requests
import torch
import gradio as gr
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from diffusers import FluxPipeline
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ==========================================
# CONFIGURATION CONSTANTS
# ==========================================
META_ACCESS_TOKEN = "your-meta-page-access-token"
FACEBOOK_PAGE_ID = "your-facebook-page-id"
GOOGLE_SCOPES = ['https://www.googleapis.com/auth/drive.file']
FLUX_MODEL_ID = os.getenv("FLUX_MODEL_ID", "black-forest-labs/FLUX.1-schnell")
LOCAL_OUTPUT_DIR = Path(os.getenv("LOCAL_OUTPUT_DIR", "outputs"))


def get_huggingface_token():
    return os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")


def has_huggingface_auth():
    if get_huggingface_token():
        return True

    hf_home = Path(os.getenv("HF_HOME", Path.home() / ".cache" / "huggingface"))
    return (hf_home / "token").exists()

# ==========================================
# LOCAL GPU ENGINE LOADING (FLUX.1-schnell)
# ==========================================
pipe = None


def get_flux_pipeline():
    global pipe
    if pipe is not None:
        return pipe

    if not has_huggingface_auth():
        raise RuntimeError(
            "FLUX.1-schnell is a gated Hugging Face model. Request access at "
            "https://huggingface.co/black-forest-labs/FLUX.1-schnell, create a "
            "Hugging Face access token, then set HF_TOKEN in your .env file before "
            "starting Docker Compose."
        )

    print("Loading FLUX into system RAM... This will take a moment on first generation.")
    try:
        pipe = FluxPipeline.from_pretrained(
            FLUX_MODEL_ID,
            torch_dtype=torch.bfloat16,
            token=get_huggingface_token()
        )
    except Exception as exc:
        if "gated repo" in str(exc).lower() or "401" in str(exc):
            raise RuntimeError(
                f"Unable to download {FLUX_MODEL_ID}. Confirm your Hugging Face "
                "account has accepted the model terms and that HF_TOKEN is valid "
                "inside the container."
            ) from exc
        raise

    # Offload layers back and forth between 32GB System RAM and 16GB VRAM dynamically.
    pipe.enable_model_cpu_offload()
    return pipe

# ==========================================
# CORE PROCESSING FUNCTIONS
# ==========================================

def save_image_locally(image):
    LOCAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = f"{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns() % 1_000_000_000:09d}"
    output_path = LOCAL_OUTPUT_DIR / f"generated_post_{timestamp}.png"
    image.save(output_path)
    return output_path


def get_google_drive_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', GOOGLE_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)


def upload_image_to_drive(local_image_path):
    print("Syncing file with Google Drive API...")
    service = get_google_drive_service()
    file_metadata = {'name': local_image_path.name}

    with open(local_image_path, 'rb') as image_file:
        media = MediaIoBaseUpload(image_file, mimetype='image/png')
        file_drive = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webContentLink'
        ).execute()

    return file_drive


def schedule_meta_post(public_url, post_caption, delay_hours):
    print("Transmitting scheduling window to Meta...")
    scheduled_epoch = int(time.time()) + int(delay_hours * 3600)

    meta_url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/photos"
    payload = {
        'url': public_url,
        'caption': post_caption,
        'published': 'false',
        'scheduled_publish_time': scheduled_epoch,
        'access_token': META_ACCESS_TOKEN
    }
    return requests.post(meta_url, data=payload).json()


def process_pipeline(json_input_str, post_caption, delay_hours, save_to_google_drive, post_to_social):
    try:
        # 1. Parse JSON input
        data = json.loads(json_input_str)
        req = data["image_generation_request"]
        
        # Determine image sizing based on request
        width, height = 1024, 1024
        if req.get("aspect_ratio") == "4:5":
            width, height = 896, 1120

        # 2. Local GPU Generation
        flux_pipe = get_flux_pipeline()
        print("Generating background with local GPU VRAM...")
        generated_img = flux_pipe(
            prompt=req["prompt"],
            height=height,
            width=width,
            guidance_scale=0.0,
            num_inference_steps=4,
            max_sequence_length=256
        ).images[0]

        # 3. Apply Text Layers
        print("Stamping overlay elements...")
        draw = ImageDraw.Draw(generated_img)
        try:
            font_main = ImageFont.truetype("arial.ttf", 38)
            font_btn = ImageFont.truetype("arial.ttf", 28)
        except IOError:
            font_main = font_btn = ImageFont.load_default()

        for overlay in req["text_overlays"]:
            text = overlay["text"]
            style = overlay["style"]
            
            if "top center" in style:
                rect_w, rect_h = 520, 80
                x1, y1 = (width - rect_w) // 2, 60
                x2, y2 = x1 + rect_w, y1 + rect_h
                draw.rounded_rectangle([x1, y1, x2, y2], radius=15, fill="#007BFF")
                draw.text((x1 + 35, y1 + 18), text, fill="white", font=font_main)
                
            elif "below main text" in style:
                buttons = [b.strip() for b in text.split("|")]
                btn_w, btn_h = 110, 60
                spacing = 25
                total_w = (len(buttons) * btn_w) + ((len(buttons) - 1) * spacing)
                start_x = (width - total_w) // 2
                y_pos = 180
                
                for i, btn_text in enumerate(buttons):
                    bx1 = start_x + (i * (btn_w + spacing))
                    by1 = y_pos
                    bx2 = bx1 + btn_w
                    by2 = by1 + btn_h
                    draw.rounded_rectangle([bx1, by1, bx2, by2], radius=10, fill="white", outline="black", width=2)
                    draw.text((bx1 + 32, by1 + 14), btn_text, fill="black", font=font_btn)

        # 4. Save locally before any optional external action.
        local_image_path = save_image_locally(generated_img)
        status_messages = [f"Image saved locally: {local_image_path}"]

        file_drive = None
        public_url = None
        should_upload_to_drive = save_to_google_drive or post_to_social

        if post_to_social and not save_to_google_drive:
            status_messages.append("Google Drive upload enabled automatically because Meta posting needs a reachable image URL.")

        # 5. Optional Google Drive upload.
        if should_upload_to_drive:
            file_drive = upload_image_to_drive(local_image_path)
            public_url = file_drive.get('webContentLink')
            status_messages.append(f"Image uploaded to Google Drive. File ID: {file_drive.get('id')}")

        # 6. Optional Meta API scheduling.
        if post_to_social:
            if not public_url:
                raise RuntimeError("Meta posting requires a Google Drive image URL, but the upload did not return one.")

            meta_res = schedule_meta_post(public_url, post_caption, delay_hours)

            if "id" in meta_res:
                status_messages.append(f"Post scheduled to release in {delay_hours} hour(s). Meta Post ID: {meta_res['id']}")
            else:
                status_messages.append(f"Meta API failed: {meta_res}")

        if not save_to_google_drive and not post_to_social:
            status_messages.append("Google Drive upload and social posting were skipped.")

        return generated_img, "\n".join(status_messages)

    except Exception as e:
        return None, f"An execution error occurred: {str(e)}"

# ==========================================
# GRADIO INTERFACE ASSEMBLY
# ==========================================
default_json_template = """{
  "image_generation_request": {
    "prompt": "Photo of smiling woman on blue tennis court holding racket. Wearing white polo and blue skirt. Sunny day, blurred trees background.",
    "text_overlays": [
      {"text": "I'm great ___ tennis.", "style": "white text on blue rounded rectangle, top center"},
      {"text": "on | in | at", "style": "three separate white buttons with black text, below main text"}
    ],
    "style": "photorealistic, bright lighting",
    "aspect_ratio": "4:5"
  }
}"""

with gr.Blocks(title="Local Social AI Automation Studio") as demo:
    gr.Markdown("# Local VRAM Content Studio")
    gr.Markdown("Input your generation schema instructions, review creative output variables, and choose whether to upload or schedule after local save.")
    
    with gr.Row():
        with gr.Column(scale=1):
            json_box = gr.Textbox(label="JSON Generation Prompt Blueprint", lines=12, value=default_json_template)
            caption_box = gr.Textbox(label="Social Post Caption / Copy text", placeholder="Type your hook or captions here...", lines=3)
            time_slider = gr.Slider(minimum=1, maximum=168, value=2, step=1, label="Post Schedule Delay (Hours from now)")
            save_drive_checkbox = gr.Checkbox(label="Auto save to Google Drive", value=False)
            post_social_checkbox = gr.Checkbox(label="Post to social media page", value=False)
            submit_btn = gr.Button("Generate Image", variant="primary")
            
        with gr.Column(scale=1):
            image_preview = gr.Image(label="Live Generated Composition Preview")
            status_box = gr.Textbox(label="System Pipeline Output Log", interactive=False)

    submit_btn.click(
        fn=process_pipeline,
        inputs=[json_box, caption_box, time_slider, save_drive_checkbox, post_social_checkbox],
        outputs=[image_preview, status_box]
    )

if __name__ == "__main__":
    # Launch local developer server web portal
    demo.launch(inbrowser=True)
