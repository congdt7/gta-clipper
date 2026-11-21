#!/usr/bin/env python3
"""Find and cut highlight clips from a gameplay video using loudness + scene-change scores."""
import argparse, json, math, re, subprocess, sys
from pathlib import Path


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def duration(video):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", video]).stdout
    return float(json.loads(out)["format"]["duration"])


def per_second(lines, key, n, reduce):
    """Parse ffmpeg metadata=print output into one value per second."""
    buckets = [[] for _ in range(n)]
    t = None
    for line in lines.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = int(float(m.group(1)))
        elif line.startswith(key + "=") and t is not None and t < n:
            v = line.split("=", 1)[1]
            buckets[t].append(-60.0 if v in ("-inf", "nan") else max(-60.0, float(v)))
    return [reduce(b) if b else None for b in buckets]


def normalize(xs):
    vals = [x for x in xs if x is not None]
    if not vals or max(vals) == min(vals):
        return [0.0] * len(xs)
    lo, hi = min(vals), max(vals)
    return [0.0 if x is None else (x - lo) / (hi - lo) for x in xs]


def audio_scores(video, n):
    af = ("aresample=8000,asetnsamples=n=8000,astats=metadata=1:reset=1,"
          "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-")
    p = subprocess.run(["ffmpeg", "-nostats", "-i", video, "-vn", "-af", af, "-f", "null", "-"],
                       capture_output=True, text=True)
    if p.returncode != 0:  # no audio stream
        return [0.0] * n
    return normalize(per_second(p.stdout, "lavfi.astats.Overall.RMS_level", n, max))


def scene_scores(video, n):
    vf = "fps=2,scale=160:-2,select='gte(scene,0)',metadata=print:key=lavfi.scene_score:file=-"
    out = run(["ffmpeg", "-nostats", "-i", video, "-an", "-vf", vf, "-f", "null", "-"]).stdout
    return normalize(per_second(out, "lavfi.scene_score", n, lambda b: sum(b) / len(b)))


def pick_windows(scores, length, count):
    """Greedy: highest-sum windows of `length` seconds that don't overlap. Returns [(start, score)]."""
    n = len(scores)
    if n <= length:
        return [(0, sum(scores))]
    prefix = [0.0]
    for s in scores:
        prefix.append(prefix[-1] + s)
    sums = sorted(((prefix[i + length] - prefix[i], i) for i in range(n - length + 1)), reverse=True)
    picked = []
    for total, start in sums:
        if all(abs(start - p) >= length for p, _ in picked):
            picked.append((start, total))
            if len(picked) == count:
                break
    return sorted(picked)


def hhmmss(t):
    return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("video", nargs="?")
    ap.add_argument("--clips", type=int, default=5)
    ap.add_argument("--length", type=int, default=30, help="seconds per clip")
    ap.add_argument("--vertical", action="store_true", help="center-crop to 9:16 1080x1920 for Shorts/TikTok")
    ap.add_argument("--out", help="output folder (default: <video>_clips next to the video)")
    ap.add_argument("--audio-weight", type=float, default=0.7)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        s = [0] * 100
        s[10:15] = [1] * 5
        s[60:70] = [2] * 10
        w = pick_windows(s, 10, 2)
        assert w == [(10, 5), (60, 20)], w
        assert pick_windows([1, 2], 10, 3) == [(0, 3)]
        print("selftest ok")
        return
    if not a.video or a.clips < 1 or a.length < 1:
        ap.error("need a video path, --clips >= 1 and --length >= 1")

    video = str(Path(a.video).expanduser().resolve())
    if not Path(video).is_file():
        sys.exit(f"Không tìm thấy file: {video}")
    out = Path(a.out).expanduser() if a.out else Path(video).with_name(Path(video).stem + "_clips")
    out.mkdir(parents=True, exist_ok=True)

    dur = duration(video)
    n = max(1, math.ceil(dur))
    print(f"Đang phân tích {hhmmss(dur)} video...", file=sys.stderr)
    au, sc = audio_scores(video, n), scene_scores(video, n)
    w = min(max(a.audio_weight, 0.0), 1.0)
    scores = [w * x + (1 - w) * y for x, y in zip(au, sc)]

    length = min(a.length, n)
    results = []
    for i, (start, total) in enumerate(pick_windows(scores, length, a.clips), 1):
        clip = out / f"clip_{i:02d}_{hhmmss(start).replace(':', '-')}.mp4"
        vf = ["-vf", "crop=ih*9/16:ih,scale=1080:1920"] if a.vertical else []
        run(["ffmpeg", "-y", "-v", "error", "-ss", str(start), "-i", video, "-t", str(length), *vf,
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", str(clip)])
        run(["ffmpeg", "-y", "-v", "error", "-ss", str(start + length / 2), "-i", video,
             "-frames:v", "1", "-vf", "scale=640:-2", str(clip.with_suffix(".jpg"))])
        results.append({"file": str(clip), "thumbnail": str(clip.with_suffix(".jpg")),
                        "start": hhmmss(start), "end": hhmmss(min(start + length, dur)),
                        "score": round(total / length, 3)})
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
