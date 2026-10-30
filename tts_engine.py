"""Standalone Neural TTS Engine
Handles:
- Natural text segmentation (clauses and sentences)
- Async Edge-TTS neural speech synthesis with network retries
- MD5-based disk caching to avoid redundant downloads
- Decoding to uncompressed 24kHz float32 buffers
"""
import os, re, io, json, asyncio, hashlib, subprocess
import numpy as np
import soundfile as sf
import edge_tts
from audio_processor import SR, trim_silence, compress, limit

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache')
os.makedirs(CACHE_DIR, exist_ok=True)

DEFAULT_VOICE = "zh-CN-YunxiNeural"  # Clear, narrative, broadcast-quality Chinese voice

def split_text_into_clauses(text, min_len=4, max_len=35):
    """
    Intelligently split paragraphs/sentences into natural speakable phrases.
    Splits by punctuation: 。！？；\n and handles long comma-separated clauses.
    """
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    segments = []
    
    for line in lines:
        # Split by strong sentence boundaries (。！？!?)
        raw_sentences = re.split(r'([。！？!?；;\n]+)', line)
        combined = []
        for i in range(0, len(raw_sentences) - 1, 2):
            sent = raw_sentences[i].strip() + raw_sentences[i+1].strip()
            if sent:
                combined.append(sent)
        if len(raw_sentences) % 2 == 1 and raw_sentences[-1].strip():
            combined.append(raw_sentences[-1].strip())

        for sent in combined:
            # If a single sentence is excessively long, split by commas
            if len(sent) > max_len and ('，' in sent or ',' in sent):
                comma_parts = re.split(r'([，,])', sent)
                curr = ""
                for j in range(0, len(comma_parts) - 1, 2):
                    part = comma_parts[j].strip() + comma_parts[j+1].strip()
                    if len(curr) + len(part) <= max_len:
                        curr += part
                    else:
                        if curr: segments.append(curr)
                        curr = part
                if len(comma_parts) % 2 == 1 and comma_parts[-1].strip():
                    curr += comma_parts[-1].strip()
                if curr: segments.append(curr)
            else:
                segments.append(sent)

    return segments if segments else [text.strip()]

def get_cache_path(text, voice, rate, pitch):
    key = f"{text}|{voice}|{rate}|{pitch}"
    md5 = hashlib.md5(key.encode('utf-8')).hexdigest()
    return os.path.join(CACHE_DIR, f"{md5}.mp3")

async def synthesize_sentence_async(text, voice=DEFAULT_VOICE, rate="+0%", pitch="+0Hz"):
    """Synthesize a single sentence with Edge-TTS, using disk cache and retry logic."""
    cache_file = get_cache_path(text, voice, rate, pitch)
    
    if not os.path.exists(cache_file) or os.path.getsize(cache_file) == 0:
        part_file = cache_file + ".part"
        last_error = None
        for attempt in range(3):
            try:
                communicator = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
                await communicator.save(part_file)
                if os.path.exists(part_file) and os.path.getsize(part_file) > 0:
                    os.replace(part_file, cache_file)
                    break
            except Exception as e:
                last_error = e
                if "NoAudioReceived" in str(type(e)):
                    break
                await asyncio.sleep(1.0 * (attempt + 1))
        else:
            if os.path.exists(part_file):
                os.remove(part_file)
            raise RuntimeError(f"Edge-TTS synthesis failed after 3 attempts: {last_error}")

    # Decode MP3 to 24kHz float32 mono array using ffmpeg
    cmd = [
        'ffmpeg', '-y', '-loglevel', 'error',
        '-i', cache_file,
        '-ar', str(SR),
        '-ac', '1',
        '-f', 'wav', '-'
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    audio_data, sr_read = sf.read(io.BytesIO(proc.stdout), dtype='float32')
    
    # Clean up acoustic boundaries and apply gentle compression
    audio_trimmed = trim_silence(audio_data, sr=SR)
    audio_comp = compress(audio_trimmed, thr=0.25, ratio=2.8)
    return limit(audio_comp, ceiling=0.98)

def synthesize_sentence(text, voice=DEFAULT_VOICE, rate="+0%", pitch="+0Hz"):
    """Synchronous wrapper for synthesize_sentence_async."""
    return asyncio.run(synthesize_sentence_async(text, voice=voice, rate=rate, pitch=pitch))
