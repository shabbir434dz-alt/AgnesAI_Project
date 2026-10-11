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

# Magic Hour SDK
from magic_hour import Client as MagicHourClient

load_dotenv()

# ============================================================
# CRAFTREEL AI - VIDEO GENERATOR (Magic Hour + Agnes AI)
# ============================================================

APP_NAME = "CraftReel AI"

OUTPUT_DIR = Path("generated_videos")
OUTPUT_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🎬",
    layout="wide"
)

# ============================================================
# CUSTOM CSS
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
.main-header h1 { font-size: 2.4rem; margin: 0; }
.main-header p { font-size: 1rem; opacity: 0.9; margin-top: 0.5rem; }
.stButton > button { font-weight: bold; border-radius: 8px; }
.download-btn {
    background-color: #4CAF50;
    color: white !important;
    padding: 12px 20px;
    border-radius: 8px;
    text-align: center;
    font-size: 16px;
    cursor: pointer;
    text-decoration: none !important;
    display: block;
    width: 100%;
    box-sizing: border-box;
    margin-top: 10px;
    font-weight: bold;
}
.download-btn:hover { background-color: #45a049; color: white !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER
# ============================================================

st.markdown("""
<div class="main-header">
    <h1>🎬 CraftReel AI</h1>
    <p>🎬 Video (Magic Hour) · 🎨 Image · 💬 Chat · 🛠️ Tools (Agnes AI)</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SESSION STATE
# ============================================================

if "agnes_key" not in st.session_state:
    st.session_state.agnes_key = ""

if "agnes_key_locked" not in st.session_state:
    st.session_state.agnes_key_locked = False

if "magic_hour_key" not in st.session_state:
    st.session_state.magic_hour_key = ""

if "magic_hour_key_locked" not in st.session_state:
    st.session_state.magic_hour_key_locked = False

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# ============================================================
# API CONFIGURATION
# ============================================================

# Agnes AI (Image, Chat, SEO)
APIS = {
    "agnes": {
        "name": "Agnes AI",
        "base_url": "https://apihub.agnes-ai.cn/v1",
        "models": {
            "image": "agnes-image-2.1-flash",
            "image_hd": "agnes-image-2.1-flash",
            "chat": "agnes-2.5-flash",
            "edit": "agnes-image-edit-v1"
        }
    }
}

# Magic Hour (Video)
MAGIC_HOUR_VIDEO_MODEL = "ltx-2.5"
MAGIC_HOUR_VIDEO_RESOLUTION = "480p"
MAX_PROMPT_LENGTH = 2000  # ✅ Magic Hour کی حد

# ============================================================
# API KEY FUNCTIONS
# ============================================================

def get_agnes_key():
    try:
        secret_key = st.secrets.get("AGNES_API_KEY", "")
        if secret_key:
            return secret_key.strip()
    except Exception:
        pass
    return st.session_state.get("agnes_key", "").strip()


def get_magic_hour_key():
    try:
        secret_key = st.secrets.get("MAGIC_HOUR_API_KEY", "")
        if secret_key:
            return secret_key.strip()
    except Exception:
        pass
    return st.session_state.get("magic_hour_key", "").strip()


def make_agnes_headers():
    key = get_agnes_key()
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

# ============================================================
# PROMPT LENGTH HELPER ✅
# ============================================================

def truncate_prompt(prompt, max_length=MAX_PROMPT_LENGTH):
    """
    پرامپٹ کو مخصوص لمبائی تک محدود کریں۔
    اگر پرامپٹ لمبا ہو تو صاف پیغام کے ساتھ مختصر کر دیں۔
    """
    if not prompt:
        return "", False
    if len(prompt) <= max_length:
        return prompt, False
    return prompt[:max_length], True

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
                    return (error.get("message") or error.get("detail") or str(error))
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
# ANDROID DOWNLOAD LINK
# ============================================================

def android_download_link(url, label="⬇️ Download"):
    if not url:
        return ""
    encoded_url = quote(str(url), safe="")
    return (
        f'<a href="craftreel-download://download?url={encoded_url}" '
        f'class="download-btn">{label}</a>'
    )

# ============================================================
# DOWNLOAD VIDEO TO STREAMLIT SERVER
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
                return {"success": False, "error": extract_error(response)}
            with open(path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file.write(chunk)
        return {"success": True, "path": str(path)}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================================
# AGNES IMAGE GENERATION
# ============================================================

def call_agnes_image(prompt, size="2K", ratio="16:9"):
    key = get_agnes_key()
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
            headers=make_agnes_headers(),
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
# MAGIC HOUR VIDEO — TEXT TO VIDEO  ✅ پرامپٹ لینتھ فکس
# ============================================================

def call_magic_hour_text_to_video(
    prompt,
    duration=5,
    aspect_ratio="16:9",
    resolution="480p"
):
    key = get_magic_hour_key()
    if not key:
        return {"success": False, "error": "❌ Magic Hour API key is missing."}

    # ✅ پرامپٹ کی لمبائی چیک کریں
    prompt, was_truncated = truncate_prompt(prompt, MAX_PROMPT_LENGTH)
    if not prompt:
        return {"success": False, "error": "❌ پرامپٹ خالی ہے۔"}
    if was_truncated:
        st.warning(
            f"⚠️ پرامپٹ بہت لمبا تھا اور اسے {MAX_PROMPT_LENGTH} حروف "
            f"تک مختصر کر دیا گیا ہے۔"
        )

    try:
        client = MagicHourClient(token=key)
        res = client.v1.text_to_video.generate(
            end_seconds=float(duration),
            aspect_ratio=aspect_ratio,
            style={"prompt": prompt},
            name="CraftReel AI Video",
            resolution=resolution,
            model=MAGIC_HOUR_VIDEO_MODEL,
            wait_for_completion=True,
            download_outputs=False
        )

        video_url = None
        if hasattr(res, 'downloads') and res.downloads:
            first = res.downloads[0]
            video_url = first.url if hasattr(first, 'url') else str(first)
        elif hasattr(res, 'output') and res.output:
            video_url = res.output.url if hasattr(res.output, 'url') else str(res.output)
        elif isinstance(res, dict):
            downloads = res.get("downloads") or []
            if downloads and isinstance(downloads[0], dict):
                video_url = downloads[0].get("url")
            if not video_url:
                output = res.get("output") or {}
                if isinstance(output, dict):
                    video_url = output.get("url")

        if video_url:
            return {
                "success": True,
                "url": video_url,
                "api": f"Magic Hour ({MAGIC_HOUR_VIDEO_MODEL})"
            }
        return {"success": False, "error": "Magic Hour نے ویڈیو URL واپس نہیں کیا۔"}

    except Exception as e:
        return {"success": False, "error": f"Magic Hour error: {str(e)}"}

# ============================================================
# MAGIC HOUR VIDEO — IMAGE TO VIDEO
# ============================================================

def call_magic_hour_image_to_video(
    image_file,
    prompt=None,
    duration=5,
    resolution="480p"
):
    key = get_magic_hour_key()
    if not key:
        return {"success": False, "error": "❌ Magic Hour API key is missing."}

    # ✅ پرامپٹ کی لمبائی چیک کریں (اگر دیا گیا ہو)
    if prompt:
        prompt, was_truncated = truncate_prompt(prompt, MAX_PROMPT_LENGTH)
        if was_truncated:
            st.warning(
                f"⚠️ پرامپٹ بہت لمبا تھا اور اسے {MAX_PROMPT_LENGTH} حروف "
                f"تک مختصر کر دیا گیا ہے۔"
            )

    try:
        temp_path = OUTPUT_DIR / f"temp_ref_{uuid.uuid4().hex[:6]}.png"
        image_file.seek(0)
        with open(temp_path, "wb") as f:
            f.write(image_file.read())

        client = MagicHourClient(token=key)

        kwargs = {
            "assets": {"image_file_path": str(temp_path)},
            "end_seconds": float(duration),
            "name": "CraftReel AI Image to Video",
            "resolution": resolution,
            "model": MAGIC_HOUR_VIDEO_MODEL,
            "wait_for_completion": True,
            "download_outputs": False,
        }
        if prompt:
            kwargs["style"] = {"prompt": prompt}

        res = client.v1.image_to_video.generate(**kwargs)

        try:
            temp_path.unlink()
        except Exception:
            pass

        video_url = None
        if hasattr(res, 'downloads') and res.downloads:
            first = res.downloads[0]
            video_url = first.url if hasattr(first, 'url') else str(first)
        elif isinstance(res, dict):
            downloads = res.get("downloads") or []
            if downloads and isinstance(downloads[0], dict):
                video_url = downloads[0].get("url")
            if not video_url:
                output = res.get("output") or {}
                if isinstance(output, dict):
                    video_url = output.get("url")

        if video_url:
            return {
                "success": True,
                "url": video_url,
                "api": f"Magic Hour ({MAGIC_HOUR_VIDEO_MODEL})"
            }
        return {"success": False, "error": "Magic Hour نے ویڈیو URL واپس نہیں کیا۔"}

    except Exception as e:
        return {"success": False, "error": f"Magic Hour error: {str(e)}"}

# ============================================================
# AGNES CHAT
# ============================================================

def call_agnes_chat(messages):
    key = get_agnes_key()
    if not key:
        return {"success": False, "error": "Agnes API key is missing."}
    payload = {"model": APIS["agnes"]["models"]["chat"], "messages": messages}
    try:
        response = requests.post(
            f"{APIS['agnes']['base_url']}/chat/completions",
            headers=make_agnes_headers(),
            json=payload,
            timeout=(15, 60)
        )
        if response.status_code == 200:
            data = response.json()
            result = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return {"success": True, "result": result, "api": "Agnes AI"}
        return {"success": False, "error": f"Agnes: {extract_error(response)}"}
    except Exception as e:
        return {"success": False, "error": f"Agnes: {str(e)}"}

# ============================================================
# AI TOOLS (Agnes)
# ============================================================

def ai_tool(prompt, tool_type, target_language="Urdu"):
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

    # ---- Agnes AI ----
    st.markdown("### 🟣 Agnes AI (Image, Chat, SEO)")
    st.caption("🔐 Keys are locked after pressing Enter")

    if not st.session_state.get("agnes_key_locked", False):
        agnes_input = st.text_input(
            "Agnes API Key",
            value=st.session_state.get("agnes_key", ""),
            type="password",
            placeholder="Paste Agnes key here",
            key="agnes_key_input"
        )
        if agnes_input:
            st.session_state.agnes_key = agnes_input.strip()
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

    # ---- Magic Hour ----
    st.markdown("### 🎬 Magic Hour (Video)")

    if not st.session_state.get("magic_hour_key_locked", False):
        mh_input = st.text_input(
            "Magic Hour API Key",
            value=st.session_state.get("magic_hour_key", ""),
            type="password",
            placeholder="Paste Magic Hour key here",
            key="magic_hour_key_input"
        )
        if mh_input:
            st.session_state.magic_hour_key = mh_input.strip()
        if st.button("🔒 Lock Magic Hour Key", key="mh_lock_btn"):
            if st.session_state.magic_hour_key:
                st.session_state.magic_hour_key_locked = True
                st.success("✅ Magic Hour Key Locked!")
    else:
        st.success("✅ Magic Hour key loaded")
        if st.button("🔓 Change Magic Hour Key", key="mh_unlock"):
            st.session_state.magic_hour_key_locked = False
            st.session_state.magic_hour_key = ""

    st.markdown("---")
    st.markdown("### 🔐 API Status")
    if get_agnes_key():
        st.success("✅ Agnes: Connected")
    else:
        st.warning("⚠️ Agnes: Key missing")
    if get_magic_hour_key():
        st.success("✅ Magic Hour: Connected")
    else:
        st.warning("⚠️ Magic Hour: Key missing")

    st.markdown("---")
    st.caption("Videos saved in `generated_videos`")

# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    ["🎬 Video", "🎨 Image", "💬 Chat", "🛠️ Tools"]
)

# ============================================================
# TAB 1 - VIDEO (Magic Hour)
# ============================================================

with tab1:
    st.markdown("### 🎬 Generate Video")
    st.caption(
        f"Powered by Magic Hour (LTX 2.5) · "
        f"Free tier: 480p, up to 60 seconds · "
        f"Max prompt: {MAX_PROMPT_LENGTH} characters"
    )

    video_mode = st.radio(
        "Video Mode",
        ["Text to Video", "Image to Video"],
        horizontal=True
    )

    if video_mode == "Text to Video":
        video_prompt = st.text_area(
            "Describe your video",
            height=100,
            key="vid_prompt",
            placeholder="Example: A realistic baby panda walking through a beautiful green forest, cinematic lighting..."
        )
        reference_image = None
        mh_prompt = video_prompt

        # ✅ لائیو کاؤنٹر
        if video_prompt:
            char_count = len(video_prompt)
            if char_count > MAX_PROMPT_LENGTH:
                st.warning(
                    f"⚠️ پرامپٹ {char_count} حروف کا ہے — "
                    f"حد {MAX_PROMPT_LENGTH} ہے۔ خود بخود مختصر کر دیا جائے گا۔"
                )
            else:
                st.caption(f"📝 {char_count} / {MAX_PROMPT_LENGTH} حروف")

    else:  # Image to Video
        reference_image = st.file_uploader(
            "Upload a reference image",
            type=["jpg", "jpeg", "png"],
            key="ref_image_mh"
        )
        if reference_image:
            st.image(reference_image, caption="Reference Image", width=200)

        video_prompt = st.text_input(
            "Optional: Describe the motion (Optional)",
            placeholder="e.g., 'The panda slowly walks forward'",
            key="vid_prompt_img"
        )
        mh_prompt = video_prompt if video_prompt else None

    col1, col2 = st.columns(2)

    with col1:
        video_duration = st.selectbox(
            "Duration (seconds)",
            [5, 10, 15, 20],
            index=0,
            help="Free tier: 5s at 480p. Longer durations may use more credits."
        )

    with col2:
        video_ratio = st.selectbox(
            "Aspect Ratio",
            ["16:9", "9:16", "1:1"],
            index=0
        )

    st.caption(f"⏱️ Selected: {video_duration} seconds · Resolution: {MAGIC_HOUR_VIDEO_RESOLUTION}")

    if st.button(
        "🎬 Generate Video",
        use_container_width=True,
        type="primary"
    ):
        if video_mode == "Text to Video" and not video_prompt:
            st.warning("Please describe your video.")
        elif video_mode == "Image to Video" and not reference_image:
            st.warning("Please upload a reference image.")
        else:
            start_time = time.time()

            with st.spinner("Magic Hour is generating your video..."):
                if video_mode == "Text to Video":
                    result = call_magic_hour_text_to_video(
                        prompt=mh_prompt,
                        duration=video_duration,
                        aspect_ratio=video_ratio,
                        resolution=MAGIC_HOUR_VIDEO_RESOLUTION
                    )
                else:
                    result = call_magic_hour_image_to_video(
                        image_file=reference_image,
                        prompt=mh_prompt,
                        duration=video_duration,
                        resolution=MAGIC_HOUR_VIDEO_RESOLUTION
                    )

            elapsed = time.time() - start_time

            if result["success"]:
                st.success(
                    f"✅ Video ready! Engine: {result['api']} · "
                    f"Time: {int(elapsed // 60)}m {int(elapsed % 60)}s"
                )
                video_url = result.get("url")

                if video_url:
                    download_result = download_url_to_file(video_url)
                    if download_result["success"]:
                        st.video(download_result["path"])
                        st.markdown(
                            android_download_link(video_url, "⬇️ Download Video"),
                            unsafe_allow_html=True
                        )
                        st.caption(f"📁 Saved locally: {download_result['path']}")
                    else:
                        st.video(video_url)
                        st.markdown(
                            android_download_link(video_url, "⬇️ Download Video"),
                            unsafe_allow_html=True
                        )
            else:
                st.error(f"❌ Video generation failed\n\n{result['error']}")

# ============================================================
# TAB 2 - IMAGE (Agnes)
# ============================================================

with tab2:
    st.markdown("### 🎨 Generate Images")
    st.info("✨ Create HD images from text descriptions — Powered by Agnes AI")

    prompt_img = st.text_area(
        "Describe your image",
        height=100,
        key="img_prompt",
        placeholder="Example: A vibrant peacock in a mystical forest, golden sunlight, 8K"
    )

    col1, col2 = st.columns(2)

    with col1:
        image_size = st.selectbox(
            "Quality",
            ["1K", "2K", "3K", "4K"],
            index=2
        )

    with col2:
        image_ratio = st.selectbox(
            "Aspect Ratio",
            ["1:1", "16:9", "9:16", "4:3", "3:4"],
            index=1
        )

    if st.button("🎨 Generate Image", use_container_width=True):
        if not prompt_img:
            st.warning("Please describe your image.")
        else:
            with st.spinner("Creating image..."):
                result = call_agnes_image(
                    prompt_img,
                    image_size,
                    image_ratio
                )

            if result["success"]:
                st.image(result["url"], use_container_width=True)
                st.success(f"✅ Image generated! ({result['api']})")
                st.markdown(
                    android_download_link(result["url"], "⬇️ Download Image"),
                    unsafe_allow_html=True
                )
            else:
                st.error(f"❌ {result['error']}")

# ============================================================
# TAB 3 - CHAT (Agnes)
# ============================================================

with tab3:
    st.markdown("### 💬 Chat with AI")
    st.caption("Powered by Agnes AI")

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
                    st.session_state.chat_messages.append(
                        {"role": "assistant", "content": result["result"]}
                    )
                else:
                    st.error(f"❌ {result['error']}")

# ============================================================
# TAB 4 - AI TOOLS (Agnes)
# ============================================================

with tab4:
    st.markdown("### 🛠️ AI Tools")
    st.caption("Powered by Agnes AI")

    tool_type = st.selectbox(
        "Select Tool",
        [
            "SEO Generator",
            "Transcript Generator",
            "Text Summarizer",
            "Content Rewriter",
            "Translator"
        ]
    )

    target_language = "Urdu"

    if tool_type == "Translator":
        target_language = st.selectbox(
            "Select Target Language",
            [
                "Urdu", "English", "Hindi", "Arabic", "French",
                "Spanish", "German", "Chinese", "Japanese",
                "Russian", "Portuguese"
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
                result = ai_tool(tool_prompt, tool_key, target_language)
            if result["success"]:
                st.success("✅ Generated!")
                st.write(result["result"])
            else:
                st.error(f"❌ {result['error']}")

# ============================================================
# FOOTER
# ============================================================

st.markdown("---")
st.caption(
    "🎬 CraftReel AI · Video by Magic Hour · Image, Chat, SEO by Agnes AI · "
    "Videos & Images saved locally."
)
