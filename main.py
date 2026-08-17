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
# LOAD LOCAL .ENV
# ============================================================

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
    <p>🎬 Video · 🎨 Image · 💬 Chat · 🛠️ Tools</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SESSION STATE
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
# API CONFIGURATION
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
# API KEY FUNCTIONS - Secrets کو ترجیح
# ============================================================

def get_api_key(api_name):
    """
    پہلے Streamlit Secrets سے Key حاصل کریں۔
    اگر Secrets میں نہ ہو تو Sidebar سے لیں۔
    """
    # 1. پہلے Secrets سے چیک کریں
    try:
        if api_name == "agnes":
            secret_key = st.secrets.get("AGNES_API_KEY", "")
            if secret_key:
                return secret_key.strip()
        elif api_name == "gemini":
            secret_key = st.secrets.get("GEMINI_API_KEY", "")
            if secret_key:
                return secret_key.strip()
    except:
        pass
    
    # 2. اگر Secrets میں نہیں تو Sidebar سے لیں
    if api_name == "agnes":
        return st.session_state.get("agnes_key", "").strip()
    elif api_name == "gemini":
        return st.session_state.get("gemini_key", "").strip()
    return ""

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
# IMAGE GENERATION - AGNES
# ============================================================

def call_agnes_image(prompt, size="2K", ratio="16:9"):
    key = get_api_key("agnes")
    if not key:
        return {
            "success": False,
            "error": "❌ Agnes API key is missing. Please add key in sidebar or Secrets."
        }

    payload = {
        "model": APIS["agnes"]["models"]["image"],
        "prompt": prompt,
        "size": size,
        "ratio": ratio,
        "extra_body": {"response_format": "url"}
    }

    try:
        response = requests.post(
            f"{APIS['agnes']['base_url']}/images/generations",
            headers=make_headers("agnes"),
            json=payload,
            timeout=(15, 120)
        )
        if response.status_code == 200:
            data = response.json()
            url = data["data"][0]["url"]
            return {
                "success": True,
                "url": url,
                "api": "Agnes AI"
            }
        return {
            "success": False,
            "error": extract_error(response)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# ============================================================
# AGNES VIDEO
# ============================================================

def call_agnes_video(prompt, quality="720p", ratio="16:9", reference_image=None, audio_prompt=None, max_minutes=12):
    key = get_api_key("agnes")
    if not key:
        return {"success": False, "error": "❌ Agnes API key is missing."}

    ratio_map = {
        "1:1": (768, 768),
        "16:9": (1024, 576),
        "9:16": (576, 1024),
        "4:3": (896, 672),
        "3:4": (672, 896)
    }
    width, height = ratio_map.get(ratio, (1024, 576))

    quality_map = {"720p": "720p", "1080p": "1080p", "2K": "2K", "4K": "4K"}
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
            reference_image.seek(0)
            ref_image_data = reference_image.read()
            base64_image = base64.b64encode(ref_image_data).decode("utf-8")
            payload["image"] = base64_image
        except Exception as e:
            return {"success": False, "error": f"Error processing reference image: {str(e)}"}

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    start_url = f"{APIS['agnes']['base_url']}/videos"

    try:
        st.info("🚀 Sending video job to Agnes...")
        response = requests.post(start_url, headers=headers, json=payload, timeout=(20, 90))
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
            status_response = requests.get(status_url, headers={"Authorization": f"Bearer {key}"}, timeout=(15, 30))
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
            download_result = download_url_to_file(video_url, headers={"Authorization": f"Bearer {key}"})
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

def call_gemini_video(prompt, quality="720p", aspect_ratio="16:9", reference_image=None, audio_prompt=None, max_minutes=15):
    key = get_api_key("gemini")
    if not key:
        return {"success": False, "error": "❌ Gemini API key is missing."}

    quality_map = {"720p": "720p", "1080p": "1080p", "2K": "2K", "4K": "4K"}
    resolution = quality_map.get(quality, "720p")

    final_prompt = prompt
    if audio_prompt:
        final_prompt = f"{prompt}. Audio: {audio_prompt}"

    model = APIS["gemini"]["models"]["video"]
    url = f"{APIS['gemini']['base_url']}/models/{model}:predictLongRunning"
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}

    payload = {
        "instances": [{"prompt": final_prompt}],
        "parameters": {"aspectRatio": aspect_ratio, "resolution": resolution}
    }

    if reference_image:
        try:
            reference_image.seek(0)
            ref_image_data = reference_image.read()
            base64_image = base64.b64encode(ref_image_data).decode("utf-8")
            payload["instances"][0]["image"] = {"mime_type": "image/jpeg", "data": base64_image}
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
            status_response = requests.get(operation_url, headers={"x-goog-api-key": key}, timeout=(15, 45))
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
            download_result = download_url_to_file(video_uri, headers={"x-goog-api-key": key})
            progress_bar.empty()
            status_text.empty()
            if download_result["success"]:
                return {"success": True, "path": download_result["path"], "api": "Gemini Veo 3"}
            return {"success": False, "error": f"Download failed: {download_result['error']}"}

        estimated = min(95, (elapsed / (max_minutes * 60)) * 100)
        progress_bar.progress(max(1, int(estimated)))
        status_text.text(f"⏳ Gemini Veo 3 processing... {int(estimated)}% · {int(elapsed // 60)}m {int(elapsed % 60)}s")

# ============================================================
# GEMINI CHAT
# ============================================================

def call_gemini_chat(messages):
    key = get_api_key("gemini")
    if not key:
        return {"success": False, "error": "Gemini API key is missing."}

    formatted = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        formatted.append({"role": role, "parts": [{"text": msg["content"]}]})

    try:
        response = requests.post(
            f"{APIS['gemini']['base_url']}/models/{APIS['gemini']['models']['chat']}:generateContent",
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
            json={"contents": formatted},
            timeout=(15, 60)
        )
        if response.status_code == 200:
            data = response.json()
            result = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return {"success": True, "result": result, "api": "Google Gemini"}
        return {"success": False, "error": f"Gemini: {extract_error(response)}"}
    except Exception as e:
        return {"success": False, "error": f"Gemini: {str(e)}"}

# ============================================================
# AGNES CHAT
# ============================================================

def call_agnes_chat(messages):
    key = get_api_key("agnes")
    if not key:
        return {"success": False, "error": "Agnes API key is missing."}

    payload = {"model": APIS["agnes"]["models"]["chat"], "messages": messages}

    try:
        response = requests.post(
            f"{APIS['agnes']['base_url']}/chat/completions",
            headers=make_headers("agnes"),
            json=payload,
            timeout=(15, 60)
        )
        if response.status_code == 200:
            data = response.json()
            result = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"success": True, "result": result, "api": "Agnes AI"}
        return {"success": False, "error": f"Agnes: {extract_error(response)}"}
    except Exception as e:
        return {"success": False, "error": f"Agnes: {str(e)}"}

# ============================================================
# CHAT FALLBACK
# ============================================================

def chat_with_fallback(messages, selected_api):
    if selected_api == "agnes":
        return call_agnes_chat(messages)
    if selected_api == "gemini":
        return call_gemini_chat(messages)
    result = call_agnes_chat(messages)
    if result["success"]:
        return result
    return call_gemini_chat(messages)

# ============================================================
# GEMINI TOOLS - MULTI LANGUAGE TRANSLATOR
# ============================================================

def gemini_tool(prompt, tool_type, target_language="Urdu"):
    tool_prompts = {
        "seo": f"Generate SEO-optimized content for:\n{prompt}\n\nInclude SEO title, description, keywords, headings, and hashtags.",
        "transcript": f"Generate a clear transcript for:\n{prompt}\n\nInclude speaker labels and timestamps.",
        "summarize": f"Summarize this text in 3-5 bullet points:\n{prompt}",
        "rewrite": f"Rewrite this content to make it more professional, clear, and engaging:\n{prompt}",
        "translate": f"Translate the following text into {target_language}:\n{prompt}"
    }
    full_prompt = tool_prompts.get(tool_type, prompt)
    messages = [{"role": "user", "content": full_prompt}]
    return call_gemini_chat(messages)

# ============================================================
# MAIN VIDEO GENERATOR
# ============================================================

def generate_video(prompt, api_choice, quality="720p", ratio="16:9", reference_image=None, audio_prompt=None):
    if api_choice == "agnes":
        return call_agnes_video(prompt, quality, ratio, reference_image, audio_prompt)
    elif api_choice == "gemini":
        return call_gemini_video(prompt, quality, ratio, reference_image, audio_prompt)
    return {"success": False, "error": "Unknown video engine."}

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    # چیک کریں کہ کیا Secrets میں Keys ہیں
    agnes_in_secrets = False
    gemini_in_secrets = False
    try:
        if st.secrets.get("AGNES_API_KEY", ""):
            agnes_in_secrets = True
        if st.secrets.get("GEMINI_API_KEY", ""):
            gemini_in_secrets = True
    except:
        pass
    
    # اگر دونوں Keys Secrets میں ہیں تو API Settings نہ دکھائیں
    if agnes_in_secrets and gemini_in_secrets:
        st.success("✅ All API keys are securely stored in Secrets.")
    else:
        st.markdown("## ⚙️ API Settings")
        st.caption("🔐 Keys are locked after pressing Enter")

        # Agnes
        st.markdown("### 🟣 Agnes AI")
        if not st.session_state.get("agnes_key_locked", False):
            key_input = st.text_input("Agnes API Key", value=st.session_state.get("agnes_key", ""), type="password", placeholder="Paste Agnes key here", key="agnes_key_input")
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

        # Gemini
        st.markdown("### ⭐ Google Gemini")
        if not st.session_state.get("gemini_key_locked", False):
            key_input = st.text_input("Gemini API Key", value=st.session_state.get("gemini_key", ""), type="password", placeholder="Paste Gemini key here", key="gemini_key_input")
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

    # Video Engine (ہمیشہ دکھائیں)
    st.markdown("### 🎬 Video Engine")
    selected_video_api = st.selectbox("Select Video Engine", ["agnes", "gemini"], index=0, format_func=lambda x: "🟣 Agnes AI" if x == "agnes" else "⭐ Gemini Veo 3")

    # Chat Engine (ہمیشہ دکھائیں)
    st.markdown("### 🤖 Chat Engine")
    selected_chat_api = st.selectbox("Select Chat Engine", ["auto", "agnes", "gemini"], index=0, format_func=lambda x: "🔄 Auto" if x == "auto" else "🟣 Agnes AI" if x == "agnes" else "⭐ Gemini")

    st.markdown("---")

    # API Status (ہمیشہ دکھائیں)
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

    video_prompt = st.text_area("Describe your video", height=100, key="vid_prompt", placeholder="Example: A realistic baby panda walking through a beautiful green forest...")
    audio_prompt = st.text_input("🎤 Add Dialogue or Narration (Optional)", placeholder="e.g., 'Hello, welcome to this video'", key="audio_prompt")

    st.markdown("### 🖼️ Reference Image (Optional)")
    reference_image = st.file_uploader("Upload a reference image for video generation", type=["jpg", "jpeg", "png"], key="ref_image")
    if reference_image:
        st.image(reference_image, caption="Reference Image", width=200)

    col1, col2 = st.columns(2)
    with col1:
        video_quality = st.selectbox("Quality", ["720p", "1080p", "2K", "4K"], index=0)
    with col2:
        video_ratio = st.selectbox("Aspect Ratio", ["16:9", "9:16", "1:1", "4:3", "3:4"], index=1)

    st.caption(f"🎯 Selected: {'🟣 Agnes AI' if selected_video_api == 'agnes' else '⭐ Gemini Veo 3'}")

    if st.button("🎬 Generate Video", use_container_width=True, type="primary"):
        if not video_prompt:
            st.warning("Please describe your video.")
        else:
            start_time = time.time()
            result = generate_video(video_prompt, selected_video_api, video_quality, video_ratio, reference_image, audio_prompt if audio_prompt else None)
            elapsed = time.time() - start_time

            if result["success"]:
                st.success(f"✅ Video ready! Engine: {result['api']} · Time: {int(elapsed // 60)}m {int(elapsed % 60)}s")
                video_path = result.get("path")
                video_url = result.get("url")
                if video_path and os.path.exists(video_path):
                    st.video(video_path)
                    with open(video_path, "rb") as video_file:
                        video_bytes = video_file.read()
                    st.download_button(label="📥 Download Video", data=video_bytes, file_name=os.path.basename(video_path), mime="video/mp4", use_container_width=True)
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
                api_choice = None if selected_chat_api == "auto" else selected_chat_api
                result = chat_with_fallback(st.session_state.chat_messages, api_choice)
                if result["success"]:
                    st.caption(f"⚡ Used: {result['api']}")
                    st.write(result["result"])
                    st.session_state.chat_messages.append({"role": "assistant", "content": result["result"]})
                else:
                    st.error(f"❌ {result['error']}")

# ============================================================
# TAB 3 - IMAGE
# ============================================================

with tab3:
    st.markdown("### 🎨 Generate Images")

    prompt_img = st.text_area("Describe your image", height=100, key="img_prompt", placeholder="Example: A vibrant peacock in a mystical forest, golden sunlight, 8K")

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
                result = call_agnes_image(prompt_img, image_size, image_ratio)
            if result["success"]:
                st.image(result["url"], use_container_width=True)
                st.success(f"✅ Image generated! ({result['api']})")
            else:
                st.error(f"❌ {result['error']}")

# ============================================================
# TAB 4 - TOOLS
# ============================================================

with tab4:
    st.markdown("### 🛠️ AI Tools")

    tool_type = st.selectbox(
        "Select Tool",
        ["SEO Generator", "Transcript Generator", "Text Summarizer", "Content Rewriter", "Translator"]
    )

    target_language = "Urdu"
    if tool_type == "Translator":
        target_language = st.selectbox(
            "Select Target Language",
            [
                "Urdu", "English", "Hindi", "Arabic", "French",
                "Spanish", "German", "Chinese", "Japanese", "Russian", "Portuguese"
            ],
            index=0
        )

    tool_map = {
        "SEO Generator": "seo",
        "Transcript Generator": "transcript",
        "Text Summarizer": "summarize",
        "Content Rewriter": "rewrite",
        "Translator": "translate"
    }
    tool_key = tool_map.get(tool_type, "seo")

    tool_prompt = st.text_area(
        f"Enter your {tool_type.lower()} input",
        height=120,
        key="tool_prompt",
        placeholder="Type or paste your text here..."
    )

    if st.button("🛠️ Generate", use_container_width=True):
        if not tool_prompt:
            st.warning("Please enter your input.")
        else:
            with st.spinner("Generating..."):
                result = gemini_tool(tool_prompt, tool_key, target_language)
            if result["success"]:
                st.success("✅ Generated!")
                st.write(result["result"])
            else:
                st.error(f"❌ {result['error']}")

# ============================================================
# FOOTER
# ============================================================

st.markdown("---")
st.caption("🚀 AI Studio Pro · Agnes AI · Google Gemini · Videos saved locally.")
