import streamlit as st
import requests
import json
import time
from urllib.parse import quote

st.set_page_config(page_title="Render Video Generator", page_icon="🎬", layout="wide")

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
.download-btn {
    background-color: #4CAF50; color: white !important; padding: 12px;
    border-radius: 8px; text-align: center; display: block; margin-top: 10px;
    font-weight: bold; text-decoration: none !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>🎬 Google AI Edge Gallery</h1>
    <p>Powered by Render MCP</p>
</div>
""", unsafe_allow_html=True)

# چیٹ ہسٹری
if "mcp_chat_history" not in st.session_state:
    st.session_state.mcp_chat_history = []

def android_download_link(url, label="⬇️ Download Video"):
    if not url: return ""
    encoded_url = quote(str(url), safe="")
    return f'<a href="craftreel-download://download?url={encoded_url}" class="download-btn">{label}</a>'

# پرانی چیٹ دکھائیں
for msg in st.session_state.mcp_chat_history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "video_url" in msg and msg["video_url"]:
            st.video(msg["video_url"])
            st.markdown(android_download_link(msg["video_url"]), unsafe_allow_html=True)

# پرامپٹ لینے کے لیے چیٹ باکس
prompt = st.chat_input("Describe your video (e.g., 'Generate video with AI Edge Gallery: A dog running')...")

if prompt:
    st.session_state.mcp_chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("⏳ Connecting to Render & Generating... (Wait up to 5 mins)"):
            try:
                base_url = "https://video-generator-mcp.onrender.com"
                session_url = None
                
                # 1. رینڈر سے سیشن حاصل کریں (Timeout 60s is fine here)
                sse_response = requests.get(f"{base_url}/sse", stream=True, timeout=60)
                for line in sse_response.iter_lines():
                    if line and line.decode('utf-8').startswith("data:"):
                        session_path = line.decode('utf-8').split("data: ")[1].strip()
                        session_url = f"{base_url}{session_path}"
                        break
                
                if not session_url:
                    raise Exception("Render MCP Session not created. Server might be sleeping.")

                st.info("✅ Connected to Render. Sending your prompt...")

                # 2. پرامپٹ بھیجیں
                payload = {"prompt": prompt}
                
                # 🚨 یہاں وقت بڑھا دیا گیا ہے (300 سیکنڈ / 5 منٹ) تاکہ ویڈیو بن سکے
                post_res = requests.post(session_url, json=payload, timeout=300)
                
                if post_res.status_code != 200:
                     raise Exception(f"Failed to send prompt. Status: {post_res.status_code}")

                st.info("⏳ Generating video... (This takes time, please wait)")

                video_url = None
                response_text = ""
                
                # 3. ویڈیو کا انتظار کریں (Response Stream)
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

                # 4. نتیجہ دکھائیں
                if video_url:
                    st.write("✅ ویڈیو تیار ہے!")
                    st.session_state.mcp_chat_history.append({
                        "role": "assistant", 
                        "content": "ویڈیو کامیابی سے بن گئی۔",
                        "video_url": video_url
                    })
                    st.video(video_url)
                    st.markdown(android_download_link(video_url), unsafe_allow_html=True)
                else:
                    st.write(response_text if response_text else "رینڈر سے کوئی ویڈیو یا جواب موصول نہیں ہوا۔")
                    st.session_state.mcp_chat_history.append({
                        "role": "assistant", 
                        "content": response_text or "کوئی جواب نہیں ملا۔",
                        "video_url": None
                    })

            except requests.exceptions.Timeout:
                st.error("⏳ ٹائم آؤٹ: رینڈر جاگ نہیں پایا یا ویڈیو بننے میں بہت زیادہ وقت لگا۔")
            except Exception as e:
                st.error(f"❌ Connection Error: {str(e)}")