import os
import asyncio
import streamlit as st
import whisper
from deep_translator import GoogleTranslator
import edge_tts
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.io.AudioFileClip import AudioFileClip

st.set_page_config(page_title="翻译视频", layout="centered")
st.title("翻译视频")
st.write("请上传视频，系统自动翻译!")

LANGUAGE_MAP = {
    "越南": {"lang": "vi", "voice": "vi-VN-HoaiMyNeural"},
    "英语": {"lang": "en", "voice": "en-US-AriaNeural"},
    "中文 (简体)": {"lang": "zh-CN", "voice": "zh-CN-XiaoxiaoNeural"}, # Đã sửa "LANG" -> "lang"
    "日语": {"lang": "ja", "voice": "ja-JP-NanamiNeural"},
    "韩语": {"lang": "ko", "voice": "ko-KR-SunHiNeural"},
    "西班牙语": {"lang": "es", "voice": "es-ES-ElviraNeural"},
    "法语": {"lang": "fr", "voice": "fr-FR-DeniseNeural"}
}

def extract_audio(video_path, audio_output_path):
    video = VideoFileClip(video_path)
    video.audio.write_audiofile(audio_output_path, logger=None)
    video.close()

@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")

def transcribe_audio(audio_path):
    model = load_whisper_model()
    result = model.transcribe(audio_path, task="transcribe")
    return result['language'], result['text']

def translate_text(text, target_lang):
    translated = GoogleTranslator(source='auto', target=target_lang).translate(text)
    return translated

async def text_to_speech(text, output_audio_path, voice):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_audio_path)

def merge_audio_to_video(video_path, new_audio_path, output_video_path):
    video = VideoFileClip(video_path)
    new_audio = AudioFileClip(new_audio_path)
    final_video = video.set_audio(new_audio)
    final_video.write_videofile(output_video_path, codec="libx264", audio_codec="aac", logger=None)
    video.close()
    new_audio.close()

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
            temp_audio = "temp_original_audio.mp3"
            temp_translated_audio = "temp_translated_audio.mp3"
            
            try:
                st.text("从视频中提取音频。...")
                extract_audio(input_video_path, temp_audio)
                
                st.text("利用人工智能分析和识别语音。...")
                detected_lang, original_text = transcribe_audio(temp_audio)
                st.info(f"本源语言: **{detected_lang}**")
                st.write(f"📝 **本原内容:** {original_text}")
                
                target_lang_code = LANGUAGE_MAP[selected_language_name]["lang"]
                target_voice = LANGUAGE_MAP[selected_language_name]["voice"]
                
                st.text(f"正在翻译到 {selected_language_name}...")
                translated_text = translate_text(original_text, target_lang_code)
                st.write(f"🌐 **内用翻译:** {translated_text}")
                
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
                # Chỉ dọn dẹp file tạm, giữ lại output cho người dùng tải
                for f in [input_video_path, temp_audio, temp_translated_audio]:
                    if os.path.exists(f): 
                        os.remove(f)