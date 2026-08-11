import streamlit as st
import requests
import time
import os
# from dotenv import load_dotenv

# load_dotenv()
# API_KEY = os.getenv("AGNES_API_KEY")

# if not API_KEY:
#     st.error("⚠️ براہ کرم .env فائل میں API Key ڈالیں")
#     st.stop()

# 👇 اپنی اصلی API Key یہاں ڈالیں
API_KEY = "sk-MPjWDba75dNViRADiz42uIzGvYQMEBSB7lLE83J6QNRSU5hY"

BASE_URL = "https://apihub.agnes-ai.com/v1"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

st.set_page_config(page_title="Agnes AI Tool", layout="wide")
st.title("🤖 Agnes AI - Multi Tool")

tab1, tab2, tab3 = st.tabs(["💬 چیٹ", "🖼️ تصویر", "🎬 ویڈیو"])

# ====== CHAT ======
with tab1:
    st.subheader("💬 Agnes AI سے بات کریں")
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    
    if prompt := st.chat_input("اپنا پیغام لکھیں..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("سوچ رہا ہوں..."):
                try:
                    response = requests.post(
                        f"{BASE_URL}/chat/completions",
                        headers=HEADERS,
                        json={
                            "model": "agnes-2.5-flash",
                            "messages": st.session_state.messages
                        }
                    )
                    if response.status_code == 200:
                        reply = response.json()["choices"][0]["message"]["content"]
                        st.write(reply)
                        st.session_state.messages.append({"role": "assistant", "content": reply})
                    else:
                        st.error(f"Error: {response.status_code}")
                except Exception as e:
                    st.error(f"Error: {e}")

# ====== IMAGE ======
with tab2:
    st.subheader("🖼️ تصویر بنائیں")
    prompt_img = st.text_area("تصویر کی تفصیل", height=100)
    col1, col2 = st.columns(2)
    with col1:
        size = st.selectbox("سائز", ["1K", "2K", "3K", "4K"])
    with col2:
        ratio = st.selectbox("نسبت", ["1:1", "16:9", "9:16"])
    
    if st.button("🎨 تصویر بنائیں"):
        if prompt_img:
            with st.spinner("تصویر بن رہی ہے..."):
                try:
                    response = requests.post(
                        f"{BASE_URL}/images/generations",
                        headers=HEADERS,
                        json={
                            "model": "agnes-image-2.1-flash",
                            "prompt": prompt_img,
                            "size": size,
                            "ratio": ratio,
                            "extra_body": {"response_format": "url"}
                        }
                    )
                    if response.status_code == 200:
                        img_url = response.json()["data"][0]["url"]
                        st.image(img_url, use_container_width=True)
                    else:
                        st.error(f"Error: {response.status_code}")
                except Exception as e:
                    st.error(f"Error: {e}")

# ====== VIDEO ======
with tab3:
    st.subheader("🎬 ویڈیو بنائیں")
    st.info("⏳ ویڈیو بننے میں 10-30 سیکنڈ لگ سکتے ہیں")
    video_prompt = st.text_area("ویڈیو کی تفصیل", height=100)
    
    if st.button("🎬 ویڈیو بنائیں"):
        if video_prompt:
            with st.spinner("ویڈیو بن رہی ہے..."):
                try:
                    response = requests.post(
                        f"{BASE_URL}/videos",
                        headers=HEADERS,
                        json={
                            "model": "agnes-video-v2.0",
                            "prompt": video_prompt,
                            "height": 768,
                            "width": 1152,
                            "num_frames": 121,
                            "frame_rate": 24
                        }
                    )
                    if response.status_code == 200:
                        video_id = response.json()["video_id"]
                        st.success(f"Task ID: {video_id}")
                        
                        video_url = None
                        for i in range(15):
                            time.sleep(2)
                            status = requests.get(
                                f"https://apihub.agnes-ai.com/agnesapi?video_id={video_id}",
                                headers=HEADERS
                            )
                            if status.status_code == 200:
                                data = status.json()
                                if "metadata" in data and "url" in data["metadata"]:
                                    video_url = data["metadata"]["url"]
                                    break
                        
                        if video_url:
                            st.success("✅ ویڈیو تیار ہے!")
                            st.video(video_url)
                        else:
                            st.warning("⏳ ویڈیو ابھی تیار نہیں")
                    else:
                        st.error(f"Error: {response.status_code}")
                except Exception as e:
                    st.error(f"Error: {e}")

st.caption("🔐 Powered by Agnes AI API")