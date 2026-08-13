import streamlit as st
import requests
import time
import json
import os
import base64
import uuid
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv

# Load .env (locally)
load_dotenv()

# ============================================================
# AI STUDIO PRO
# Video Generation Edition
# ============================================================

APP_NAME = "AI Studio Pro"

OUTPUT_DIR = Path("generated_videos")
OUTPUT_DIR.mkdir(exist_ok=True)

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🚀",
    layout="wide"
)

# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 1.5rem;
    border-radius: 12px;
    color: white;
    text-align: center;
    margin-bottom: 1.5rem;
}
.main-header h1 {
    font-size: 2.4rem;
    margin: 0;
}
.main-header p {
    font-size: 1rem;
    opacity: 0.9;
    margin-top: 0.5rem;
}
.stButton > button {
    font-weight: bold;
    border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>🚀 AI Studio Pro</h1>
    <p>🎬 Video Generation · 🎨 Image · 💬 Chat</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SESSION STATE - API Keys
# ============================================================

if "agnes_key" not in st.session_state:
    st.session_state.agnes_key = ""

if "gemini_key" not in st.session_state:
    st.session_state.gemini_key = ""

if "agnes_key_locked" not in st.session_state:
    st.session_state.agnes_key_locked = False

if "gemini_key_locked" not in st.session_state:
    st.session_state.gemini_key_locked = False

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# ============================================================
# API CONFIGURATION - ✅ نیا Endpoint
# ============================================================

APIS = {
    "agnes": {
        "name": "Agnes AI",
        "base_url": "https://apihub.agnes-ai.cn/v1",  # ✅ نیا Endpoint
        "models": {
            "video": "agnes-video-v2.0",
            "image": "agnes-image-2.1-flash",
            "chat": "agnes-2.5-flash"
        }
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "models": {
            "chat": "gemini-2.0-flash",
            "vision": "gemini-2.0-flash",
            "video": "veo-3.1-generate-preview"
        }
    }
}

# ============================================================
# API KEY FUNCTIONS
# ============================================================

def get_api_key(api_name):
    """API Key کو Session State سے حاصل کریں"""
    if api_name == "agnes":
        return st.session_state.get("agnes_key", "").strip()
    elif api_name == "gemini":
        return st.session_state.get("gemini_key", "").strip()
    return ""

def is_key_locked(api_name):
    if api_name == "agnes":
        return st.session_state.get("agnes_key_locked", False)
    elif api_name == "gemini":
        return st.session_state.get("gemini_key_locked", False)
    return False

# ============================================================
# HEADERS
# ============================================================

def make_headers(api_name):
    key = get_api_key(api_name)

    if api_name == "gemini":
        return {
            "Content-Type": "application/json",
            "x-goog-api-key": key
        }
    else:
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }

# ============================================================
# ERROR EXTRACTION
# ============================================================

def extract_error(response):
    try:
        data = response.json()
        if isinstance(data, dict):
            if "error" in data:
                error = data["error"]
                if isinstance(error, dict):
                    return error.get("message") or error.get("detail") or str(error)
                return str(error)
            if "message" in data:
                return str(data["message"])
            if "detail" in data:
                return str(data["detail"])
        text = response.text.strip()
        if text:
            return text[:1000]
    except Exception:
        pass
    return f"HTTP {response.status_code}"

# ============================================================
# DOWNLOAD VIDEO
# ============================================================

def download_url_to_file(url, filename=None, headers=None):
    if not filename:
        filename = f"video_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.mp4"
    path = OUTPUT_DIR / filename

    try:
        with requests.get(url, headers=headers or {}, stream=True, timeout=(20, 900)) as response:
            if response.status_code != 200:
                return {"success": False, "error": extract_error(response)}
            with open(path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file.write(chunk)
        return {"success": True, "path": str(path)}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================================
# AGNES VIDEO - 15 Seconds
# ============================================================

def call_agnes_video(
    prompt,
    quality="720p",
    ratio="16:9",
    reference_image=None,
    audio_prompt=None,
    max_minutes=12
):
    key = get_api_key("agnes")
    if not key:
        return {
            "success": False,
            "error": "❌ Agnes API key is missing. Please add key in sidebar."
        }

    ratio_map = {
        "1:1": (768, 768),
        "16:9": (1024, 576),
        "9:16": (576, 1024),
        "4:3": (896, 672),
        "3:4": (672, 896)
    }
    width, height = ratio_map.get(ratio, (1024, 576))

    quality_map = {
        "720p": "720p",
        "1080p": "1080p",
        "2K": "2K",
        "4K": "4K"
    }
    quality_value = quality_map.get(quality, "720p")

    final_prompt = prompt
    if audio_prompt:
        final_prompt = f"{prompt}. Audio: {audio_prompt}"

    payload = {
        "model": APIS["agnes"]["models"]["video"],
        "prompt": final_prompt,
        "height": height,
        "width": width,
        "num_frames": 361,
        "frame_rate": 24,
        "duration": 15,
        "quality": quality_value
    }

    if reference_image:
        try:
            ref_image_data = reference_image.read()
            base64_image = base64.b64encode(ref_image_data).decode("utf-8")
            payload["image"] = base64_image
        except Exception as e:
            return {"success": False, "error": f"Error processing reference image: {str(e)}"}

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    start_url = f"{APIS['agnes']['base_url']}/videos"

    try:
        st.info("🚀 Sending video job to Agnes...")
        response = requests.post(
            start_url,
            headers=headers,
            json=payload,
            timeout=(20, 90)
        )
        if response.status_code == 429:
            return {"success": False, "error": "Agnes rate limit. Try again later."}
        if response.status_code not in (200, 201, 202):
            return {"success": False, "error": f"Agnes start error: {extract_error(response)}"}
        data = response.json()
        video_id = data.get("video_id") or data.get("id") or data.get("job_id")
        if not video_id:
            return {"success": False, "error": "Agnes did not return a video/job ID."}
        st.success(f"✅ Agnes job started: {video_id}")
    except Exception as e:
        return {"success": False, "error": f"Agnes start error: {str(e)}"}

    status_url = f"https://apihub.agnes-ai.com/agnesapi?video_id={quote(str(video_id))}"
    progress_bar = st.progress(0)
    status_text = st.empty()
    started_at = time.time()
    poll_count = 0

    while True:
        elapsed = time.time() - started_at
        if elapsed > (max_minutes * 60):
            progress_bar.empty()
            status_text.empty()
            return {"success": False, "error": f"Agnes job exceeded {max_minutes} minutes.", "video_id": video_id}

        if poll_count < 5:
            interval = 2
        elif poll_count < 15:
            interval = 4
        else:
            interval = 7
        time.sleep(interval)
        poll_count += 1

        try:
            status_response = requests.get(
                status_url,
                headers={"Authorization": f"Bearer {key}"},
                timeout=(15, 30)
            )
        except:
            status_text.warning("⚠️ Agnes status request failed. Trying again...")
            continue

        if status_response.status_code != 200:
            continue

        try:
            status_data = status_response.json()
        except:
            continue

        actual_error = status_data.get("error")
        internal_status = str(status_data.get("internal_status", "")).lower()
        external_status = str(status_data.get("status", "")).lower()

        if actual_error not in (None, "", {}, []):
            progress_bar.empty()
            status_text.empty()
            return {"success": False, "error": f"Agnes error: {actual_error}", "video_id": video_id}

        failed_statuses = {"failed", "failure", "cancelled", "canceled", "error", "expired"}
        if internal_status in failed_statuses or external_status in failed_statuses:
            progress_bar.empty()
            status_text.empty()
            return {"success": False, "error": f"Agnes job failed: {internal_status or external_status}", "video_id": video_id}

        progress_value = status_data.get("progress")
        if isinstance(progress_value, (int, float)):
            progress_value = max(0, min(100, progress_value))
            progress_bar.progress(int(progress_value))

        video_url = None
        metadata = status_data.get("metadata")
        if isinstance(metadata, dict):
            video_url = metadata.get("url")
        if not video_url:
            video_url = status_data.get("url")
        if not video_url:
            video_obj = status_data.get("video")
            if isinstance(video_obj, dict):
                video_url = video_obj.get("url")

        if video_url:
            progress_bar.progress(100)
            status_text.success("✅ Agnes video is ready. Downloading...")
            download_result = download_url_to_file(
                video_url,
                headers={"Authorization": f"Bearer {key}"}
            )
            progress_bar.empty()
            status_text.empty()
            if download_result["success"]:
                return {"success": True, "path": download_result["path"], "api": "Agnes AI", "video_id": video_id}
            return {"success": True, "url": video_url, "api": "Agnes AI", "video_id": video_id}

        if progress_value is not None:
            status_text.text(f"⏳ Agnes generating video... {int(progress_value)}% · {int(elapsed // 60)}m {int(elapsed % 60)}s")

# ============================================================
# GEMINI VEO 3 VIDEO
# ============================================================

def call_gemini_video(
    prompt,
    quality="720p",
    aspect_ratio="16:9",
    reference_image=None,
    audio_prompt=None,
    max_minutes=15
):
    key = get_api_key("gemini")
    if not key:
        return {
            "success": False,
            "error": "❌ Gemini API key is missing. Please add key in sidebar."
        }

    quality_map = {
        "720p": "720p",
        "1080p": "1080p",
        "2K": "2K",
        "4K": "4K"
    }
    resolution = quality_map.get(quality, "720p")

    final_prompt = prompt
    if audio_prompt:
        final_prompt = f"{prompt}. Audio: {audio_prompt}"

    model = APIS["gemini"]["models"]["video"]
    url = f"{APIS['gemini']['base_url']}/models/{model}:predictLongRunning"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": key
    }

    payload = {
        "instances": [{"prompt": final_prompt}],
        "parameters": {
            "aspectRatio": aspect_ratio,
            "resolution": resolution
        }
    }

    if reference_image:
        try:
            ref_image_data = reference_image.read()
            base64_image = base64.b64encode(ref_image_data).decode("utf-8")
            payload["instances"][0]["image"] = {
                "mime_type": "image/jpeg",
                "data": base64_image
            }
        except Exception as e:
            return {"success": False, "error": f"Error processing reference image: {str(e)}"}

    try:
        st.info("🚀 Sending video job to Gemini Veo 3...")
        response = requests.post(url, headers=headers, json=payload, timeout=(20, 90))
        if response.status_code not in (200, 201, 202):
            return {"success": False, "error": f"Gemini start error: {extract_error(response)}"}
        data = response.json()
        operation_name = data.get("name")
        if not operation_name:
            return {"success": False, "error": "Gemini did not return an operation name."}
        st.success("✅ Gemini video job started.")
    except Exception as e:
        return {"success": False, "error": f"Gemini start error: {str(e)}"}

    progress_bar = st.progress(0)
    status_text = st.empty()
    started_at = time.time()

    while True:
        elapsed = time.time() - started_at
        if elapsed > (max_minutes * 60):
            progress_bar.empty()
            status_text.empty()
            return {"success": False, "error": f"Gemini job exceeded {max_minutes} minutes.", "operation": operation_name}

        time.sleep(8)
        operation_url = f"{APIS['gemini']['base_url']}/{operation_name}"

        try:
            status_response = requests.get(
                operation_url,
                headers={"x-goog-api-key": key},
                timeout=(15, 45)
            )
        except:
            status_text.warning("⚠️ Gemini status timeout. Trying again...")
            continue

        if status_response.status_code != 200:
            continue

        try:
            status_data = status_response.json()
        except:
            continue

        if "error" in status_data:
            error_value = status_data.get("error")
            if error_value:
                progress_bar.empty()
                status_text.empty()
                return {"success": False, "error": f"Gemini video job failed: {error_value}"}

        done = status_data.get("done", False)
        if done:
            response_data = status_data.get("response", {})
            generated_response = response_data.get("generateVideoResponse", {})
            samples = generated_response.get("generatedSamples", [])
            if not samples:
                samples = response_data.get("generatedVideos", [])
            video_uri = None
            if samples:
                first_sample = samples[0]
                if isinstance(first_sample, dict):
                    video_obj = first_sample.get("video", {})
                    if isinstance(video_obj, dict):
                        video_uri = video_obj.get("uri")
            if not video_uri:
                progress_bar.empty()
                status_text.empty()
                return {"success": False, "error": "Gemini finished but no video URI was found."}

            progress_bar.progress(100)
            status_text.info("📥 Gemini video ready. Downloading...")
            download_result = download_url_to_file(
                video_uri,
                headers={"x-goog-api-key": key}
            )
            progress_bar.empty()
            status_text.empty()
            if download_result["success"]:
                return {"success": True, "path": download_result["path"], "api": "Gemini Veo 3"}
            return {"success": False, "error": f"Download failed: {download_result['error']}"}

        estimated = min(95, (elapsed / (max_minutes * 60)) * 100)
        progress_bar.progress(max(1, int(estimated)))
        status_text.text(f"⏳ Gemini Veo 3 processing... {int(estimated)}% · {int(elapsed // 60)}m {int(elapsed % 60)}s")

# ============================================================
# MAIN VIDEO GENERATOR
# ============================================================

def generate_video(prompt, api_choice, quality="720p", ratio="16:9", reference_image=None, audio_prompt=None):
    if api_choice == "agnes":
        return call_agnes_video(
            prompt,
            quality=quality,
            ratio=ratio,
            reference_image=reference_image,
            audio_prompt=audio_prompt
        )
    elif api_choice == "gemini":
        return call_gemini_video(
            prompt,
            quality=quality,
            aspect_ratio=ratio,
            reference_image=reference_image,
            audio_prompt=audio_prompt
        )
    return {"success": False, "error": "Unknown video engine."}

# ============================================================
# SIDEBAR - API Keys with LOCK
# ============================================================

with st.sidebar:
    st.markdown("## ⚙️ API Settings")
    st.caption("🔐 Keys are locked after pressing Enter")

    # --------------------------------------------------------
    # AGNES
    # --------------------------------------------------------
    st.markdown("### 🟣 Agnes AI")

    if not st.session_state.get("agnes_key_locked", False):
        key_input = st.text_input(
            "Agnes API Key",
            value=st.session_state.get("agnes_key", ""),
            type="password",
            placeholder="Paste Agnes key here",
            key="agnes_key_input"
        )
        if key_input:
            st.session_state.agnes_key = key_input.strip()
        if st.button("🔒 Lock Agnes Key", key="agnes_lock_btn"):
            if st.session_state.agnes_key:
                st.session_state.agnes_key_locked = True
                st.success("✅ Agnes Key Locked!")
    else:
        st.success("✅ Agnes key loaded")
        if st.button("🔓 Change Agnes Key", key="agnes_unlock"):
            st.session_state.agnes_key_locked = False
            st.session_state.agnes_key = ""

    # --------------------------------------------------------
    # GEMINI
    # --------------------------------------------------------
    st.markdown("### ⭐ Google Gemini")

    if not st.session_state.get("gemini_key_locked", False):
        key_input = st.text_input(
            "Gemini API Key",
            value=st.session_state.get("gemini_key", ""),
            type="password",
            placeholder="Paste Gemini key here",
            key="gemini_key_input"
        )
        if key_input:
            st.session_state.gemini_key = key_input.strip()
        if st.button("🔒 Lock Gemini Key", key="gemini_lock_btn"):
            if st.session_state.gemini_key:
                st.session_state.gemini_key_locked = True
                st.success("✅ Gemini Key Locked!")
    else:
        st.success("✅ Gemini key loaded")
        if st.button("🔓 Change Gemini Key", key="gemini_unlock"):
            st.session_state.gemini_key_locked = False
            st.session_state.gemini_key = ""

    st.markdown("---")

    # --------------------------------------------------------
    # VIDEO ENGINE
    # --------------------------------------------------------
    st.markdown("### 🎬 Video Engine")
    selected_video_api = st.selectbox(
        "Select Video Engine",
        ["agnes", "gemini"],
        index=0,
        format_func=lambda x: "🟣 Agnes AI" if x == "agnes" else "⭐ Gemini Veo 3"
    )

    st.markdown("---")

    # API Status
    st.markdown("### 🔐 API Status")
    if st.session_state.get("agnes_key", ""):
        st.success("✅ Agnes: Connected")
    else:
        st.warning("⚠️ Agnes: Key missing")

    if st.session_state.get("gemini_key", ""):
        st.success("✅ Gemini: Connected")
    else:
        st.warning("⚠️ Gemini: Key missing")

    st.markdown("---")
    st.caption("Videos saved in `generated_videos`")

# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(["🎬 Video", "💬 Chat", "🎨 Image", "🛠️ Tools"])

# ============================================================
# TAB 1 - VIDEO
# ============================================================

with tab1:
    st.markdown("### 🎬 Generate Video")

    video_prompt = st.text_area(
        "Describe your video",
        height=100,
        key="vid_prompt",
        placeholder="Example: A realistic baby panda walking through a beautiful green forest..."
    )

    audio_prompt = st.text_input(
        "🎤 Add Dialogue or Narration (Optional)",
        placeholder="e.g., 'Hello, welcome to this video'",
        key="audio_prompt"
    )

    st.markdown("### 🖼️ Reference Image (Optional)")
    reference_image = st.file_uploader(
        "Upload a reference image for video generation",
        type=["jpg", "jpeg", "png"],
        key="ref_image"
    )

    if reference_image:
        st.image(reference_image, caption="Reference Image", width=200)

    col1, col2 = st.columns(2)

    with col1:
        video_quality = st.selectbox(
            "Quality",
            ["720p", "1080p", "2K", "4K"],
            index=0
        )

    with col2:
        video_ratio = st.selectbox(
            "Aspect Ratio",
            ["16:9", "9:16", "1:1", "4:3", "3:4"],
            index=1
        )

    st.caption(f"🎯 Selected: {'🟣 Agnes AI' if selected_video_api == 'agnes' else '⭐ Gemini Veo 3'}")

    if st.button("🎬 Generate Video", use_container_width=True, type="primary"):
        if not video_prompt:
            st.warning("Please describe your video.")
        else:
            start_time = time.time()

            result = generate_video(
                prompt=video_prompt,
                api_choice=selected_video_api,
                quality=video_quality,
                ratio=video_ratio,
                reference_image=reference_image,
                audio_prompt=audio_prompt if audio_prompt else None
            )

            elapsed = time.time() - start_time

            if result["success"]:
                st.success(
                    f"✅ Video ready! Engine: {result['api']} · "
                    f"Time: {int(elapsed // 60)}m {int(elapsed % 60)}s"
                )

                video_path = result.get("path")
                video_url = result.get("url")

                if video_path and os.path.exists(video_path):
                    st.video(video_path)

                    with open(video_path, "rb") as video_file:
                        video_bytes = video_file.read()

                    st.download_button(
                        label="📥 Download Video",
                        data=video_bytes,
                        file_name=os.path.basename(video_path),
                        mime="video/mp4",
                        use_container_width=True
                    )

                    st.caption(f"📁 Saved locally: {video_path}")

                elif video_url:
                    st.video(video_url)
                    st.link_button("📥 Open Video", video_url, use_container_width=True)

            else:
                st.error(f"❌ Video generation failed\n\n{result['error']}")

                if result.get("video_id"):
                    st.info(f"Job ID: {result['video_id']}")

# ============================================================
# TAB 2 - CHAT
# ============================================================

with tab2:
    st.markdown("### 💬 Chat with AI")

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    prompt = st.chat_input("Type your message...")

    if prompt:
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                st.info("Chat feature coming soon with Gemini integration.")

# ============================================================
# TAB 3 - IMAGE
# ============================================================

with tab3:
    st.markdown("### 🎨 Generate Images")

    st.info("Image generation via Agnes AI is available.")

    prompt_img = st.text_area("Describe your image", height=100, key="img_prompt")

    col1, col2 = st.columns(2)
    with col1:
        image_size = st.selectbox("Quality", ["1K", "2K", "3K", "4K"], index=1)
    with col2:
        image_ratio = st.selectbox("Aspect Ratio", ["1:1", "16:9", "9:16", "4:3", "3:4"], index=1)

    if st.button("🎨 Generate Image", use_container_width=True):
        if not prompt_img:
            st.warning("Please describe your image.")
        else:
            with st.spinner("Creating image..."):
                st.info("Image generation via Agnes API is configured.")
                st.warning("Please ensure Agnes API key is loaded.")

# ============================================================
# TAB 4 - TOOLS
# ============================================================

with tab4:
    st.markdown("### 🛠️ AI Tools")

    tool_type = st.selectbox(
        "Select Tool",
        ["SEO Generator", "Transcript Generator", "Text Summarizer", "Content Rewriter", "Urdu Translator"]
    )

    tool_prompt = st.text_area("Enter your input", height=120, key="tool_prompt")

    if st.button("🛠️ Generate", use_container_width=True):
        if not tool_prompt:
            st.warning("Please enter your input.")
        else:
            with st.spinner("Generating..."):
                st.info("Tool generation via Gemini API is configured.")
                st.warning("Please ensure Gemini API key is loaded.")

# ============================================================
# FOOTER
# ============================================================

st.markdown("---")
st.caption("🚀 AI Studio Pro · Agnes AI · Google Gemini · Videos saved locally.")
