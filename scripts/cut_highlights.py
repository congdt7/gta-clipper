#!/usr/bin/env python3
"""Find and cut highlight clips from a gameplay video using loudness + scene-change scores."""
import argparse, json, math, re, subprocess, sys
from datetime import datetime
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


def layout_filter(layout, cam, src="[0:v]", face=None):
    """ffmpeg filter_complex for a layout, output label [v]. `cam` = (x, y, w, h) as 0..1 fractions.
    `src` is the gameplay stream label; `face` (a stream label) replaces the facecam crop in the top band."""
    if layout == "wide":
        return f"{src}null[v]"
    if layout == "center":
        return f"{src}crop=ih*9/16:ih,scale=1080:1920,setsar=1[v]"
    has_face = bool(face or cam)
    # top-band source: the overlay stream, or a crop of the facecam box from the gameplay
    branches = ["[a]", "[b]"] + (["[c]"] if has_face and not face else [])
    head = f"{src}split={len(branches)}{''.join(branches)};"
    def top(size):
        s = face if face else f"[c]crop=iw*{cam[2]}:ih*{cam[3]}:iw*{cam[0]}:ih*{cam[1]},"
        return f"{s}scale={size}:force_original_aspect_ratio=decrease[cam];"
    if layout == "stack":  # facecam top 1080x600 on blurred fill, gameplay bottom 1080x1320
        return (head + "[a]crop=ih*1080/1320:ih,scale=1080:1320[g];" + top("1080:600") +
                "[b]scale=1080:600:force_original_aspect_ratio=increase,crop=1080:600,boxblur=20[bg];"
                "[bg][cam]overlay=(W-w)/2:(H-h)/2[top];[top][g]vstack,setsar=1[v]")
    # full: whole 16:9 gameplay across the middle of a blurred fill, facecam (if any) in the top band
    base = ("[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=25[bg];"
            "[b]scale=1080:-2[g];[bg][g]overlay=0:(H-h)/2")
    if not has_face:
        return f"{head}{base},setsar=1[v]"
    return (f"{head}{base}[mid];" + top("1000:600") +
            "[mid][cam]overlay=(W-w)/2:(656-h)/2,setsar=1[v]")


def overlay_filter(layout, cam, size):
    """Black out the facecam box in input 0 and put input 1 (cartoon) there; feed the cartoon to the top band too."""
    W, H = size
    bx, by, bw, bh = (round(W * cam[0]), round(H * cam[1]), round(W * cam[2]), round(H * cam[3]))
    need_top = layout in ("stack", "full")
    ov = "[1:v]split=2[o1][o2];" if need_top else "[1:v]null[o1];"
    return (f"{ov}[0:v]drawbox=x={bx}:y={by}:w={bw}:h={bh}:color=black:t=fill[d];"
            f"[o1]scale={bw}:{bh}:force_original_aspect_ratio=decrease[os];"
            f"[d][os]overlay={bx}+({bw}-w)/2:{by}+({bh}-h)/2[src];"
            + layout_filter(layout, cam, "[src]", "[o2]" if need_top else None))


def video_size(video):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
               "-of", "json", video]).stdout
    s = json.loads(out)["streams"][0]
    return s["width"], s["height"]


def parse_cam(s):
    cam = tuple(float(v) for v in s.split(","))
    if len(cam) != 4 or not all(0 <= v <= 1 for v in cam) or cam[2] <= 0 or cam[3] <= 0 \
            or cam[0] + cam[2] > 1 or cam[1] + cam[3] > 1:
        raise argparse.ArgumentTypeError("--facecam cần 4 số x,y,w,h trong khoảng 0..1, nằm trong khung hình")
    return cam


def hhmmss(t):
    return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d}"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("video", nargs="?")
    ap.add_argument("--clips", type=int, default=5)
    ap.add_argument("--length", type=int, default=30, help="seconds per clip")
    ap.add_argument("--layout", choices=["wide", "center", "stack", "full"], default="wide",
                    help="wide: keep original; center: 9:16 center crop; stack: facecam top + gameplay "
                         "bottom; full: whole gameplay shrunk into 9:16 (+ facecam on top if given)")
    ap.add_argument("--vertical", action="store_true", help="same as --layout center")
    ap.add_argument("--facecam", type=parse_cam, help="facecam box as fractions x,y,w,h, e.g. 0,0.14,0.24,0.32")
    ap.add_argument("--cam-overlay", help="PNG/GIF/video (alpha ok) that replaces the facecam everywhere; needs --facecam")
    ap.add_argument("--preview", action="store_true",
                    help="write one frame with a 10%% grid to <video>_preview.jpg (to locate the facecam) and exit")
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
        assert parse_cam("0,0.1,0.25,0.3") == (0, 0.1, 0.25, 0.3)
        for bad in ("0,0,1", "0.9,0,0.2,0.1", "0,0,0,0.5"):
            try:
                parse_cam(bad)
                raise AssertionError(bad)
            except argparse.ArgumentTypeError:
                pass
        print("selftest ok")
        return
    if a.vertical and a.layout == "wide":
        a.layout = "center"
    if a.layout == "stack" and not a.facecam:
        ap.error("--layout stack cần --facecam (dùng --preview để tìm vị trí facecam)")
    if a.cam_overlay:
        if not a.facecam:
            ap.error("--cam-overlay cần --facecam để biết che chỗ nào")
        a.cam_overlay = str(Path(a.cam_overlay).expanduser().resolve())
        if not Path(a.cam_overlay).is_file():
            sys.exit(f"Không tìm thấy file overlay: {a.cam_overlay}")
    if not a.video or a.clips < 1 or a.length < 1:
        ap.error("need a video path, --clips >= 1 and --length >= 1")

    video = str(Path(a.video).expanduser().resolve())
    if not Path(video).is_file():
        sys.exit(f"Không tìm thấy file: {video}")
    if a.preview:
        prev = Path(video).with_name(Path(video).stem + "_preview.jpg")
        run(["ffmpeg", "-y", "-v", "error", "-ss", str(duration(video) / 2), "-i", video, "-frames:v", "1",
             "-vf", "scale=1280:-2,drawgrid=w=iw/10:h=ih/10:t=1:c=red@0.6", str(prev)])
        print(prev)
        return
    base = Path(a.out).expanduser() if a.out else Path(video).with_name(Path(video).stem + "_clips")
    created = datetime.now()
    # one folder per run so re-cutting never overwrites or mixes with earlier clips
    out = base / f"{created:%Y-%m-%d_%H%M%S}_{a.layout}"
    k = 2
    while out.exists():
        out = base / f"{created:%Y-%m-%d_%H%M%S}_{a.layout}_{k}"
        k += 1
    out.mkdir(parents=True)

    dur = duration(video)
    n = max(1, math.ceil(dur))
    print(f"Đang phân tích {hhmmss(dur)} video...", file=sys.stderr)
    au, sc = audio_scores(video, n), scene_scores(video, n)
    w = min(max(a.audio_weight, 0.0), 1.0)
    scores = [w * x + (1 - w) * y for x, y in zip(au, sc)]

    length = min(a.length, n)
    ov_in = []
    if a.cam_overlay:
        static = Path(a.cam_overlay).suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp")
        ov_in = (["-loop", "1"] if static else ["-stream_loop", "-1"]) + ["-i", a.cam_overlay]
        fc = overlay_filter(a.layout, a.facecam, video_size(video))
    else:
        fc = None if a.layout == "wide" else layout_filter(a.layout, a.facecam)
    vf = ["-filter_complex", fc, "-map", "[v]", "-map", "0:a?"] if fc else []
    results = []
    for i, (start, total) in enumerate(pick_windows(scores, length, a.clips), 1):
        clip = out / f"clip_{i:02d}_{hhmmss(start).replace(':', '-')}.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-ss", str(start), "-i", video, *ov_in, "-t", str(length), *vf,
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", str(clip)])
        # thumbnail from the finished clip so it shows the chosen layout
        run(["ffmpeg", "-y", "-v", "error", "-ss", str(length / 2), "-i", str(clip),
             "-frames:v", "1", "-vf", "scale='min(640,iw)':-2", str(clip.with_suffix(".jpg"))])
        results.append({"file": clip.name, "thumbnail": clip.with_suffix(".jpg").name,
                        "start": hhmmss(start), "end": hhmmss(min(start + length, dur)),
                        "score": round(total / length, 3)})
    sidecar = Path(video).with_suffix(".json")  # written by find_trending.py
    try:
        source = json.loads(sidecar.read_text()) if sidecar.is_file() else None
    except (OSError, json.JSONDecodeError):
        source = None
    manifest = {"created_at": created.isoformat(timespec="seconds"), "video": video, "source": source,
                "layout": a.layout, "facecam": a.facecam, "cam_overlay": a.cam_overlay,
                "clip_length": length, "clips": results}
    (out / "clips.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps({"folder": str(out), **manifest}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
