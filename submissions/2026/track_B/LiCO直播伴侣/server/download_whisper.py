import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
from huggingface_hub import snapshot_download
print("Starting download...")
snapshot_download("Systran/faster-whisper-base")
print("Download complete.")
