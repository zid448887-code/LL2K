import os
import asyncio
import time
import subprocess
import streamlit as st
from faster_whisper import WhisperModel
from deep_translator import GoogleTranslator
import edge_tts

# 设置页面
st.set_page_config(page_title="翻译视频", page_icon="🎬", layout="centered")

# Custom CSS
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

# 1. 密码验证功能
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

# 2. 语言列表
LANGUAGE_MAP = {
    "越南": {"lang": "vi", "voice": "vi-VN-HoaiMyNeural"},
    "英语": {"lang": "en", "voice": "en-US-AriaNeural"},
    "中文 (简体)": {"lang": "zh-CN", "voice": "zh-CN-XiaoxiaoNeural"},
    "日语": {"lang": "ja", "voice": "ja-JP-NanamiNeural"},
    "韩语": {"lang": "ko", "voice": "ko-KR-SunHiNeural"},
    "西班牙语": {"lang": "es", "voice": "es-ES-ElviraNeural"},
    "法语": {"lang": "fr", "voice": "fr-FR-DeniseNeural"},
    "俄语": {"lang": "ru", "voice": "ru-RU-SvetlanaNeural"},
    "葡萄牙语": {"lang": "pt", "voice": "pt-BR-FranciscaNeural"}
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
    # Sử dụng faster-whisper tiny chạy trên CPU bằng int8 (cực nhẹ và cực nhanh)
    return WhisperModel("tiny", device="cpu", compute_type="int8")

def transcribe_audio_fast(audio_path):
    model = load_whisper_model()
    segments, info = model.transcribe(audio_path, beam_size=1)
    text = "".join([segment.text for segment in segments])
    return info.language, text

def translate_text(text, target_lang):
    for attempt in range(3):
        try:
            translated = GoogleTranslator(source='auto', target=target_lang).translate(text)
            return translated
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)

async def text_to_speech(text, output_audio_path, voice):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_audio_path)

def merge_audio_to_video(video_path, new_audio_path, output_video_path):
    # Ghép nhạc bằng FFmpeg trực tiếp (-c:v copy), không mã hóa lại video -> Nhanh tức thì!
    command = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", new_audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        output_video_path
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# 主界面
st.markdown("<div class='main-header'><h1>🎬 翻译视频 (极速 organization 版)</h1><p>请上传视频，系统自动翻译!</p></div>", unsafe_allow_html=True)

col1, col2 = st.columns([5, 1])
with col2:
    if st.button("退出登录"):
        st.session_state["authenticated"] = False
        st.rerun()

uploaded_file = st.file_uploader("选择您的视频文件（MP4、AVI、MOV）:", type=["mp4", "avi", "mov"])
selected_language_name = st.selectbox("选择目标翻译语言。:", list(LANGUAGE_MAP.keys()))

if uploaded_file is not None:
    st.video(uploaded_file)
    if st.button("开始视频处理"):
        with st.spinner("正在处理……请稍候。."):
            input_video_path = "temp_input.mp4"
            with open(input_video_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            output_video_path = "temp_output.mp4"
            temp_audio = "temp_original_audio.wav"
            temp_translated_audio = "temp_translated_audio.mp3"
            
            try:
                st.text("从视频中提取音频。...")
                extract_audio(input_video_path, temp_audio)
                
                st.text("利用 AI 极速识别语音...")
                detected_lang, original_text = transcribe_audio_fast(temp_audio)
                st.info(f"本源语言: **{detected_lang}**")
                
                st.write("📝 **本原内容:**")
                st.code(original_text, language=None)
                
                target_lang_code = LANGUAGE_MAP[selected_language_name]["lang"]
                target_voice = LANGUAGE_MAP[selected_language_name]["voice"]
                
                st.text(f"正在翻译到 {selected_language_name}...")
                translated_text = translate_text(original_text, target_lang_code)
                
                st.write("🌐 **内用翻译 (点击右上角按钮复制):**")
                st.code(translated_text, language=None)
                
                st.text("正在弄新的声音...")
                asyncio.run(text_to_speech(translated_text, temp_translated_audio, target_voice))
                
                st.text("跟换视频...")
                merge_audio_to_video(input_video_path, temp_translated_audio, output_video_path)
                
                st.success("处理视频成功!")
                st.subheader("视频翻译:")
                st.video(output_video_path)
                
                with open(output_video_path, "rb") as file:
                    st.download_button(
                        label="下载视频",
                        data=file,
                        file_name="translated_video.mp4",
                        mime="video/mp4"
                    )
            except Exception as e:
                st.error(f"出现错误: {e}")
            finally:
                for f in [input_video_path, temp_audio, temp_translated_audio, output_video_path]:
                    if os.path.exists(f): 
                        os.remove(f)