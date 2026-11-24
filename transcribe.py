"""Transcribe one audio track of a recording with faster-whisper (CPU).

Usage:
  .venv\\Scripts\\python.exe transcribe.py <recording> <audio_track_index> <out.json> [model]

Writes JSON: {"segments": [{"start": s, "end": s, "text": "..."}], "language": "..."}
The audio is decoded by ffmpeg into a 16 kHz mono WAV in the same folder as out.json
(small: about 115 MB per hour), then removed.
"""
import json
import subprocess
import sys
from pathlib import Path

FFMPEG = (r"C:\Users\jeffr\AppData\Local\Microsoft\WinGet\Packages"
          r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.1-full_build\bin\ffmpeg.exe")


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    src, track, out = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
    model_name = sys.argv[4] if len(sys.argv) > 4 else "small"
    out.parent.mkdir(parents=True, exist_ok=True)
    wav = out.with_suffix(".wav")
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", src, "-vn", "-map", f"0:a:{track}",
                    "-ac", "1", "-ar", "16000", str(wav)], check=True)
    # Load the WAV ourselves: faster-whisper's own loader (PyAV) is incompatible
    # with the installed PyAV version, and ffmpeg already did the decoding.
    import wave
    import numpy as np
    with wave.open(str(wav), "rb") as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio, vad_filter=True, beam_size=1)
    result = {"language": info.language, "segments": [
        {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
        for s in segments]}
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    wav.unlink(missing_ok=True)
    print(f"{len(result['segments'])} segments, language={info.language} -> {out}")


if __name__ == "__main__":
    main()
