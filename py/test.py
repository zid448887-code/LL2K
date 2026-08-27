import os
import asyncio
import time
import tempfile
import subprocess
import streamlit as st
from faster_whisper import WhisperModel
import translators as ts
import edge_tts

st.set_page_config(page_title="翻译视频", page_icon="阿杰", layout="centered")

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.15);
    }
    .stButton>button {
        width: 100%;
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        padding: 10px;
        border: none;
    }
</style>
""", unsafe_allow_html=True)
APP_PASSWORD = "ajiechanbomaydi"

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.markdown("<div class='main-header'><h1>请输入密码</h1><p>请输入访问密码以继续使用系统</p></div>", unsafe_allow_html=True)
    with st.form("login_form"):
        pwd_input = st.text_input("密码:", type="password")
        submit_btn = st.form_submit_button("登录")
        if submit_btn:
            if pwd_input == APP_PASSWORD:
                st.session_state["authenticated"] = True
                st.success("登录成功!")
                st.rerun()
            else:
                st.error("密码错误，请重试!")
    st.stop()

LANGUAGE_MAP = {
    "越南🇻🇳": {"lang": "vi", "voice": "vi-VN-HoaiMyNeural"},
    "英语🏴󠁧󠁢󠁥󠁮󠁧󠁿": {"lang": "en", "voice": "en-US-AriaNeural"},
    "中文 (简体)🇨🇳": {"lang": "zh-Hans", "voice": "zh-CN-XiaoxiaoNeural"},
    "日语🇯🇵": {"lang": "ja", "voice": "ja-JP-NanamiNeural"},
    "韩语🇰🇷": {"lang": "ko", "voice": "ko-KR-SunHiNeural"},
    "西班牙语🇪🇸": {"lang": "es", "voice": "es-ES-ElviraNeural"},
    "法语🇫🇷": {"lang": "fr", "voice": "fr-FR-DeniseNeural"},
    "俄语🇷🇺": {"lang": "ru", "voice": "ru-RU-SvetlanaNeural"},
    "葡萄牙语🇵🇹": {"lang": "pt", "voice": "pt-BR-FranciscaNeural"}
}

def extract_audio(video_path, audio_output_path):
    command = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        audio_output_path
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@st.cache_resource
def load_whisper_model():
    return WhisperModel("tiny", device="cpu", compute_type="int8")

def transcribe_audio(audio_path):
    model = load_whisper_model()
    segments, info = model.transcribe(audio_path, beam_size=1)
    text = " ".join([segment.text.strip() for segment in segments])
    return info.language, text

def translate_text(text, target_lang):
    if not text.strip():
        return ""
    
    lang_code = "zh-Hans" if target_lang in ["zh-CN", "zh-Hans"] else target_lang

    engines = ['bing', 'google', 'yandex']
    
    for engine in engines:
        try:
            res = ts.translate_text(
                query_text=text,
                translator=engine,
                from_language='auto',
                to_language=lang_code
            )
            if res and "Error 500" not in str(res):
                return res
        except Exception:
            continue
            
    return text

def run_tts_sync(text, output_audio_path, voice):
    async def _tts():
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_audio_path)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_tts())
    finally:
        loop.close()

def merge_audio_to_video(video_path, new_audio_path, output_video_path):
    command = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", new_audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        output_video_path
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

st.markdown("<div class='main-header'><h1> 系统翻译视频</h1><p>请上传视频，系统自动翻译!</p></div>", unsafe_allow_html=True)

col1, col2 = st.columns([5, 1])
with col2:
    if st.button("退出登录"):
        st.session_state["authenticated"] = False
        st.rerun()

uploaded_file = st.file_uploader("选择您的视频文件（MP4、AVI、MOV）:", type=["mp4", "avi", "mov"])
selected_language_name = st.selectbox("选择目标翻译语言:", list(LANGUAGE_MAP.keys()))

if uploaded_file is not None:
    st.video(uploaded_file)
    if st.button("开始视频处理"):
        with st.spinner("正在处理……请稍候..."):
            with tempfile.TemporaryDirectory() as temp_dir:
                input_video_path = os.path.join(temp_dir, "temp_input.mp4")
                output_video_path = os.path.join(temp_dir, "temp_output.mp4")
                temp_audio = os.path.join(temp_dir, "temp_original_audio.wav")
                temp_translated_audio = os.path.join(temp_dir, "temp_translated_audio.mp3")

                with open(input_video_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                try:
                    st.text("从视频中提取音频...")
                    extract_audio(input_video_path, temp_audio)
                    
                    st.text("利用 AI 识别语音...")
                    detected_lang, original_text = transcribe_audio(temp_audio)
                    st.info(f"本源语言: **{detected_lang}**")
                    
                    st.write("📝 **本原内容:**")
                    st.code(original_text, language=None)
                    
                    target_lang_code = LANGUAGE_MAP[selected_language_name]["lang"]
                    target_voice = LANGUAGE_MAP[selected_language_name]["voice"]
                    
                    st.text(f"正在翻译到 {selected_language_name}...")
                    translated_text = translate_text(original_text, target_lang_code)
                    
                    st.write("🌐 **内容翻译 (点击右上角按钮复制):**")
                    st.code(translated_text, language=None)
                    
                    st.text("正在生成新的声音...")
                    run_tts_sync(translated_text, temp_translated_audio, target_voice)
                    
                    st.text("正在替换视频音频...")
                    merge_audio_to_video(input_video_path, temp_translated_audio, output_video_path)
                    
                    st.success("处理视频成功!")
                    st.subheader("视频翻译结果:")
                    
                    with open(output_video_path, "rb") as file:
                        video_bytes = file.read()
                        st.video(video_bytes)
                        st.download_button(
                            label="下载视频",
                            data=video_bytes,
                            file_name="translated_video.mp4",
                            mime="video/mp4"
                        )
                except Exception as e:
                    st.error(f"出现错误: {e}")