import streamlit as st
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

# Hugging Face SDK
try:
    from huggingface_hub import InferenceClient
except ImportError:
    st.error("Please install huggingface_hub: pip install huggingface_hub")

load_dotenv()

# ============================================================
# CRAFTREEL AI - VIDEO GENERATOR & EDITOR
# (Agnes AI + Magic Hour + Hugging Face + OpenShot Engine)
# ============================================================

APP_NAME = "CraftReel AI"
OUTPUT_DIR = Path("generated_videos")
OUTPUT_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title=APP_NAME, page_icon="🎬", layout="wide")

# ============================================================
# CUSTOM CSS
# ============================================================
st.markdown("""
<style>
.main-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 1.5rem; border-radius: 12px; color: white;
    text-align: center; margin-bottom: 1.5rem;
}
.main-header h1 { font-size: 2.4rem; margin: 0; }
.main-header p { font-size: 1rem; opacity: 0.9; margin-top: 0.5rem; }
.stButton > button { font-weight: bold; border-radius: 8px; }
.download-btn {
    background-color: #4CAF50; color: white !important;
    padding: 12px 20px; border-radius: 8px; text-align: center;
    font-size: 16px; cursor: pointer; text-decoration: none !important;
    display: block; width: 100%; box-sizing: border-box;
    margin-top: 10px; font-weight: bold;
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
    <p>🎬 Video (Agnes + Magic Hour + Hugging Face + OpenShot) · 🎨 Image · 💬 Chat · 🛠️ Tools</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SESSION STATE
# ============================================================
if "agnes_key" not in st.session_state: st.session_state.agnes_key = ""
if "agnes_key_locked" not in st.session_state: st.session_state.agnes_key_locked = False
if "chat_messages" not in st.session_state: st.session_state.chat_messages = []

MAX_PROMPT_LENGTH = 2000

# ============================================================
# API KEY FUNCTIONS
# ============================================================
def get_secret_key(name, default=""):
    try:
        return st.secrets.get(name, default).strip()
    except Exception:
        return default

def get_agnes_key():
    return get_secret_key("AGNES_API_KEY") or st.session_state.get("agnes_key", "").strip()

def get_magic_hour_key():
    return get_secret_key("MAGIC_HOUR_API_KEY") or st.session_state.get("magic_hour_key", "").strip()

def get_hf_token():
    return get_secret_key("HF_TOKEN") or st.session_state.get("hf_token", "").strip()

def make_headers(key):
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

# ============================================================
# HELPERS
# ============================================================
def extract_error(response):
    try:
        data = response.json()
        if isinstance(data, dict):
            if "error" in data:
                err = data["error"]
                return err.get("message", str(err)) if isinstance(err, dict) else str(err)
            if "message" in data: return str(data["message"])
            if "detail" in data: return str(data["detail"])
        return response.text[:1000]
    except:
        return f"HTTP {response.status_code}"

def android_download_link(url, label="⬇️ Download"):
    if not url: return ""
    return f'<a href="{url}" class="download-btn" download>{label}</a>'

def truncate_prompt(prompt, max_len=MAX_PROMPT_LENGTH):
    if not prompt: return "", False
    if len(prompt) <= max_len: return prompt, False
    return prompt[:max_len], True

# ============================================================
# AGNES AI (Image, Chat, Tools, Video)
# ============================================================
def call_agnes_image(prompt, size="2K", ratio="16:9"):
    key = get_agnes_key()
    if not key: return {"success": False, "error": "Agnes API key missing."}
    payload = {"model": "agnes-image-2.1-flash", "prompt": prompt, "size": size, "ratio": ratio, "extra_body": {"response_format": "url"}}
    try:
        r = requests.post("https://apihub.agnes-ai.cn/v1/images/generations", headers=make_headers(key), json=payload, timeout=(15, 120))
        if r.status_code == 200: return {"success": True, "url": r.json()["data"][0]["url"], "api": "Agnes AI"}
        return {"success": False, "error": extract_error(r)}
    except Exception as e: return {"success": False, "error": str(e)}

def call_agnes_chat(messages):
    key = get_agnes_key()
    if not key: return {"success": False, "error": "Agnes API key missing."}
    try:
        r = requests.post("https://apihub.agnes-ai.cn/v1/chat/completions", headers=make_headers(key), json={"model": "agnes-2.5-flash", "messages": messages}, timeout=(15, 60))
        if r.status_code == 200: return {"success": True, "result": r.json()["choices"][0]["message"]["content"], "api": "Agnes AI"}
        return {"success": False, "error": extract_error(r)}
    except Exception as e: return {"success": False, "error": str(e)}

def ai_tool(prompt, tool_type, target_lang="Urdu"):
    prompts = {
        "seo": f"Generate SEO-optimized content for:\n{prompt}",
        "transcript": f"Generate a clear transcript for:\n{prompt}",
        "summarize": f"Summarize this text in 3-5 bullet points:\n{prompt}",
        "rewrite": f"Rewrite this content professionally:\n{prompt}",
        "translate": f"Translate into {target_lang}:\n{prompt}"
    }
    return call_agnes_chat([{"role": "user", "content": prompts.get(tool_type, prompt)}])

def call_agnes_video(prompt, duration=5, aspect_ratio="16:9", resolution="720P"):
    key = get_agnes_key()
    if not key: return {"success": False, "error": "❌ Agnes API key is missing."}
    
    prompt, was_truncated = truncate_prompt(prompt, MAX_PROMPT_LENGTH)
    if was_truncated: st.warning(f"⚠️ Prompt was truncated to {MAX_PROMPT_LENGTH} characters.")

    payload = {
        "model": "agnes-video-2.5",
        "prompt": prompt,
        "seconds": str(duration),
        "mode": "text",
        "size": resolution,
        "aspect_ratio": aspect_ratio
    }
    
    try:
        response = requests.post("https://apihub.agnes-ai.cn/v1/videos", headers=make_headers(key), json=payload, timeout=(15, 120))
        if response.status_code != 200:
            return {"success": False, "error": f"Agnes Video Error: {extract_error(response)}"}
            
        data = response.json()
        video_id = data.get("video_id") or data.get("id")
        if not video_id:
            return {"success": False, "error": "❌ No video_id returned from API."}
            
        status_placeholder = st.empty()
        max_attempts = 60
        poll_interval = 5
        
        for attempt in range(max_attempts):
            time.sleep(poll_interval)
            status_placeholder.info(f"⏳ Video generation in progress... (Attempt {attempt + 1}/{max_attempts})")
            
            try:
                poll_response = requests.get(f"https://apihub.agnes-ai.cn/v1/agnesapi", params={"video_id": video_id, "model_name": "agnes-video-2.5"}, headers=make_headers(key), timeout=(15, 60))
                if poll_response.status_code == 200:
                    poll_data = poll_response.json()
                    status = poll_data.get("status", "").lower()
                    if status == "completed":
                        video_url = poll_data.get("url")
                        if video_url:
                            status_placeholder.success("✅ Video ready!")
                            return {"success": True, "url": video_url, "api": "Agnes Video 2.5"}
                        else:
                            return {"success": False, "error": "❌ Video completed but no URL found."}
                    elif status == "failed":
                        error_msg = poll_data.get("error", "Unknown error")
                        status_placeholder.error(f"❌ Video generation failed: {error_msg}")
                        return {"success": False, "error": error_msg}
            except Exception:
                continue
                
        status_placeholder.warning("⚠️ Timeout waiting for video generation.")
        return {"success": False, "error": "Timeout: Video generation took too long."}
    except Exception as e:
        return {"success": False, "error": f"Agnes Video Error: {str(e)}"}

# ============================================================
# MAGIC HOUR (Text-to-Video)
# ============================================================
def call_magic_hour_video(prompt, duration=4, aspect_ratio="16:9", resolution="480p", model="ltx-2.5"):
    key = get_magic_hour_key()
    if not key: return {"success": False, "error": "Magic Hour API key missing."}
    prompt, _ = truncate_prompt(prompt)
    
    payload = {
        "end_seconds": duration,
        "aspect_ratio": aspect_ratio,
        "style": {"prompt": prompt},
        "name": "CraftReel Video",
        "model": model,
        "resolution": resolution
    }
    
    try:
        r = requests.post("https://api.magichour.ai/v1/text-to-video", headers=make_headers(key), json=payload, timeout=(15, 120))
        if r.status_code not in (200, 201): return {"success": False, "error": extract_error(r)}
        
        data = r.json()
        job_id = data.get("id")
        if not job_id: return {"success": False, "error": "No job ID returned."}
        
        status_ph = st.empty()
        for attempt in range(60):
            time.sleep(5)
            status_ph.info(f"⏳ Magic Hour generating video... (Attempt {attempt+1}/60)")
            poll = requests.get(f"https://api.magichour.ai/v1/video-projects/{job_id}", headers=make_headers(key), timeout=(15, 60))
            if poll.status_code == 200:
                pdata = poll.json()
                status = pdata.get("status", "").lower()
                if status == "complete":
                    url = pdata.get("downloads", [{}])[0].get("url") if pdata.get("downloads") else pdata.get("video_url")
                    status_ph.success("✅ Video Ready!")
                    return {"success": True, "url": url, "api": "Magic Hour"}
                elif status in ("error", "failed"):
                    status_ph.error(f"❌ Error: {pdata.get('error')}")
                    return {"success": False, "error": pdata.get("error")}
        status_ph.warning("⚠️ Timeout.")
        return {"success": False, "error": "Timeout waiting for video."}
    except Exception as e: return {"success": False, "error": str(e)}

# ============================================================
# HUGGING FACE (Text-to-Video)
# ============================================================
def call_hf_video(prompt, model_id="Wan-AI/Wan2.2-T2V-A14B"):
    token = get_hf_token()
    if not token: return {"success": False, "error": "Hugging Face token missing."}
    prompt, _ = truncate_prompt(prompt)
    
    try:
        # hf-inference پرووائیڈر کے ساتھ صحیح ماڈل
        client = InferenceClient(provider="hf-inference", api_key=token)
        video_bytes = client.text_to_video(prompt, model=model_id)
        
        filename = f"hf_video_{int(time.time())}.mp4"
        filepath = OUTPUT_DIR / filename
        with open(filepath, "wb") as f:
            f.write(video_bytes)
            
        return {"success": True, "path": str(filepath), "api": "Hugging Face"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================================
# OPENSHOT / FFMPEG ENGINE
# ============================================================
def ffmpeg_create_video(images, audio, duration_per_img, output_name):
    temp_dir = tempfile.mkdtemp()
    try:
        img_paths = []
        for i, img in enumerate(images):
            p = os.path.join(temp_dir, f"img_{i}.jpg")
            with open(p, "wb") as f: f.write(img.getbuffer())
            img_paths.append(p)
        
        audio_path = None
        if audio:
            audio_path = os.path.join(temp_dir, "audio.mp3")
            with open(audio_path, "wb") as f: f.write(audio.getbuffer())
            
        out_path = os.path.join(OUTPUT_DIR, output_name)
        
        filter_complex = ""
        for i in range(len(img_paths)):
            filter_complex += f"[{i}:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}];"
        if len(img_paths) > 1:
            filter_complex += "".join([f"[v{i}]" for i in range(len(img_paths))]) + f"concat=n={len(img_paths)}:v=1:a=0[outv]"
        else:
            filter_complex += "[v0]copy[outv]"
            
        cmd = ["ffmpeg", "-y"]
        for p in img_paths:
            cmd.extend(["-loop", "1", "-t", str(duration_per_img), "-i", p])
        if audio_path:
            cmd.extend(["-i", audio_path])
        cmd.extend(["-filter_complex", filter_complex, "-map", "[outv]"])
        if audio_path:
            cmd.extend(["-map", f"{len(img_paths)}:a", "-c:a", "aac", "-shortest"])
        cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", out_path])
        
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if res.returncode != 0: return {"success": False, "error": res.stderr}
        return {"success": True, "path": out_path}
    except Exception as e: return {"success": False, "error": str(e)}
    finally: shutil.rmtree(temp_dir, ignore_errors=True)

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("## ⚙️ API Settings")
    
    st.markdown("### 🟣 Agnes AI")
    if not st.session_state.agnes_key_locked:
        agnes_key = st.text_input("Agnes API Key", type="password", key="agnes_input")
        if agnes_key: st.session_state.agnes_key = agnes_key.strip()
        if st.button("🔒 Lock Agnes Key"):
            if st.session_state.agnes_key: st.session_state.agnes_key_locked = True
    else:
        st.success("✅ Agnes Key Locked")
        if st.button("🔓 Change Key"): st.session_state.agnes_key_locked = False
        
    st.markdown("---")
    st.markdown("### 🎬 Magic Hour")
    mh_key = st.text_input("Magic Hour API Key", type="password", key="mh_input")
    if mh_key: st.session_state.magic_hour_key = mh_key.strip()
    
    st.markdown("---")
    st.markdown("### 🤗 Hugging Face")
    hf_token = st.text_input("HF Token", type="password", key="hf_input")
    if hf_token: st.session_state.hf_token = hf_token.strip()
    
    st.markdown("---")
    st.markdown("### 🔐 Status")
    if get_agnes_key(): st.success("Agnes: Connected")
    else: st.warning("Agnes: Missing")
    if get_magic_hour_key(): st.success("Magic Hour: Connected")
    else: st.warning("Magic Hour: Missing")
    if get_hf_token(): st.success("Hugging Face: Connected")
    else: st.warning("Hugging Face: Missing")

# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3, tab4 = st.tabs(["🎬 Video", "🎨 Image", "💬 Chat", "🛠️ Tools"])

# ============================================================
# TAB 1: VIDEO
# ============================================================
with tab1:
    st.markdown("### 🎬 Video Generation")
    engine = st.radio("Select Engine", ["Agnes AI", "Hugging Face", "Magic Hour", "OpenShot Editor"], horizontal=True)
    
    st.markdown("---")
    
    if engine == "Agnes AI":
        st.info("💡 Agnes AI: 5-10 second clips. (API call will be made, may face limit issues).")
        prompt = st.text_area("Describe your video", height=100, key="agnes_vid_prompt")
        
        col1, col2 = st.columns(2)
        with col1: dur = st.selectbox("Duration", [5, 10], index=0)
        with col2: ratio = st.selectbox("Aspect Ratio", ["16:9", "9:16", "1:1"], index=0)
        
        if st.button("Generate via Agnes", type="primary"):
            if prompt:
                res = call_agnes_video(prompt, dur, ratio)
                if res["success"]: 
                    st.video(res["url"])
                    st.markdown(android_download_link(res["url"], "⬇️ Download Video"), unsafe_allow_html=True)
                else: 
                    st.error(res["error"])

    elif engine == "Hugging Face":
        st.info("💡 Hugging Face: Uses Wan-AI/Wan2.2-T2V-A14B model (approx 5s clips).")
        prompt = st.text_area("Describe your video", height=100, key="hf_prompt")
        
        model = st.selectbox("Model", ["Wan-AI/Wan2.2-T2V-A14B"]) # صرف یہی ماڈل کام کرے گا
        
        if st.button("Generate via Hugging Face", type="primary"):
            if prompt:
                with st.spinner("Hugging Face is generating video (this may take a minute)..."):
                    res = call_hf_video(prompt, model)
                if res["success"]: 
                    st.video(res["path"])
                else: 
                    st.error(res["error"])
                
    elif engine == "Magic Hour":
        st.info("💡 Magic Hour: 5-30 second clips, free tier available (use 4s to stay in 100 credits).")
        prompt = st.text_area("Describe your video", height=100, key="mh_prompt")
        col1, col2 = st.columns(2)
        with col1: dur = st.selectbox("Duration", [4, 5, 10, 15, 20, 30], index=0)
        with col2: ratio = st.selectbox("Aspect Ratio", ["16:9", "9:16", "1:1"], index=0)
        
        if st.button("Generate via Magic Hour", type="primary"):
            if prompt:
                res = call_magic_hour_video(prompt, dur, ratio)
                if res["success"]: st.video(res["url"])
                else: st.error(res["error"])

    else:
        st.info("💡 OpenShot Engine (FFmpeg): Create long videos from images & audio.")
        images = st.file_uploader("Upload Images", type=["jpg", "png"], accept_multiple_files=True)
        audio = st.file_uploader("Upload Audio (Optional)", type=["mp3", "wav"])
        dur = st.slider("Seconds per image", 1, 10, 3)
        out_name = st.text_input("Output Filename", f"video_{int(time.time())}.mp4")
        
        if st.button("Create Video (FFmpeg)", type="primary"):
            if images:
                with st.spinner("FFmpeg processing..."):
                    res = ffmpeg_create_video(images, audio, dur, out_name)
                if res["success"]: st.video(res["path"])
                else: st.error(res["error"])

# ============================================================
# TAB 2: IMAGE
# ============================================================
with tab2:
    st.markdown("### 🎨 Generate Images")
    prompt = st.text_area("Describe your image", height=100, key="img_prompt")
    col1, col2 = st.columns(2)
    with col1: size = st.selectbox("Quality", ["1K", "2K", "3K", "4K"], index=2)
    with col2: ratio = st.selectbox("Aspect Ratio", ["1:1", "16:9", "9:16"], index=1)
    
    if st.button("Generate Image"):
        if prompt:
            with st.spinner("Creating image..."):
                res = call_agnes_image(prompt, size, ratio)
            if res["success"]: 
                st.image(res["url"])
                st.markdown(android_download_link(res["url"], "⬇️ Download Image"), unsafe_allow_html=True)
            else: st.error(res["error"])

# ============================================================
# TAB 3: CHAT
# ============================================================
with tab3:
    st.markdown("### 💬 Chat with AI")
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]): st.write(msg["content"])
        
    if prompt := st.chat_input("Type your message..."):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                res = call_agnes_chat(st.session_state.chat_messages)
                if res["success"]:
                    st.write(res["result"])
                    st.session_state.chat_messages.append({"role": "assistant", "content": res["result"]})
                else: st.error(res["error"])

# ============================================================
# TAB 4: TOOLS
# ============================================================
with tab4:
    st.markdown("### 🛠️ AI Tools")
    tool = st.selectbox("Select Tool", ["SEO Generator", "Transcript Generator", "Text Summarizer", "Content Rewriter", "Translator"])
    lang = "Urdu"
    if tool == "Translator":
        lang = st.selectbox("Target Language", ["Urdu", "English", "Hindi", "Arabic", "French", "Spanish"], index=0)
        
    input_text = st.text_area(f"Enter input for {tool}", height=120)
    
    if st.button("Generate"):
        if input_text:
            with st.spinner("Generating..."):
                res = ai_tool(input_text, tool.lower().split()[0], lang)
            if res["success"]: st.write(res["result"])
            else: st.error(res["error"])

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.caption("🎬 CraftReel AI · Video: Agnes, Magic Hour, Hugging Face & FFmpeg · Image/Chat/Tools: Agnes AI")
