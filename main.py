import streamlit as st
import requests
import time
import os
import base64
import uuid
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

# ============================================================
# CRAFTREEL AI - ALL-IN-ONE
# ============================================================

APP_NAME = "CraftReel AI"

OUTPUT_DIR = Path("generated_videos")
OUTPUT_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🎬",
    layout="wide"
)

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
    <h1>🎬 CraftReel AI</h1>
    <p>🎬 Video · 🎨 Image · 🖼️ BG Remover · 💬 Chat · 🛠️ Tools</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SESSION STATE
# ============================================================

if "agnes_key" not in st.session_state:
    st.session_state.agnes_key = ""

if "agnes_key_locked" not in st.session_state:
    st.session_state.agnes_key_locked = False

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
            "image_hd": "agnes-image-3.0-flash",
            "chat": "agnes-2.5-flash",
            "edit": "agnes-image-edit-v1"
        }
    }
}

# ============================================================
# API KEY FUNCTIONS
# ============================================================

def get_api_key():
    try:
        secret_key = st.secrets.get("AGNES_API_KEY", "")
        if secret_key:
            return secret_key.strip()
    except:
        pass
    return st.session_state.get("agnes_key", "").strip()

def make_headers():
    key = get_api_key()
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
# IMAGE GENERATION - TEXT TO IMAGE
# ============================================================

def call_agnes_image(prompt, size="2K", ratio="16:9"):
    key = get_api_key()
    if not key:
        return {"success": False, "error": "❌ Agnes API key is missing."}

    payload = {
        "model": APIS["agnes"]["models"]["image_hd"],
        "prompt": prompt,
        "size": size,
        "ratio": ratio,
        "extra_body": {"response_format": "url"}
    }

    try:
        response = requests.post(
            f"{APIS['agnes']['base_url']}/images/generations",
            headers=make_headers(),
            json=payload,
            timeout=(15, 120)
        )
        if response.status_code == 200:
            data = response.json()
            url = data["data"][0]["url"]
            return {"success": True, "url": url, "api": "Agnes AI HD"}
        return {"success": False, "error": extract_error(response)}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================================
# BACKGROUND REMOVER - IMAGE TO IMAGE
# ============================================================

def remove_background(image_data):
    key = get_api_key()
    if not key:
        return {"success": False, "error": "❌ Agnes API key is missing."}

    try:
        image = Image.open(image_data)
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        return {"success": False, "error": f"Error processing image: {str(e)}"}

    payload = {
        "model": APIS["agnes"]["models"]["edit"],
        "prompt": "Remove background, transparent background, no background, keep only the main subject",
        "image": base64_image,
        "mode": "background_removal"
    }

    try:
        response = requests.post(
            f"{APIS['agnes']['base_url']}/images/edits",
            headers=make_headers(),
            json=payload,
            timeout=(15, 60)
        )
        if response.status_code == 200:
            data = response.json()
            url = data["data"][0]["url"]
            return {"success": True, "url": url}
        return {"success": False, "error": f"Error: {extract_error(response)}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================================
# AGNES VIDEO
# ============================================================

def call_agnes_video(prompt, quality="720p", ratio="16:9", reference_image=None, audio_prompt=None, max_minutes=12):
    key = get_api_key()
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

    smooth_progress = 0

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

        # ====================================================
        # TIME-BASED SMOOTH PROGRESS BAR
        # ====================================================

        if elapsed < 15:
            smooth_progress = (elapsed / 15) * 25
        elif elapsed < 45:
            smooth_progress = 25 + ((elapsed - 15) / 30) * 30
        elif elapsed < 90:
            smooth_progress = 55 + ((elapsed - 45) / 45) * 25
        elif elapsed < 150:
            smooth_progress = 80 + ((elapsed - 90) / 60) * 15
        else:
            smooth_progress = min(99, 95 + (elapsed - 150) / 30)

        progress_bar.progress(min(100, int(smooth_progress)))

        # ====================================================

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

        if smooth_progress is not None:
            status_text.text(f"⏳ Agnes generating video... {int(smooth_progress)}% · {int(elapsed // 60)}m {int(elapsed % 60)}s")

# ============================================================
# AGNES CHAT
# ============================================================

def call_agnes_chat(messages):
    key = get_api_key()
    if not key:
        return {"success": False, "error": "Agnes API key is missing."}

    payload = {"model": APIS["agnes"]["models"]["chat"], "messages": messages}

    try:
        response = requests.post(
            f"{APIS['agnes']['base_url']}/chat/completions",
            headers=make_headers(),
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
# GEMINI TOOLS (Using Agnes Chat)
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
    return call_agnes_chat(messages)

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("## ⚙️ API Settings")
    st.caption("🔐 Keys are locked after pressing Enter")

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

    st.markdown("---")

    st.markdown("### 🔐 API Status")
    if get_api_key():
        st.success("✅ Agnes: Connected")
    else:
        st.warning("⚠️ Agnes: Key missing")

    st.markdown("---")
    st.caption("Videos saved in `generated_videos`")

# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎬 Video", "🎨 Image", "🖼️ BG Remover", "💬 Chat", "🛠️ Tools"])

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

    if st.button("🎬 Generate Video", use_container_width=True, type="primary"):
        if not video_prompt:
            st.warning("Please describe your video.")
        else:
            start_time = time.time()
            result = call_agnes_video(video_prompt, video_quality, video_ratio, reference_image, audio_prompt if audio_prompt else None)
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
# TAB 2 - IMAGE (Text-to-Image)
# ============================================================

with tab2:
    st.markdown("### 🎨 Generate Images")

    st.info("✨ Create HD images from text descriptions")

    prompt_img = st.text_area("Describe your image", height=100, key="img_prompt", placeholder="Example: A vibrant peacock in a mystical forest, golden sunlight, 8K")

    col1, col2 = st.columns(2)
    with col1:
        image_size = st.selectbox("Quality", ["1K", "2K", "3K", "4K"], index=2)
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
# TAB 3 - BACKGROUND REMOVER (Image-to-Image)
# ============================================================

with tab3:
    st.markdown("### 🖼️ Background Remover")

    st.info("Remove background from any image instantly")

    uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"], key="bg_uploader")

    if uploaded_file:
        col1, col2 = st.columns(2)

        with col1:
            st.image(uploaded_file, caption="Original Image", use_container_width=True)

        if st.button("🖼️ Remove Background", use_container_width=True, type="primary"):
            with st.spinner("Removing background..."):
                result = remove_background(uploaded_file)

            if result["success"]:
                with col2:
                    st.image(result["url"], caption="Background Removed", use_container_width=True)
                    st.download_button(
                        label="📥 Download Image",
                        data=requests.get(result["url"]).content,
                        file_name="no_bg.png",
                        mime="image/png",
                        use_container_width=True
                    )
                st.success("✅ Background removed successfully!")
            else:
                st.error(f"❌ {result['error']}")

# ============================================================
# TAB 4 - CHAT
# ============================================================

with tab4:
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
                result = call_agnes_chat(st.session_state.chat_messages)
                if result["success"]:
                    st.caption(f"⚡ Used: {result['api']}")
                    st.write(result["result"])
                    st.session_state.chat_messages.append({"role": "assistant", "content": result["result"]})
                else:
                    st.error(f"❌ {result['error']}")

# ============================================================
# TAB 5 - TOOLS
# ============================================================

with tab5:
    st.markdown("### 🛠️ AI Tools")

    tool_type = st.selectbox(
        "Select Tool",
        ["SEO Generator", "Transcript Generator", "Text Summarizer", "Content Rewriter", "Translator"]
    )

    target_language = "Urdu"
    if tool_type == "Translator":
        target_language = st.selectbox(
            "Select Target Language",
            ["Urdu", "English", "Hindi", "Arabic", "French", "Spanish", "German", "Chinese", "Japanese", "Russian", "Portuguese"],
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

    tool_prompt = st.text_area(f"Enter your {tool_type.lower()} input", height=120, key="tool_prompt", placeholder="Type or paste your text here...")

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
st.caption("🎬 CraftReel AI · Powered by Agnes AI · Videos & Images saved locally.")
