"""Voice Narrator Generator CLI
Produces broadcast-grade voiceover audio from text with exact timestamp tracking.

Usage Examples:
    python generate.py "太行、王屋二山，方七百里，高万仞。"
    python generate.py --file script.txt --voice zh-CN-YunjianNeural --rate -4% --tail 2.0
    python generate.py "第一句话。第二句话！第三句话？" --out output/custom.wav
"""
import os, sys, argparse, json, time, asyncio

# Ensure safe output encoding on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import soundfile as sf
from tts_engine import split_text_into_clauses, synthesize_sentence_async, DEFAULT_VOICE
from audio_processor import SR, stitch_segments, normalize_loudness, measure_lufs

async def process_text_to_audio_async(
    text,
    voice=DEFAULT_VOICE,
    rate="+0%",
    pitch="+0Hz",
    pause_sec=0.55,
    lead_in_sec=0.25,
    tail_sec=1.8,
    target_lufs=-14.0,
    out_wav="output/master_voice.wav",
    out_json="output/timeline.json",
    concurrency=6
):
    start_time = time.time()
    clauses = split_text_into_clauses(text)
    
    print("\n" + "=" * 62, flush=True)
    print(">> Voice Narrator - High Performance Studio Synthesis", flush=True)
    print("=" * 62, flush=True)
    print(f" Voice Model : {voice}", flush=True)
    print(f" Rate / Pitch: {rate} / {pitch}", flush=True)
    print(f" Lead-In Gap : {lead_in_sec}s opening cushion", flush=True)
    print(f" Pause Gap   : {pause_sec}s between clauses", flush=True)
    print(f" Tail Buffer : {tail_sec}s lingering acoustic silence at end", flush=True)
    print(f" Segments    : {len(clauses)} clauses detected (concurrency: {concurrency})", flush=True)
    print("-" * 62, flush=True)

    sem = asyncio.Semaphore(concurrency)

    async def fetch_one(idx, clause):
        async with sem:
            audio = await synthesize_sentence_async(clause, voice=voice, rate=rate, pitch=pitch)
            dur = len(audio) / SR
            print(f" [{idx+1:02d}/{len(clauses):02d}] Synthesized ({dur:4.2f}s): {clause}", flush=True)
            return {
                'id': f'L{idx+1}',
                'text': clause,
                'audio': audio,
                'duration': dur
            }

    tasks = [fetch_one(i, c) for i, c in enumerate(clauses)]
    segments_data = await asyncio.gather(*tasks)

    print("-" * 62, flush=True)
    print(">> Stitching segments and applying studio mastering...", flush=True)

    # Stitch segments into continuous track with lead-in and lingering tail padding
    master_raw, timeline = stitch_segments(
        segments_data,
        pause_sec=pause_sec,
        lead_in_sec=lead_in_sec,
        tail_sec=tail_sec,
        sr=SR
    )
    
    # Apply Broadcast Mastering to Target LUFS
    master_final = normalize_loudness(master_raw, sr=SR, target_lufs=target_lufs)
    measured_lufs = measure_lufs(master_final, sr=SR)
    total_dur = len(master_final) / SR

    # Ensure output directories exist
    os.makedirs(os.path.dirname(os.path.abspath(out_wav)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(out_json)), exist_ok=True)

    # Save Master Audio
    sf.write(out_wav, master_final, SR)

    # Save Timeline Manifest
    manifest = {
        'meta': {
            'voice': voice,
            'rate': rate,
            'sample_rate': SR,
            'lead_in_sec': lead_in_sec,
            'pause_sec': pause_sec,
            'tail_sec': tail_sec,
            'total_duration_sec': round(total_dur, 3),
            'target_lufs': target_lufs,
            'measured_lufs': round(float(measured_lufs), 2),
            'segments_count': len(timeline),
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S')
        },
        'timeline': timeline
    }
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time
    print("-" * 62, flush=True)
    print(f"[*] Master Audio Output : {out_wav}", flush=True)
    print(f"[*] Timeline Manifest   : {out_json}", flush=True)
    print(f"[*] Total Audio Duration: {total_dur:.3f} s (including {tail_sec}s tail)", flush=True)
    print(f"[*] Measured Loudness   : {measured_lufs:.2f} LUFS", flush=True)
    print("=" * 62 + "\n", flush=True)

    # Print timeline summary table
    print(f"Timeline Summary ({len(timeline)} segments):", flush=True)
    for item in timeline[:8]:
        print(f"  [{item['start_time']:6.2f}s -> {item['end_time']:6.2f}s] ({item['duration']:4.2f}s): {item['text']}", flush=True)
    if len(timeline) > 16:
        print(f"  ... [skipped {len(timeline)-16} middle segments] ...", flush=True)
        for item in timeline[-8:]:
            print(f"  [{item['start_time']:6.2f}s -> {item['end_time']:6.2f}s] ({item['duration']:4.2f}s): {item['text']}", flush=True)
    elif len(timeline) > 8:
        for item in timeline[8:]:
            print(f"  [{item['start_time']:6.2f}s -> {item['end_time']:6.2f}s] ({item['duration']:4.2f}s): {item['text']}", flush=True)
    print(f"  [{timeline[-1]['end_time']:6.2f}s -> {total_dur:6.2f}s] ({tail_sec:4.2f}s): [Ending Lingering Silence / 余音留白]", flush=True)
    print("", flush=True)

    return out_wav, out_json

def process_text_to_audio(*args, **kwargs):
    return asyncio.run(process_text_to_audio_async(*args, **kwargs))

def main():
    parser = argparse.ArgumentParser(description="Standalone Broadcast Voice Narrator")
    parser.add_argument("text", nargs="?", help="Text string to speak")
    parser.add_argument("--file", "-f", help="Input text file path")
    parser.add_argument("--voice", "-v", default=DEFAULT_VOICE, help=f"Voice model (default: {DEFAULT_VOICE})")
    parser.add_argument("--rate", "-r", default="+0%", help="Speed rate adjustment (e.g. -4%, +10%)")
    parser.add_argument("--pitch", "-p", default="+0Hz", help="Pitch adjustment (e.g. -2Hz, +5Hz)")
    parser.add_argument("--pause", type=float, default=0.55, help="Pause between sentences in seconds (default: 0.55)")
    parser.add_argument("--lead", "-l", type=float, default=0.25, help="Opening lead-in silence in seconds (default: 0.25)")
    parser.add_argument("--tail", "-t", type=float, default=1.8, help="Ending tail silence in seconds (default: 1.8)")
    parser.add_argument("--lufs", type=float, default=-14.0, help="Target broadcast LUFS (default: -14.0)")
    parser.add_argument("--concurrency", "-c", type=int, default=6, help="Max concurrent TTS downloads (default: 6)")
    parser.add_argument("--out", "-o", default="output/master_voice.wav", help="Output WAV file path")
    parser.add_argument("--json", "-j", default="output/timeline.json", help="Output JSON timeline path")

    args = parser.parse_args()

    content = None
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: file not found '{args.file}'", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
    elif args.text:
        content = args.text
    else:
        print("Please provide text as argument or via --file. Example:")
        print("  python generate.py \"天行健，君子以自强不息。地势坤，君子以厚德载物。\"")
        sys.exit(1)

    process_text_to_audio(
        text=content,
        voice=args.voice,
        rate=args.rate,
        pitch=args.pitch,
        pause_sec=args.pause,
        lead_in_sec=args.lead,
        tail_sec=args.tail,
        target_lufs=args.lufs,
        out_wav=args.out,
        out_json=args.json,
        concurrency=args.concurrency
    )

if __name__ == "__main__":
    main()
