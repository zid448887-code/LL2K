import os
import asyncio
import tempfile
import subprocess
import streamlit as st
from faster_whisper import WhisperModel
import translators as ts
import edge_tts

st.set_page_config(page_title="阿杰", page_icon="♦️", layout="centered")

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
    st.markdown("<div class='main-header'><h1>系统登录</h1><p>请输入登录密码🆓</p></div>", unsafe_allow_html=True)
    with st.form("login_form"):
        pwd_input = st.text_input("密码:", type="password")
        if st.form_submit_button("登录"):
            if pwd_input == APP_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("密码错误!")
    st.stop()

LANGUAGE_MAP = {
    "越南语 🇻🇳": {"lang": "vi", "voice": "vi-VN-HoaiMyNeural"},
    "英语 🏴󠁧󠁢󠁥󠁮󠁧󠁿": {"lang": "en", "voice": "en-US-AriaNeural"},
    "中文 (简体) 🇨🇳": {"lang": "zh-Hans", "voice": "zh-CN-XiaoxiaoNeural"},
    "日语 🇯🇵": {"lang": "ja", "voice": "ja-JP-NanamiNeural"},
    "韩语 🇰🇷": {"lang": "ko", "voice": "ko-KR-SunHiNeural"},
    "西班牙语 🇪🇸": {"lang": "es", "voice": "es-ES-ElviraNeural"},
    "法语 🇫🇷": {"lang": "fr", "voice": "fr-FR-DeniseNeural"},
}

def extract_audio(video_path, audio_output_path):
    command = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        audio_output_path
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

@st.cache_resource
def load_whisper_model():
    return WhisperModel("base", device="cpu", compute_type="int8")

def translate_text(text, target_lang):
    if not text.strip():
        return ""
    lang_code = "zh-Hans" if target_lang in ["zh-CN", "zh-Hans"] else target_lang
    for engine in ['bing', 'google']:
        try:
            res = ts.translate_text(query_text=text, translator=engine, from_language='auto', to_language=lang_code)
            if res and "Error 500" not in str(res):
                return res
        except:
            continue
    return text

async def text_to_speech_file(text, voice, out_path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)

st.markdown("<div class='main-header'><h1>系统翻译视频</h1><p></p></div>", unsafe_allow_html=True)

if st.button("退出"):
    st.session_state["authenticated"] = False
    st.rerun()

uploaded_file = st.file_uploader("筛选视频 (MP4, AVI, MOV):", type=["mp4", "avi", "mov"])
selected_language_name = st.selectbox("筛选语言:", list(LANGUAGE_MAP.keys()))

if uploaded_file is not None:
    st.video(uploaded_file)
    if st.button("开始处理"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            input_video = os.path.join(temp_dir, "input.mp4")
            audio_path = os.path.join(temp_dir, "audio.wav")
            output_video = os.path.join(temp_dir, "output.mp4")
            
            with open(input_video, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            try:
                status_text.text(" 正在从视频中提取音频...")
                progress_bar.progress(20)
                extract_audio(input_video, audio_path)
                
                status_text.text("你的杰哥 正在分析语音和时机。...")
                progress_bar.progress(40)
                model = load_whisper_model()
                segments, info = model.transcribe(audio_path, beam_size=5)
                
                segment_list = list(segments)
                detected_lang = info.language
                detected_lang_prob = info.language_probability
                
                target_lang_code = LANGUAGE_MAP[selected_language_name]["lang"]
                target_voice = LANGUAGE_MAP[selected_language_name]["voice"]
                
                original_transcript = []
                translated_transcript = []
                
                status_text.text("正在将内容翻译成新语言……...")
                progress_bar.progress(60)
                
                translated_audio_parts = []
                for i, seg in enumerate(segment_list):
                    orig_text = seg.text.strip()
                    if not orig_text:
                        continue
                    original_transcript.append(f"[{seg.start:.1f}s -> {seg.end:.1f}s]: {orig_text}")
                    
                    trans_text = translate_text(orig_text, target_lang_code)
                    translated_transcript.append(trans_text)
                    
                    part_audio = os.path.join(temp_dir, f"part_{i}.mp3")
                    asyncio.run(text_to_speech_file(trans_text, target_voice, part_audio))
                    translated_audio_parts.append(part_audio)

                st.write(f" **原版 (检测到的语言: {detected_lang} - 精准: {detected_lang_prob:.2f}):**")
                st.code("\n".join(original_transcript), language=None)
                
                st.write(f" **相应的翻译 (目标语言: {selected_language_name}):**")
                st.code("\n".join(translated_transcript), language=None)
                
                status_text.text("目前正在合成并组装完整的音频。...")
                progress_bar.progress(80)
                
                concat_list_path = os.path.join(temp_dir, "concat.txt")
                with open(concat_list_path, "w", encoding="utf-8") as f_concat:
                    for p in translated_audio_parts:
                        f_concat.write(f"file '{p}'\n")
                
                full_translated_audio = os.path.join(temp_dir, "full_trans.mp3")
                cmd_concat = [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", concat_list_path, "-c", "copy", full_translated_audio
                ]
                subprocess.run(cmd_concat, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                status_text.text("最终视频打包...")
                progress_bar.progress(95)
                
                cmd_merge = [
                    "ffmpeg", "-y", "-i", input_video, "-i", full_translated_audio,
                    "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0",
                    output_video
                ]
                subprocess.run(cmd_merge, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                progress_bar.progress(100)
                status_text.text("视频处理成功!")
                
                st.success("好了！您可以观看 or 下载下方的视频。:")
                with open(output_video, "rb") as vf:
                    video_bytes = vf.read()
                    st.video(video_bytes)
                    st.download_button("下载已翻译的视频", data=video_bytes, file_name="ai_translated_video.mp4", mime="video/mp4")
                    
            except Exception as e:
                st.error(f"处理过程中发生错误。: {e}")