import streamlit as st
import requests
import time
import os
import base64
import uuid
import json
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

# ============================================================
# CRAFTREEL AI - ALL IN ONE
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
    <p>🎬 Video (Render MCP) · 🎨 Image · 💬 Chat · 🛠️ Tools (Agnes AI)</p>
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

if "mcp_chat_history" not in st.session_state:
    st.session_state.mcp_chat_history = []
if "mcp_session_url" not in st.session_state:
    st.session_state.mcp_session_url = None

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
# AGNES IMAGE & CHAT
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
            return {"success": True, "url": data["data"][0]["url"], "api": "Agnes AI HD"}
        return {"success": False, "error": extract_error(response)}
    except Exception as e:
        return {"success": False, "error": str(e)}

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
            result = data.get("choices", [{}])[0].get("message", {}).get("content", "")
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
    return call_agnes_chat([{"role": "user", "content": full_prompt}])

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
    st.success("✅ Render MCP: Configured")

# ============================================================
# TABS
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs(
    ["🎬 Video", "🎨 Image", "💬 Chat", "🛠️ Tools"]
)

# ============================================================
# TAB 1 - VIDEO (Render MCP)
# ============================================================

with tab1:
    st.markdown("### 🎬 Generate Video via Render MCP")
    st.caption("Powered by Google AI Edge Gallery (via Render) · Live Chat Session")

    for msg in st.session_state.mcp_chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if "video_url" in msg and msg["video_url"]:
                st.video(msg["video_url"])
                st.markdown(android_download_link(msg["video_url"], "⬇️ Download Video"), unsafe_allow_html=True)

    prompt = st.chat_input("Describe your video (e.g., 'Generate video with AI Edge Gallery: A dog running')...")

    if prompt:
        st.session_state.mcp_chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("⏳ Connecting to Render MCP & Generating..."):
                try:
                    base_url = "https://video-generator-mcp.onrender.com"
                    st.session_state.mcp_session_url = None
                    
                    # Create Session
                    sse_response = requests.get(f"{base_url}/sse", stream=True, timeout=60)
                    for line in sse_response.iter_lines():
                        if line and line.decode('utf-8').startswith("data:"):
                            session_path = line.decode('utf-8').split("data: ")[1].strip()
                            st.session_state.mcp_session_url = f"{base_url}{session_path}"
                            break
                    
                    if not st.session_state.mcp_session_url:
                        raise Exception("Render MCP Session not created.")

                    st.info("✅ Connected. Sending your prompt...")

                    payload = {"prompt": prompt}
                    post_res = requests.post(st.session_state.mcp_session_url, json=payload, timeout=60)
                    
                    if post_res.status_code != 200:
                         raise Exception(f"Failed to send prompt. Status: {post_res.status_code}")

                    st.info("⏳ Video generation started. Waiting for result... (It may take a few minutes)")

                    video_url = None
                    response_text = ""
                    
                    stream_res = requests.get(f"{base_url}/sse", stream=True, timeout=300)
                    for line in stream_res.iter_lines():
                        if line:
                            decoded = line.decode('utf-8')
                            if decoded.startswith("data:"):
                                data_str = decoded.split("data: ")[1].strip()
                                try:
                                    data_json = json.loads(data_str)
                                    if "result" in data_json:
                                        content = data_json["result"].get("content", [])
                                        for item in content:
                                            if item.get("type") == "text":
                                                response_text += item.get("text", "") + "\n"
                                                if ".mp4" in response_text or "http" in response_text:
                                                    video_url = response_text.strip()
                                except:
                                    pass
                            if video_url:
                                break

                    if video_url:
                        st.write("✅ ویڈیو تیار ہے!")
                        st.session_state.mcp_chat_history.append({"role": "assistant", "content": "ویڈیو کامیابی سے بن گئی۔", "video_url": video_url})
                        st.video(video_url)
                        st.markdown(android_download_link(video_url, "⬇️ Download Video"), unsafe_allow_html=True)
                    else:
                        st.write(response_text if response_text else "رینڈر سے کوئی ویڈیو یا جواب موصول نہیں ہوا۔")
                        st.session_state.mcp_chat_history.append({"role": "assistant", "content": response_text or "کوئی جواب نہیں ملا۔", "video_url": None})

                except Exception as e:
                    st.error(f"❌ Connection Error: {str(e)}")

# ============================================================
# TAB 2 - IMAGE (Agnes)
# ============================================================

with tab2:
    st.markdown("### 🎨 Generate Images")
    st.info("✨ Create HD images from text descriptions — Powered by Agnes AI")

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
                    st.session_state.chat_messages.append({"role": "assistant", "content": result["result"]})
                else:
                    st.error(f"❌ {result['error']}")

# ============================================================
# TAB 4 - AI TOOLS (Agnes)
# ============================================================

with tab4:
    st.markdown("### 🛠️ AI Tools")
    st.caption("Powered by Agnes AI")

    tool_type = st.selectbox("Select Tool", ["SEO Generator", "Transcript Generator", "Text Summarizer", "Content Rewriter", "Translator"])
    target_language = "Urdu"
    if tool_type == "Translator":
        target_language = st.selectbox("Select Target Language", ["Urdu", "English", "Hindi", "Arabic", "French", "Spanish", "German", "Chinese", "Japanese", "Russian", "Portuguese"], index=0)

    tool_map = {"SEO Generator": "seo", "Transcript Generator": "transcript", "Text Summarizer": "summarize", "Content Rewriter": "rewrite", "Translator": "translate"}
    tool_key = tool_map.get(tool_type, "seo")

    tool_prompt = st.text_area(f"Enter your {tool_type.lower()} input", height=120, key="tool_prompt", placeholder="Type or paste your text here...")

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
st.caption("🎬 CraftReel AI · Video by Render MCP · Image, Chat, SEO by Agnes AI")
