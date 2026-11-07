# ============================================================
# TAB 1 - VIDEO (Render MCP Live Chat & Generation)
# ============================================================

if "mcp_chat_history" not in st.session_state:
    st.session_state.mcp_chat_history = []
if "mcp_session_url" not in st.session_state:
    st.session_state.mcp_session_url = None

with tab1:
    st.markdown("### 🎬 Generate Video via Render MCP")
    st.caption("Powered by Google AI Edge Gallery (via Render) · Live Chat Session")

    # چیٹ ہسٹری دکھائیں
    for msg in st.session_state.mcp_chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if "video_url" in msg and msg["video_url"]:
                st.video(msg["video_url"])
                st.markdown(
                    android_download_link(msg["video_url"], "⬇️ Download Video"),
                    unsafe_allow_html=True
                )

    # صارف کا پرامپٹ لینے کے لیے چیٹ باکس
    prompt = st.chat_input("Describe your video (e.g., 'Generate video with AI Edge Gallery: A dog running')...")

    if prompt:
        # صارف کا پیغام شامل کریں
        st.session_state.mcp_chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("⏳ Connecting to Render MCP & Generating..."):
                try:
                    import requests
                    import json
                    
                    base_url = "https://video-generator-mcp.onrender.com"
                    
                    # نیا سیشن بنائیں
                    st.session_state.mcp_session_url = None
                    sse_response = requests.get(f"{base_url}/sse", stream=True, timeout=60)
                    for line in sse_response.iter_lines():
                        if line and line.decode('utf-8').startswith("data:"):
                            session_path = line.decode('utf-8').split("data: ")[1].strip()
                            st.session_state.mcp_session_url = f"{base_url}{session_path}"
                            break
                    
                    if not st.session_state.mcp_session_url:
                        raise Exception("Render MCP Session not created.")

                    st.info("✅ Connected. Sending your prompt...")

                    # آپ کا ایم سی پی نیچرل لینگویج سمجھتا ہے، اس لیے ہم سیدھا پرامپٹ بھیج رہے ہیں
                    # (اگر اسے خاص فارمیٹ چاہیے تو یہاں تبدیلی کی جا سکتی ہے)
                    payload = {"prompt": prompt}
                    
                    post_res = requests.post(st.session_state.mcp_session_url, json=payload, timeout=60)
                    
                    if post_res.status_code != 200:
                         raise Exception(f"Failed to send prompt. Status: {post_res.status_code}")

                    st.info("⏳ Video generation started. Waiting for result... (It may take a few minutes)")

                    # جواب کا انتظار کریں
                    video_url = None
                    response_text = ""
                    
                    # 5 منٹ تک ویڈیو کا انتظار کریں
                    stream_res = requests.get(f"{base_url}/sse", stream=True, timeout=300)
                    for line in stream_res.iter_lines():
                        if line:
                            decoded = line.decode('utf-8')
                            if decoded.startswith("data:"):
                                data_str = decoded.split("data: ")[1].strip()
                                try:
                                    data_json = json.loads(data_str)
                                    
                                    # جواب چیک کریں
                                    if "result" in data_json:
                                        content = data_json["result"].get("content", [])
                                        for item in content:
                                            if item.get("type") == "text":
                                                response_text += item.get("text", "") + "\n"
                                                # اگر لنک ملا تو اسے ویڈیو سمجھیں
                                                if ".mp4" in response_text or "http" in response_text:
                                                    video_url = response_text.strip()
                                except:
                                    pass
                            
                            if video_url:
                                break

                    # نتیجہ دکھائیں
                    if video_url:
                        st.write("✅ ویڈیو تیار ہے!")
                        st.session_state.mcp_chat_history.append({
                            "role": "assistant", 
                            "content": "ویڈیو کامیابی سے بن گئی۔",
                            "video_url": video_url
                        })
                        st.video(video_url)
                        st.markdown(android_download_link(video_url, "⬇️ Download Video"), unsafe_allow_html=True)
                    else:
                        # اگر صرف ٹیکسٹ آیا (جیسے اس نے کوئی سوال پوچھا ہو)
                        st.write(response_text if response_text else "رینڈر سے کوئی ویڈیو یا جواب موصول نہیں ہوا۔")
                        st.session_state.mcp_chat_history.append({
                            "role": "assistant", 
                            "content": response_text or "کوئی جواب نہیں ملا۔",
                            "video_url": None
                        })

                except requests.exceptions.Timeout:
                    st.error("⏳ ٹائم آؤٹ: ویڈیو بننے میں بہت زیادہ وقت لگا۔")
                except Exception as e:
                    st.error(f"❌ Connection Error: {str(e)}")