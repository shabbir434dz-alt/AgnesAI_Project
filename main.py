import streamlit as st
import streamlit.components.v1 as components
import requests
import time
import os
import uuid
import subprocess
import tempfile
import shutil
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

# ============================================================
# CRAFTREEL AI - VIDEO GENERATOR & EDITOR
# (Agnes AI + OpenShot Engine/FFmpeg)
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
    <p>🎬 Video Editor (OpenShot Engine) · 🎨 Image · 💬 Chat · 🛠️ Tools (Agnes AI)</p>
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
            "image": "agnes-image-2.1-flash",
            "image_hd": "agnes-image-2.1-flash",
            "chat": "agnes-2.5-flash",
            "edit": "agnes-image-edit-v1"
        }
    }
}

MAX_PROMPT_LENGTH = 2000

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

def make_agnes_headers():
    key = get_agnes_key()
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

# ============================================================
# ERROR EXTRACTION & HELPERS
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

def android_download_link(url, label="⬇️ Download"):
    if not url:
        return ""
    encoded_url = quote(str(url), safe="")
    return (
        f'<a href="craftreel-download://download?url={encoded_url}" '
        f'class="download-btn">{label}</a>'
    )

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
# AGNES CHAT & TOOLS
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
# OPENSHT / FFMPEG VIDEO ENGINE
# ============================================================

def ffmpeg_create_video_from_images(image_files, audio_file, duration_per_image, output_name):
    """یہ فنکشن تصاویر اور آڈیو کو ملا کر ویڈیو بناتا ہے (OpenShot انجن)"""
    
    # عارضی فولڈر بنائیں
    temp_dir = tempfile.mkdtemp()
    image_paths = []
    
    try:
        # تصاویر کو محفوظ کریں
        for i, img in enumerate(image_files):
            img_path = os.path.join(temp_dir, f"img_{i}.jpg")
            with open(img_path, "wb") as f:
                f.write(img.getbuffer())
            image_paths.append(img_path)
            
        audio_path = None
        if audio_file:
            audio_path = os.path.join(temp_dir, "audio.mp3")
            with open(audio_path, "wb") as f:
                f.write(audio_file.getbuffer())

        # FFmpeg کمانڈ بنائیں
        output_path = os.path.join(OUTPUT_DIR, output_name)
        
        # ہر تصویر کو ایک مخصوص وقت تک دکھانے کے لیے فلٹر
        filter_complex = ""
        for i in range(len(image_paths)):
            filter_complex += f"[{i}:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}];"
        
        # تصاویر کو کنیکٹ کریں
        if len(image_paths) > 1:
            for i in range(len(image_paths)):
                filter_complex += f"[v{i}]" 
            filter_complex += f"concat=n={len(image_paths)}:v=1:a=0[outv]"
        else:
            filter_complex += "[v0]copy[outv]"

        cmd = ["ffmpeg", "-y"]
        
        # تصاویر کے ان پٹس شامل کریں
        for img_path in image_paths:
            cmd.extend(["-loop", "1", "-t", str(duration_per_image), "-i", img_path])
            
        # آڈیو شامل کریں
        if audio_path:
            cmd.extend(["-i", audio_path])

        cmd.extend(["-filter_complex", filter_complex, "-map", "[outv]"])
        
        # آڈیو میپ کریں
        if audio_path:
            cmd.extend(["-map", f"{len(image_paths)}:a", "-c:a", "aac", "-shortest"])
        
        # ویڈیو سیٹنگز
        cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", output_path])
        
        # کمانڈ چلائیں
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            return {"success": False, "error": result.stderr}
            
        return {"success": True, "path": output_path}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def ffmpeg_merge_videos(video_files, output_name):
    """یہ فنکشن ایک سے زیادہ ویڈیوز کو آپس میں جوڑتا ہے"""
    temp_dir = tempfile.mkdtemp()
    video_paths = []
    
    try:
        for i, vid in enumerate(video_files):
            vid_path = os.path.join(temp_dir, f"vid_{i}.mp4")
            with open(vid_path, "wb") as f:
                f.write(vid.getbuffer())
            video_paths.append(vid_path)
            
        list_file = os.path.join(temp_dir, "list.txt")
        with open(list_file, "w") as f:
            for vp in video_paths:
                f.write(f"file '{vp}'\n")
                
        output_path = os.path.join(OUTPUT_DIR, output_name)
        
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file, "-c", "copy", output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        if result.returncode != 0:
            return {"success": False, "error": result.stderr}
            
        return {"success": True, "path": output_path}
        
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("## ⚙️ API Settings")

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
    st.markdown("### 🔐 API Status")
    if get_agnes_key():
        st.success("✅ Agnes: Connected")
    else:
        st.warning("⚠️ Agnes: Key missing")
    st.info("✅ OpenShot Engine (FFmpeg): Ready")

    st.markdown("---")
    st.caption("Videos saved in `generated_videos`")

# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    ["🎬 Video", "🎨 Image", "💬 Chat", "🛠️ Tools"]
)

# ============================================================
# TAB 1 - VIDEO (OpenShot Engine & Agnes)
# ============================================================

with tab1:
    st.markdown("### 🎬 Video Generation & Editing")
    
    # ٹوگل: اوپن شوٹ یا ایگنس
    video_engine = st.radio(
        "Select Video Engine",
        ["OpenShot Engine (FFmpeg)", "Agnes AI (Text-to-Video - Limited)"],
        horizontal=True,
        help="OpenShot آپ کی تصاویر اور آڈیو سے ویڈیو بناتا ہے۔ ایگنس ٹیکسٹ سے ویڈیو بناتا ہے لیکن اس کی لمٹ ہے۔"
    )
    
    st.markdown("---")

    if video_engine == "OpenShot Engine (FFmpeg)":
        st.info("💡 یہاں سے آپ اپنی تصاویر، آڈیو اور ویڈیو کلپس کو ملا کر ایک لمبی ویڈیو بنا سکتے ہیں۔ (کوئی لمٹ نہیں)")
        
        editor_mode = st.selectbox(
            "What do you want to do?",
            ["Create Video from Images + Audio", "Merge Multiple Videos"]
        )
        
        if editor_mode == "Create Video from Images + Audio":
            st.markdown("#### 🖼️ Create Video from Images")
            
            uploaded_images = st.file_uploader(
                "Upload Images (Select multiple)", 
                type=["jpg", "jpeg", "png"], 
                accept_multiple_files=True
            )
            
            uploaded_audio = st.file_uploader(
                "Upload Background Music (Optional)", 
                type=["mp3", "wav", "m4a"]
            )
            
            col_d, col_n = st.columns(2)
            with col_d:
                duration_per_img = st.slider("Duration per image (seconds)", 1, 10, 3)
            with col_n:
                output_name = st.text_input("Output File Name", f"openshot_video_{int(time.time())}.mp4")
            
            if st.button("🎬 Create Video", use_container_width=True, type="primary"):
                if not uploaded_images:
                    st.warning("Please upload at least one image.")
                else:
                    with st.spinner("FFmpeg (OpenShot Engine) ویڈیو بنا رہا ہے... انتظار کریں..."):
                        result = ffmpeg_create_video_from_images(uploaded_images, uploaded_audio, duration_per_img, output_name)
                        
                    if result["success"]:
                        st.success("✅ ویڈیو کامیابی سے بن گئی!")
                        st.video(result["path"])
                        
                        with open(result["path"], "rb") as f:
                            st.download_button(
                                label="⬇️ Download Video",
                                data=f,
                                file_name=output_name,
                                mime="video/mp4"
                            )
                    else:
                        st.error(f"❌ FFmpeg Error:\n{result['error']}")
        
        elif editor_mode == "Merge Multiple Videos":
            st.markdown("#### 🎞️ Merge Multiple Videos")
            uploaded_videos = st.file_uploader(
                "Upload Videos to Merge (Select multiple)", 
                type=["mp4", "mov", "avi"], 
                accept_multiple_files=True
            )
            
            merge_name = st.text_input("Output File Name", f"merged_video_{int(time.time())}.mp4")
            
            if st.button("🔗 Merge Videos", use_container_width=True, type="primary"):
                if not uploaded_videos or len(uploaded_videos) < 2:
                    st.warning("Please upload at least 2 videos to merge.")
                else:
                    with st.spinner("ویڈیوز کو جوڑا جا رہا ہے..."):
                        result = ffmpeg_merge_videos(uploaded_videos, merge_name)
                        
                    if result["success"]:
                        st.success("✅ ویڈیوز کامیابی سے جوڑ دی گئیں!")
                        st.video(result["path"])
                        with open(result["path"], "rb") as f:
                            st.download_button(
                                label="⬇️ Download Merged Video",
                                data=f,
                                file_name=merge_name,
                                mime="video/mp4"
                            )
                    else:
                        st.error(f"❌ Error merging videos:\n{result['error']}")

    else:
        # Agnes AI Video (Experimental)
        st.warning("⚠️ Agnes AI ابھی ویڈیو جنریشن میں محدود ہے (1 کال فی 24 گھنٹے)۔ اسے صرف تجرباتی طور پر استعمال کریں۔")
        
        video_prompt = st.text_area(
            "Describe your video",
            height=100,
            key="vid_prompt",
            placeholder="Example: A cinematic slow-motion shot of a golden eagle soaring through a mountain valley at sunrise."
        )
        
        col1, col2 = st.columns(2)
        with col1:
            video_duration = st.selectbox("Duration (seconds)", [5, 10, 15, 20], index=1)
        with col2:
            video_ratio = st.selectbox("Aspect Ratio", ["16:9", "9:16", "1:1"], index=0)
            
        if st.button("🎬 Generate via Agnes (AI)", use_container_width=True):
            if not video_prompt:
                st.warning("Please describe your video.")
            else:
                # یہاں ایگنس کی ویڈیو جنریشن کا کوڈ آئے گا (اگر آپ کے پاس اس کی API ہو)
                st.error("❌ Agnes Video API ابھی دستیاب نہیں ہے یا اس کی لمٹ ختم ہو چکی ہے۔ براہ کرم 'OpenShot Engine' استعمال کریں۔")
                st.info("نوٹ: ایگنس کی ویڈیو جنریشن کی کوئی آفیشل API ڈاکومنٹیشن نہیں ہے، اس لیے اسے فی الحال غیر فعال رکھا گیا ہے۔")

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
                st.markdown(android_download_link(result["url"], "⬇️ Download Image"), unsafe_allow_html=True)
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
st.caption("🎬 CraftReel AI · Video by OpenShot Engine (FFmpeg) · Image, Chat, SEO by Agnes AI")
