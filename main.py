import streamlit as st
import requests
import time
import os
import base64
import uuid
import asyncio
import edge_tts
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

# ============================================================
# CRAFTREEL AI - VIDEO (Agnes) + VOICE (Edge-TTS) + IMAGE (Agnes) + CHAT (Groq)
# ============================================================

APP_NAME = "CraftReel AI"
OUTPUT_DIR = Path("generated_media")
OUTPUT_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title=APP_NAME, page_icon="🎬", layout="wide")

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
    background-color: #4CAF50; color: white !important; padding: 12px;
    border-radius: 8px; text-align: center; display: block; margin-top: 10px;
    font-weight: bold; text-decoration: none !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>🎬 CraftReel AI</h1>
    <p>🔊 Voice (Edge-TTS) · 🎨 Image (Agnes) · 💬 Chat (Groq)</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SESSION STATE
# ============================================================

if "agnes_key" not in st.session_state: st.session_state.agnes_key = ""
if "agnes_key_locked" not in st.session_state: st.session_state.agnes_key_locked = False
if "groq_key" not in st.session_state: st.session_state.groq_key = ""
if "groq_key_locked" not in st.session_state: st.session_state.groq_key_locked = False
if "chat_messages" not in st.session_state: st.session_state.chat_messages = []

# ============================================================
# API CONFIGURATION
# ============================================================

APIS = {
    "agnes": {"base_url": "https://apihub.agnes-ai.cn/v1", "model": "agnes-image-2.1-flash"},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "openai/gpt-oss-20b"}
}

# ============================================================
# API KEY FUNCTIONS
# ============================================================

def get_key(service):
    try:
        key = st.secrets.get(f"{service.upper()}_API_KEY", "")
        if key: return key.strip()
    except: pass
    return st.session_state.get(f"{service}_key", "").strip()

def make_headers(service):
    return {"Authorization": f"Bearer {get_key(service)}", "Content-Type": "application/json"}

def extract_error(response):
    try: return response.json().get("error", {}).get("message", str(response.text))[:500]
    except: return str(response.text)[:500]

def android_download_link(url, label="⬇️ Download"):
    if not url: return ""
    encoded_url = quote(str(url), safe="")
    return f'<a href="craftreel-download://download?url={encoded_url}" class="download-btn">{label}</a>'

# ============================================================
# EDGE-TTS (100+ VOICES)
# ============================================================

async def generate_voice(text, voice_id):
    try:
        communicate = edge_tts.Communicate(text, voice_id)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        
        if audio_data:
            filename = f"voice_{uuid.uuid4().hex[:6]}.mp3"
            path = OUTPUT_DIR / filename
            with open(path, "wb") as f: f.write(audio_data)
            return {"success": True, "path": str(path)}
        return {"success": False, "error": "No audio generated"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================================
# AGNES IMAGE
# ============================================================

def call_agnes_image(prompt, size="2K", ratio="16:9"):
    if not get_key("agnes"): return {"success": False, "error": "Agnes Key Missing"}
    payload = {"model": APIS["agnes"]["model"], "prompt": prompt, "size": size, "ratio": ratio, "extra_body": {"response_format": "url"}}
    try:
        r = requests.post(f"{APIS['agnes']['base_url']}/images/generations", headers=make_headers("agnes"), json=payload, timeout=120)
        if r.status_code == 200: return {"success": True, "url": r.json()["data"][0]["url"]}
        return {"success": False, "error": extract_error(r)}
    except Exception as e: return {"success": False, "error": str(e)}

# ============================================================
# GROQ CHAT
# ============================================================

def call_groq_chat(messages):
    if not get_key("groq"): return {"success": False, "error": "Groq Key Missing"}
    payload = {"model": APIS["groq"]["model"], "messages": messages}
    try:
        r = requests.post(f"{APIS['groq']['base_url']}/chat/completions", headers=make_headers("groq"), json=payload, timeout=60)
        if r.status_code == 200: return {"success": True, "result": r.json()["choices"][0]["message"]["content"]}
        return {"success": False, "error": extract_error(r)}
    except Exception as e: return {"success": False, "error": str(e)}

# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("## ⚙️ API Settings")
    
    # Agnes
    st.markdown("### 🎨 Agnes (Image)")
    if not st.session_state.get("agnes_key_locked"):
        k = st.text_input("Agnes Key", type="password", key="ag_in")
        if k: st.session_state.agnes_key = k.strip()
        if st.button("🔒 Lock Agnes"):
            st.session_state.agnes_key_locked = True; st.rerun()
    else:
        st.success("✅ Agnes Locked")
        if st.button("🔓 Unlock Agnes"):
            st.session_state.agnes_key_locked = False; st.rerun()

    st.markdown("---")
    # Groq
    st.markdown("### ⚡ Groq (Chat/SEO)")
    if not st.session_state.get("groq_key_locked"):
        k = st.text_input("Groq Key", type="password", key="gq_in")
        if k: st.session_state.groq_key = k.strip()
        if st.button("🔒 Lock Groq"):
            st.session_state.groq_key_locked = True; st.rerun()
    else:
        st.success("✅ Groq Locked")
        if st.button("🔓 Unlock Groq"):
            st.session_state.groq_key_locked = False; st.rerun()

    st.markdown("---")
    st.info("🔊 Edge-TTS (Voice) is Free. No Key required.")

# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔊 Voice", "🎨 Image", "💬 Chat", "🛠️ Tools", "🎬 Video (Soon)"])

# TAB 1 - VOICE (Edge-TTS)
with tab1:
    st.markdown("### 🔊 Generate Voice (100+ Voices)")
    st.info("Select any language, gender, or character voice. Urdu, English, Arabic, Hindi, and many more.")
    
    text = st.text_area("Enter text for voice", height=150, key="voice_text")
    
    # Voice list
    voice_options = [
        "ur-PK-UzmaNeural (Urdu Female)",
        "ur-PK-AsadNeural (Urdu Male)",
        "en-US-AriaNeural (English Female)",
        "en-US-GuyNeural (English Male)",
        "en-GB-SoniaNeural (British Female)",
        "hi-IN-SwaraNeural (Hindi Female)",
        "ar-SA-ZariyahNeural (Arabic Female)",
        "zh-CN-XiaochenNeural (Chinese Child)",
        "fr-FR-DeniseNeural (French Female)",
        "de-DE-KatjaNeural (German Female)",
        "es-ES-ElviraNeural (Spanish Female)",
        "ru-RU-SvetlanaNeural (Russian Female)",
        "tr-TR-EmelNeural (Turkish Female)",
        "ja-JP-NanamiNeural (Japanese Female)",
        "ko-KR-SunHiNeural (Korean Female)"
    ]
    
    selected_voice = st.selectbox("Select Voice", voice_options, index=0)
    voice_id = selected_voice.split(" ")[0]
    
    if st.button("🔊 Generate Voice", use_container_width=True):
        if not text: st.warning("Enter text")
        else:
            with st.spinner("Generating voice..."):
                res = asyncio.run(generate_voice(text, voice_id))
            if res["success"]:
                st.success("✅ Voice Ready!")
                st.audio(res["path"])
                with open(res["path"], "rb") as f:
                    st.download_button("⬇️ Download MP3", f, file_name="voice.mp3")
            else: st.error(res["error"])

# TAB 2 - IMAGE (Agnes)
with tab2:
    st.markdown("### 🎨 Generate Image (Agnes)")
    prompt = st.text_area("Describe image", height=100, key="i_prompt")
    c1, c2 = st.columns(2)
    with c1: sz = st.selectbox("Quality", ["1K", "2K", "3K", "4K"], index=2)
    with c2: rat = st.selectbox("Ratio", ["1:1", "16:9", "9:16", "4:3"], index=1)
    
    if st.button("🎨 Generate Image", use_container_width=True):
        if not prompt: st.warning("Enter prompt")
        else:
            with st.spinner("Creating image..."):
                res = call_agnes_image(prompt, sz, rat)
            if res["success"]:
                st.image(res["url"], use_container_width=True)
                st.markdown(android_download_link(res["url"], "⬇️ Download"), unsafe_allow_html=True)
            else: st.error(res["error"])

# TAB 3 - CHAT (Groq)
with tab3:
    st.markdown("### 💬 Chat (Groq)")
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]): st.write(msg["content"])
    prompt = st.chat_input("Type message...")
    if prompt:
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.write(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                res = call_groq_chat(st.session_state.chat_messages)
            if res["success"]:
                st.write(res["result"])
                st.session_state.chat_messages.append({"role": "assistant", "content": res["result"]})
            else: st.error(res["error"])

# TAB 4 - TOOLS (Groq)
with tab4:
    st.markdown("### 🛠️ AI Tools (Groq)")
    tool = st.selectbox("Tool", ["SEO", "Summarize", "Rewrite", "Translate"])
    t_prompt = st.text_area("Input text", height=150)
    if st.button("🛠️ Run", use_container_width=True):
        if not t_prompt: st.warning("Enter text")
        else:
            with st.spinner("Working..."):
                prompts = {"SEO": f"Generate SEO content:\n{t_prompt}", "Summarize": f"Summarize:\n{t_prompt}", "Rewrite": f"Rewrite:\n{t_prompt}", "Translate": f"Translate to Urdu:\n{t_prompt}"}
                res = call_groq_chat([{"role": "user", "content": prompts.get(tool, t_prompt)}])
            if res["success"]: st.write(res["result"])
            else: st.error(res["error"])

# TAB 5 - VIDEO (Placeholder)
with tab5:
    st.markdown("### 🎬 Generate Video")
    st.info("⚠️ Video API is currently being set up. Please check back later.")
    st.markdown("We are finding the best free video generation API for you.")

st.markdown("---")
st.caption("🎬 CraftReel AI · Voice (Edge-TTS) · Image (Agnes) · Chat (Groq)")