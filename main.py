import streamlit as st
import sys

# یہ ڈیبگ لائنز ہیں
st.write("✅ Step 1: App started successfully")
sys.stdout.flush()

import streamlit as st
import requests
import time
import os
import base64
import uuid
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv

# ============================================================
# AI STUDIO PRO - STABLE VERSION
# ============================================================

load_dotenv()

APP_NAME = "AI Studio Pro"
OUTPUT_DIR = Path("generated_videos")
OUTPUT_DIR.mkdir(exist_ok=True)

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
# SAFE SECRET / ENV HELPERS
# ============================================================

def read_secret(*names):
    """Read a secret safely from Streamlit Cloud Secrets or .env."""
    try:
        for name in names:
            try:
                value = st.secrets[name]
                if value is not None and str(value).strip():
                    return str(value).strip()
            except Exception:
                pass
    except Exception:
        pass

    for name in names:
        value = os.getenv(name, "")
        if value and value.strip():
            return value.strip()

    return ""

# ============================================================
# SESSION STATE
# ============================================================

# IMPORTANT:
# The real API keys are stored separately from the text-input widgets.
# This prevents a Streamlit rerun after video generation from clearing them.

if "agnes_key" not in st.session_state:
    st.session_state.agnes_key = read_secret(
        "AGNES_API_KEY",
        "AGNES_KEY"
    )

if "gemini_key" not in st.session_state:
    st.session_state.gemini_key = read_secret(
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_KEY"
    )

if "agnes_locked" not in st.session_state:
    st.session_state.agnes_locked = bool(
        st.session_state.agnes_key
    )

if "gemini_locked" not in st.session_state:
    st.session_state.gemini_locked = bool(
        st.session_state.gemini_key
    )

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# ============================================================
# API CONFIG
# ============================================================

APIS = {
    "agnes": {
        "name": "Agnes AI",
        "base_url": "https://apihub.agnes-ai.cn/v1",
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
# KEY HELPERS
# ============================================================

def get_api_key(api_name):
    if api_name == "agnes":
        return str(st.session_state.get("agnes_key", "")).strip()
    if api_name == "gemini":
        return str(st.session_state.get("gemini_key", "")).strip()
    return ""

def save_agnes_from_input():
    value = st.session_state.get("agnes_input", "").strip()
    if value:
        st.session_state.agnes_key = value

def save_gemini_from_input():
    value = st.session_state.get("gemini_input", "").strip()
    if value:
        st.session_state.gemini_key = value

def lock_agnes():
    value = st.session_state.get("agnes_input", "").strip()
    if value:
        st.session_state.agnes_key = value
        st.session_state.agnes_locked = True

def lock_gemini():
    value = st.session_state.get("gemini_input", "").strip()
    if value:
        st.session_state.gemini_key = value
        st.session_state.gemini_locked = True

def unlock_agnes():
    st.session_state.agnes_locked = False
    st.session_state.agnes_key = ""
    st.session_state.pop("agnes_input", None)

def unlock_gemini():
    st.session_state.gemini_locked = False
    st.session_state.gemini_key = ""
    st.session_state.pop("gemini_input", None)

# ============================================================
# ERROR HELPER
# ============================================================

def extract_error(response):
    try:
        data = response.json()

        if isinstance(data, dict):
            error = data.get("error")

            if error:
                if isinstance(error, dict):
                    return (
                        error.get("message")
                        or error.get("detail")
                        or str(error)
                    )
                return str(error)

            if data.get("message"):
                return str(data["message"])

            if data.get("detail"):
                return str(data["detail"])

        text = response.text.strip()
        if text:
            return text[:1500]

    except Exception:
        pass

    return f"HTTP {response.status_code}"

# ============================================================
# DOWNLOAD
# ============================================================

def download_url_to_file(url, filename=None, headers=None):
    if not filename:
        filename = (
            f"video_{time.strftime('%Y%m%d_%H%M%S')}_"
            f"{uuid.uuid4().hex[:6]}.mp4"
        )

    path = OUTPUT_DIR / filename

    try:
        with requests.get(
            url,
            headers=headers or {},
            stream=True,
            timeout=(20, 900)
        ) as response:

            if response.status_code != 200:
                return {
                    "success": False,
                    "error": extract_error(response)
                }

            with open(path, "wb") as f:
                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        f.write(chunk)

        return {
            "success": True,
            "path": str(path)
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# ============================================================
# AGNES VIDEO
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
            "error": (
                "❌ Agnes API key is missing. "
                "Add it in Sidebar or Streamlit Secrets."
            )
        }

    ratio_map = {
        "1:1": (768, 768),
        "16:9": (1024, 576),
        "9:16": (576, 1024),
        "4:3": (896, 672),
        "3:4": (672, 896)
    }

    width, height = ratio_map.get(ratio, (1024, 576))

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
        "quality": quality
    }

    if reference_image:
        try:
            reference_image.seek(0)
            image_data = reference_image.read()
            payload["image"] = base64.b64encode(
                image_data
            ).decode("utf-8")
        except Exception as e:
            return {
                "success": False,
                "error": f"Reference image error: {e}"
            }

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
            return {
                "success": False,
                "error": "Agnes rate limit. Try again later."
            }

        if response.status_code not in (200, 201, 202):
            return {
                "success": False,
                "error": (
                    "Agnes start error: "
                    + extract_error(response)
                )
            }

        data = response.json()

        video_id = (
            data.get("video_id")
            or data.get("id")
            or data.get("job_id")
        )

        if not video_id:
            return {
                "success": False,
                "error": "Agnes did not return a video/job ID."
            }

        st.success(f"✅ Agnes job started: {video_id}")

    except Exception as e:
        return {
            "success": False,
            "error": f"Agnes start error: {e}"
        }

    # Kept from the user's previously working Localhost version.
    status_url = (
        "https://apihub.agnes-ai.com/agnesapi"
        f"?video_id={quote(str(video_id))}"
    )

    progress_bar = st.progress(0)
    status_text = st.empty()

    started_at = time.time()
    poll_count = 0

    while True:
        elapsed = time.time() - started_at

        if elapsed > max_minutes * 60:
            progress_bar.empty()
            status_text.empty()
            return {
                "success": False,
                "error": f"Agnes job exceeded {max_minutes} minutes.",
                "video_id": video_id
            }

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
        except Exception:
            status_text.warning(
                "⚠️ Agnes status request failed. Retrying..."
            )
            continue

        if status_response.status_code != 200:
            continue

        try:
            status_data = status_response.json()
        except Exception:
            continue

        actual_error = status_data.get("error")
        internal_status = str(
            status_data.get("internal_status", "")
        ).lower()
        external_status = str(
            status_data.get("status", "")
        ).lower()

        if actual_error not in (None, "", {}, []):
            progress_bar.empty()
            status_text.empty()
            return {
                "success": False,
                "error": f"Agnes error: {actual_error}",
                "video_id": video_id
            }

        failed = {
            "failed",
            "failure",
            "cancelled",
            "canceled",
            "error",
            "expired"
        }

        if internal_status in failed or external_status in failed:
            progress_bar.empty()
            status_text.empty()
            return {
                "success": False,
                "error": (
                    "Agnes job failed: "
                    f"{internal_status or external_status}"
                ),
                "video_id": video_id
            }

        progress = status_data.get("progress")

        if isinstance(progress, (int, float)):
            progress = max(0, min(100, progress))
            progress_bar.progress(int(progress))

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
            status_text.success(
                "✅ Agnes video ready. Downloading..."
            )

            result = download_url_to_file(
                video_url,
                headers={"Authorization": f"Bearer {key}"}
            )

            progress_bar.empty()
            status_text.empty()

            if result["success"]:
                return {
                    "success": True,
                    "path": result["path"],
                    "api": "Agnes AI",
                    "video_id": video_id
                }

            # If the API URL is usable but download fails,
            # still return it to the UI.
            return {
                "success": True,
                "url": video_url,
                "api": "Agnes AI",
                "video_id": video_id
            }

        if progress is not None:
            status_text.text(
                f"⏳ Agnes generating video... "
                f"{int(progress)}% · "
                f"{int(elapsed // 60)}m "
                f"{int(elapsed % 60)}s"
            )
        else:
            status_text.text(
                "⏳ Agnes generating video... "
                f"{int(elapsed // 60)}m "
                f"{int(elapsed % 60)}s"
            )

# ============================================================
# GEMINI VEO VIDEO
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
            "error": (
                "❌ Gemini API key is missing. "
                "Add it in Sidebar or Streamlit Secrets."
            )
        }

    final_prompt = prompt
    if audio_prompt:
        final_prompt = f"{prompt}. Audio: {audio_prompt}"

    model = APIS["gemini"]["models"]["video"]

    url = (
        f"{APIS['gemini']['base_url']}/models/"
        f"{model}:predictLongRunning"
    )

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": key
    }

    payload = {
        "instances": [{"prompt": final_prompt}],
        "parameters": {
            "aspectRatio": aspect_ratio,
            "resolution": quality
        }
    }

    if reference_image:
        try:
            reference_image.seek(0)
            image_data = reference_image.read()

            payload["instances"][0]["image"] = {
                "mime_type": reference_image.type or "image/jpeg",
                "data": base64.b64encode(
                    image_data
                ).decode("utf-8")
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Reference image error: {e}"
            }

    try:
        st.info("🚀 Sending video job to Gemini Veo 3...")

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=(20, 90)
        )

        if response.status_code not in (200, 201, 202):
            return {
                "success": False,
                "error": (
                    "Gemini start error: "
                    + extract_error(response)
                )
            }

        data = response.json()
        operation_name = data.get("name")

        if not operation_name:
            return {
                "success": False,
                "error": (
                    "Gemini did not return an operation name."
                )
            }

        st.success("✅ Gemini video job started.")

    except Exception as e:
        return {
            "success": False,
            "error": f"Gemini start error: {e}"
        }

    progress_bar = st.progress(0)
    status_text = st.empty()
    started_at = time.time()

    while True:
        elapsed = time.time() - started_at

        if elapsed > max_minutes * 60:
            progress_bar.empty()
            status_text.empty()
            return {
                "success": False,
                "error": (
                    f"Gemini job exceeded {max_minutes} minutes."
                ),
                "operation": operation_name
            }

        time.sleep(8)

        operation_url = (
            f"{APIS['gemini']['base_url']}/"
            f"{operation_name}"
        )

        try:
            status_response = requests.get(
                operation_url,
                headers={"x-goog-api-key": key},
                timeout=(15, 45)
            )
        except Exception:
            status_text.warning(
                "⚠️ Gemini status timeout. Retrying..."
            )
            continue

        if status_response.status_code != 200:
            continue

        try:
            status_data = status_response.json()
        except Exception:
            continue

        if status_data.get("error"):
            progress_bar.empty()
            status_text.empty()
            return {
                "success": False,
                "error": (
                    "Gemini video job failed: "
                    f"{status_data.get('error')}"
                )
            }

        if status_data.get("done", False):
            response_data = status_data.get("response", {})
            generated = response_data.get(
                "generateVideoResponse",
                {}
            )

            samples = generated.get(
                "generatedSamples",
                []
            )

            if not samples:
                samples = response_data.get(
                    "generatedVideos",
                    []
                )

            video_uri = None

            if samples:
                first = samples[0]

                if isinstance(first, dict):
                    video_obj = first.get("video", {})

                    if isinstance(video_obj, dict):
                        video_uri = video_obj.get("uri")

            if not video_uri:
                progress_bar.empty()
                status_text.empty()
                return {
                    "success": False,
                    "error": (
                        "Gemini finished but no video URI was found."
                    )
                }

            progress_bar.progress(100)
            status_text.info(
                "📥 Gemini video ready. Downloading..."
            )

            result = download_url_to_file(
                video_uri,
                headers={"x-goog-api-key": key}
            )

            progress_bar.empty()
            status_text.empty()

            if result["success"]:
                return {
                    "success": True,
                    "path": result["path"],
                    "api": "Gemini Veo 3"
                }

            return {
                "success": False,
                "error": (
                    "Download failed: "
                    f"{result['error']}"
                )
            }

        estimated = min(
            95,
            (elapsed / (max_minutes * 60)) * 100
        )

        progress_bar.progress(
            max(1, int(estimated))
        )

        status_text.text(
            f"⏳ Gemini Veo 3 processing... "
            f"{int(estimated)}% · "
            f"{int(elapsed // 60)}m "
            f"{int(elapsed % 60)}s"
        )

# ============================================================
# VIDEO ROUTER
# ============================================================

def generate_video(
    prompt,
    api_choice,
    quality="720p",
    ratio="16:9",
    reference_image=None,
    audio_prompt=None
):
    if api_choice == "agnes":
        return call_agnes_video(
            prompt,
            quality=quality,
            ratio=ratio,
            reference_image=reference_image,
            audio_prompt=audio_prompt
        )

    if api_choice == "gemini":
        return call_gemini_video(
            prompt,
            quality=quality,
            aspect_ratio=ratio,
            reference_image=reference_image,
            audio_prompt=audio_prompt
        )

    return {
        "success": False,
        "error": "Unknown video engine."
    }

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("## ⚙️ API Settings")
    st.caption(
        "Keys stay available during the current session. "
        "Cloud Secrets load automatically."
    )

    # --------------------------------------------------------
    # AGNES
    # --------------------------------------------------------

    st.markdown("### 🟣 Agnes AI")

    if st.session_state.agnes_locked:
        st.success("✅ Agnes key loaded")

        if st.button(
            "🔓 Change Agnes Key",
            key="agnes_change"
        ):
            unlock_agnes()
            st.rerun()

    else:
        st.text_input(
            "Agnes API Key",
            type="password",
            key="agnes_input",
            on_change=save_agnes_from_input,
            placeholder="Paste Agnes key here"
        )

        if st.button(
            "🔒 Lock Agnes Key",
            key="agnes_lock"
        ):
            value = st.session_state.get(
                "agnes_input", ""
            ).strip()

            if value:
                st.session_state.agnes_key = value
                st.session_state.agnes_locked = True
                st.rerun()
            else:
                st.warning("Please enter Agnes API key first.")

    # --------------------------------------------------------
    # GEMINI
    # --------------------------------------------------------

    st.markdown("### ⭐ Google Gemini")

    if st.session_state.gemini_locked:
        st.success("✅ Gemini key loaded")

        if st.button(
            "🔓 Change Gemini Key",
            key="gemini_change"
        ):
            unlock_gemini()
            st.rerun()

    else:
        st.text_input(
            "Gemini API Key",
            type="password",
            key="gemini_input",
            on_change=save_gemini_from_input,
            placeholder="Paste Gemini key here"
        )

        if st.button(
            "🔒 Lock Gemini Key",
            key="gemini_lock"
        ):
            value = st.session_state.get(
                "gemini_input", ""
            ).strip()

            if value:
                st.session_state.gemini_key = value
                st.session_state.gemini_locked = True
                st.rerun()
            else:
                st.warning("Please enter Gemini API key first.")

    st.markdown("---")

    # --------------------------------------------------------
    # VIDEO ENGINE
    # --------------------------------------------------------

    st.markdown("### 🎬 Video Engine")

    selected_video_api = st.selectbox(
        "Select Video Engine",
        ["agnes", "gemini"],
        format_func=lambda x:
            "🟣 Agnes AI"
            if x == "agnes"
            else "⭐ Gemini Veo 3",
        key="video_engine"
    )

    st.markdown("---")

    # --------------------------------------------------------
    # API STATUS
    # --------------------------------------------------------

    st.markdown("### 🔐 API Status")

    if get_api_key("agnes"):
        st.success("✅ Agnes: Connected")
    else:
        st.warning("⚠️ Agnes: Key missing")

    if get_api_key("gemini"):
        st.success("✅ Gemini: Connected")
    else:
        st.warning("⚠️ Gemini: Key missing")

    st.markdown("---")
    st.caption("Videos saved in generated_videos")

# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    ["🎬 Video", "💬 Chat", "🎨 Image", "🛠️ Tools"]
)

# ============================================================
# VIDEO TAB
# ============================================================

with tab1:
    st.markdown("### 🎬 Generate Video")

    video_prompt = st.text_area(
        "Describe your video",
        height=100,
        key="vid_prompt",
        placeholder=(
            "Example: A realistic baby panda walking "
            "through a beautiful green forest..."
        )
    )

    audio_prompt = st.text_input(
        "🎤 Add Dialogue or Narration (Optional)",
        placeholder="e.g., Hello, welcome to this video",
        key="audio_prompt"
    )

    st.markdown("### 🖼️ Reference Image (Optional)")

    reference_image = st.file_uploader(
        "Upload a reference image for video generation",
        type=["jpg", "jpeg", "png"],
        key="ref_image"
    )

    if reference_image:
        st.image(
            reference_image,
            caption="Reference Image",
            width=200
        )

    col1, col2 = st.columns(2)

    with col1:
        video_quality = st.selectbox(
            "Quality",
            ["720p", "1080p", "2K", "4K"],
            index=0,
            key="video_quality"
        )

    with col2:
        video_ratio = st.selectbox(
            "Aspect Ratio",
            ["16:9", "9:16", "1:1", "4:3", "3:4"],
            index=1,
            key="video_ratio"
        )

    st.caption(
        "🎯 Selected: "
        + (
            "🟣 Agnes AI"
            if selected_video_api == "agnes"
            else "⭐ Gemini Veo 3"
        )
    )

    if st.button(
        "🎬 Generate Video",
        use_container_width=True,
        type="primary",
        key="generate_video_button"
    ):
        if not video_prompt.strip():
            st.warning("Please describe your video.")

        elif not get_api_key(selected_video_api):
            st.error(
                "❌ API key is missing. "
                "Please add the selected engine key."
            )

        else:
            start_time = time.time()

            result = generate_video(
                prompt=video_prompt,
                api_choice=selected_video_api,
                quality=video_quality,
                ratio=video_ratio,
                reference_image=reference_image,
                audio_prompt=audio_prompt or None
            )

            elapsed = time.time() - start_time

            if result.get("success"):
                st.success(
                    f"✅ Video ready! "
                    f"Engine: {result.get('api', selected_video_api)} · "
                    f"Time: {int(elapsed // 60)}m "
                    f"{int(elapsed % 60)}s"
                )

                video_path = result.get("path")
                video_url = result.get("url")

                if video_path and os.path.exists(video_path):
                    st.video(video_path)

                    with open(video_path, "rb") as f:
                        video_bytes = f.read()

                    st.download_button(
                        "📥 Download Video",
                        data=video_bytes,
                        file_name=os.path.basename(video_path),
                        mime="video/mp4",
                        use_container_width=True,
                        key="download_video"
                    )

                elif video_url:
                    st.video(video_url)
                    st.link_button(
                        "📥 Open Video",
                        video_url,
                        use_container_width=True
                    )

            else:
                st.error(
                    "❌ Video generation failed\n\n"
                    + str(result.get("error", "Unknown error"))
                )

                if result.get("video_id"):
                    st.info(
                        f"Job ID: {result['video_id']}"
                    )

# ============================================================
# CHAT TAB
# ============================================================

with tab2:
    st.markdown("### 💬 Chat with AI")

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    prompt = st.chat_input("Type your message...")

    if prompt:
        st.session_state.chat_messages.append(
            {"role": "user", "content": prompt}
        )

        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            st.info(
                "Chat feature is not connected yet. "
                "The Gemini key is available for future integration."
            )

# ============================================================
# IMAGE TAB
# ============================================================

with tab3:
    st.markdown("### 🎨 Generate Images")

    st.info(
        "Image UI is ready. The current code keeps "
        "the existing Agnes image placeholder."
    )

    prompt_img = st.text_area(
        "Describe your image",
        height=100,
        key="img_prompt"
    )

    col1, col2 = st.columns(2)

    with col1:
        st.selectbox(
            "Quality",
            ["1K", "2K", "3K", "4K"],
            index=1,
            key="image_quality"
        )

    with col2:
        st.selectbox(
            "Aspect Ratio",
            ["1:1", "16:9", "9:16", "4:3", "3:4"],
            index=1,
            key="image_ratio"
        )

    if st.button(
        "🎨 Generate Image",
        use_container_width=True,
        key="generate_image_button"
    ):
        if not prompt_img.strip():
            st.warning("Please describe your image.")
        elif not get_api_key("agnes"):
            st.warning("Please add Agnes API key first.")
        else:
            st.info(
                "Image generation endpoint is not implemented "
                "in the original application yet."
            )

# ============================================================
# TOOLS TAB
# ============================================================

with tab4:
    st.markdown("### 🛠️ AI Tools")

    st.selectbox(
        "Select Tool",
        [
            "SEO Generator",
            "Transcript Generator",
            "Text Summarizer",
            "Content Rewriter",
            "Urdu Translator"
        ],
        key="tool_type"
    )

    tool_prompt = st.text_area(
        "Enter your input",
        height=120,
        key="tool_prompt"
    )

    if st.button(
        "🛠️ Generate",
        use_container_width=True,
        key="generate_tool_button"
    ):
        if not tool_prompt.strip():
            st.warning("Please enter your input.")
        elif not get_api_key("gemini"):
            st.warning("Please add Gemini API key first.")
        else:
            st.info(
                "Tool generation endpoint is not implemented "
                "in the original application yet."
            )

# ============================================================
# FOOTER
# ============================================================

st.markdown("---")
st.caption(
    "🚀 AI Studio Pro · Agnes AI · Google Gemini · "
    "Videos saved locally."
)

