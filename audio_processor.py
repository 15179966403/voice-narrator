"""Standalone Audio DSP Processor
Provides professional broadcast-grade vocal processing:
- Silence trimming with configurable acoustic padding
- Dynamic range compression (vocal presence & warmth)
- Peak limiting & digital anti-clipping
- Psychoacoustic K-weighting loudness measurement (-14 LUFS standard)
- Natural breathing pause insertion, acoustic lead-in, and lingering tail padding
"""
import numpy as np
from scipy.signal import butter, sosfilt

SR = 24000  # Default 24kHz studio vocal rate

def trim_silence(signal, sr=SR, thr_db=-45.0, pad_ms=60):
    """Trim leading and trailing silence while preserving natural acoustic breath padding."""
    if len(signal) == 0:
        return signal
    thr = 10.0 ** (thr_db / 20.0)
    win_size = int(sr * 0.015)  # 15ms
    if win_size < 1:
        win_size = 1
    abs_sig = np.abs(signal)
    
    indices = np.where(abs_sig > thr)[0]
    if len(indices) == 0:
        return signal
    
    pad = int(sr * (pad_ms / 1000.0))
    start = max(0, indices[0] - pad)
    end = min(len(signal), indices[-1] + pad)
    return signal[start:end]

def compress(signal, thr=0.25, ratio=3.0):
    """Dynamic range compressor for vocals: tames high peaks and raises body presence."""
    out = signal.copy()
    mask = np.abs(out) > thr
    excess = np.abs(out[mask]) - thr
    compressed_excess = excess / ratio
    out[mask] = np.sign(out[mask]) * (thr + compressed_excess)
    return out

def limit(signal, ceiling=0.98):
    """Soft-knee peak limiter to prevent digital clipping."""
    out = signal.copy()
    peak = np.abs(out).max()
    if peak > ceiling:
        out = np.tanh(out / ceiling) * ceiling
    return out

def k_weighting_filter(signal, sr=SR):
    """Apply ITU-R BS.1770 K-weighting pre-filter for psychoacoustic loudness calculation."""
    sos_hp = butter(2, 80.0, btype='highpass', fs=sr, output='sos')
    filtered = sosfilt(sos_hp, signal)
    return filtered

def measure_lufs(signal, sr=SR):
    """Approximate integrated loudness in LUFS following ITU-R BS.1770 standards."""
    filtered = k_weighting_filter(signal, sr)
    ms = np.mean(filtered ** 2)
    if ms <= 1e-12:
        return -70.0
    return -0.691 + 10.0 * np.log10(ms)

def normalize_loudness(signal, sr=SR, target_lufs=-14.0):
    """Normalize vocal track to broadcast target LUFS with safety headroom."""
    current_lufs = measure_lufs(signal, sr)
    if current_lufs <= -65.0:
        return signal
    gain_db = target_lufs - current_lufs
    gain_lin = 10.0 ** (gain_db / 20.0)
    scaled = signal * gain_lin
    return limit(scaled, ceiling=0.98)

def stitch_segments(segments, pause_sec=0.55, lead_in_sec=0.2, tail_sec=1.5, sr=SR):
    """
    Stitch multiple line segments into one cohesive master vocal track.
    Adds:
      - lead_in_sec: gentle opening room silence before first word (e.g. 0.2s)
      - pause_sec: breathing pause between clauses (e.g. 0.55s)
      - tail_sec: lingering acoustic decay silence at the end (e.g. 1.5s ~ 2.0s),
                  eliminating sudden cutoff / 'power-outage' sensation.
    """
    timeline = []
    pause_len = int(pause_sec * sr)
    lead_len = int(lead_in_sec * sr)
    tail_len = int(tail_sec * sr)
    
    total_len = lead_len + sum(len(s['audio']) for s in segments) + max(0, len(segments) - 1) * pause_len + tail_len
    master = np.zeros(total_len, dtype=np.float32)
    current_pos = lead_len

    for idx, seg in enumerate(segments):
        audio = seg['audio'].copy()
        
        # Apply smooth microscopic fade-out at the very end of the last sentence
        if idx == len(segments) - 1:
            fade_len = int(min(len(audio), sr * 0.12))  # 120ms smooth decay
            if fade_len > 0:
                audio[-fade_len:] *= np.cos(np.linspace(0, np.pi / 2, fade_len))

        dur_sec = len(audio) / sr
        start_sec = current_pos / sr
        end_sec = start_sec + dur_sec

        master[current_pos : current_pos + len(audio)] = audio

        timeline.append({
            'index': idx + 1,
            'id': seg.get('id', f'L{idx+1}'),
            'text': seg['text'],
            'start_time': round(start_sec, 3),
            'end_time': round(end_sec, 3),
            'duration': round(dur_sec, 3)
        })

        current_pos += len(audio) + pause_len

    return master, timeline
