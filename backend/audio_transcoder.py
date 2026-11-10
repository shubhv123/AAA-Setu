import logging
import subprocess
import imageio_ffmpeg
from typing import Optional

logger = logging.getLogger("aaa_setu.transcoder")

_ffmpeg_bin: Optional[str] = None

def get_ffmpeg_binary() -> str:
    global _ffmpeg_bin
    if _ffmpeg_bin is None:
        _ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
    return _ffmpeg_bin

def any_audio_to_pcm_wav(audio_bytes: bytes, target_sample_rate: int = 16000) -> bytes:
    """
    Transcodes any input audio container (OGG Opus, WebM, MP3, AAC, WAV) into
    standard 16-bit little-endian mono Linear PCM WAV at 16,000 Hz, strictly formatted
    for Gnani Prisma STT (avoids HTTP 400 AUDIO_CONVERSION_ERROR).
    """
    if not audio_bytes:
        raise ValueError("audio_bytes cannot be empty.")

    ffmpeg = get_ffmpeg_binary()
    cmd = [
        ffmpeg,
        "-y",
        "-i", "pipe:0",
        "-f", "wav",
        "-acodec", "pcm_s16le",
        "-ac", "1",
        "-ar", str(target_sample_rate),
        "pipe:1"
    ]

    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    out_bytes, err_bytes = process.communicate(input=audio_bytes)
    if process.returncode != 0:
        err_msg = err_bytes.decode("utf-8", errors="replace")
        logger.error(f"FFmpeg transcoding to PCM WAV failed: {err_msg}")
        raise RuntimeError(f"Audio transcoding to WAV failed: {err_msg}")

    return out_bytes

def wav_to_ogg_opus(wav_bytes: bytes) -> bytes:
    """
    Converts 16kHz PCM WAV into WhatsApp voice note format (audio/ogg with opus codec)
    at 32kbps for fast, ultra-low-bandwidth delivery to frontline workers in 2G areas.
    """
    if not wav_bytes:
        raise ValueError("wav_bytes cannot be empty.")

    ffmpeg = get_ffmpeg_binary()
    cmd = [
        ffmpeg,
        "-y",
        "-i", "pipe:0",
        "-c:a", "libopus",
        "-b:a", "32k",
        "-f", "ogg",
        "pipe:1"
    ]

    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    out_bytes, err_bytes = process.communicate(input=wav_bytes)
    if process.returncode != 0:
        err_msg = err_bytes.decode("utf-8", errors="replace")
        logger.error(f"FFmpeg transcoding to OGG Opus failed: {err_msg}")
        raise RuntimeError(f"Audio transcoding to OGG Opus failed: {err_msg}")

    return out_bytes

