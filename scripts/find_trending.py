#!/usr/bin/env python3
"""Find trending YouTube live streams for a game and record the next N minutes of each."""
import argparse, json, re, shutil, subprocess, sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

# pip --user installs often leave yt-dlp off PATH; fall back to the module
YTDLP = ["yt-dlp"] if shutil.which("yt-dlp") else [sys.executable, "-m", "yt_dlp"]
LIVE_FILTER = "EgJAAQ%253D%253D"  # YouTube search filter: "Live"


def search_live(query, limit):
    """Return live streams for `query`, most concurrent viewers first."""
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp={LIVE_FILTER}"
    p = subprocess.run([*YTDLP, "--flat-playlist", "-I", f"1:{limit}", "-J", url],
                       capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"yt-dlp search failed:\n{p.stderr[-2000:]}")
    entries = json.loads(p.stdout).get("entries") or []
    streams = [{"id": e["id"], "url": f"https://www.youtube.com/watch?v={e['id']}",
                "title": e.get("title"), "channel": e.get("channel") or e.get("uploader"),
                "viewers": e.get("concurrent_view_count") or 0}
               for e in entries if e.get("id")]
    if streams and not any(s["viewers"] for s in streams):
        print("Cảnh báo: YouTube không trả số người xem lần này, giữ thứ tự của YouTube. Thử chạy lại.", file=sys.stderr)
    return sorted(streams, key=lambda s: s["viewers"], reverse=True)


def record(stream, minutes, out_dir):
    """Record `minutes` of a live stream from now via its HLS URL."""
    # YouTube needs a JS runtime; yt-dlp only auto-uses deno, so opt into node when that's what exists
    js = ["--js-runtimes", "node"] if shutil.which("node") and not shutil.which("deno") else []
    hls = subprocess.run([*YTDLP, *js, "-g", "-f", "bv*[height<=1080]+ba/b[height<=1080]/b", stream["url"]],
                         capture_output=True, text=True)
    urls = hls.stdout.split()
    if hls.returncode != 0 or not urls:
        print(f"Bỏ qua {stream['url']}: không lấy được luồng ({hls.stderr.strip()[-300:]})", file=sys.stderr)
        return None
    started = datetime.now()
    safe = re.sub(r"[^\w\-]+", "_", stream["channel"] or "unknown")[:60]
    out = out_dir / f"{safe}_{started:%Y-%m-%d_%H%M%S}_{stream['id']}.mp4"
    print(f"Đang ghi {minutes} phút: {stream['title']} ({stream['viewers']} người xem)", file=sys.stderr)
    inputs = [arg for u in urls[:2] for arg in ("-i", u)]
    maps = ["-map", "0:v:0", "-map", "1:a:0"] if len(urls) > 1 else []  # separate video + audio streams
    p = subprocess.run(["ffmpeg", "-n", "-v", "error", *inputs, *maps,  # -n: never overwrite a recording
                        "-t", str(minutes * 60), "-c", "copy", str(out)])
    if p.returncode != 0 or not out.exists():
        return None
    # sidecar read by cut_highlights.py so clips.json can credit the source
    meta = {k: stream[k] for k in ("url", "title", "channel", "viewers")}
    meta |= {"recorded_at": started.isoformat(timespec="seconds"), "minutes": minutes}
    out.with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return str(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--query", default="GTA 6")
    ap.add_argument("--top", type=int, default=3, help="how many streams to record")
    ap.add_argument("--minutes", type=float, default=20, help="minutes to record per stream")
    ap.add_argument("--min-viewers", type=int, default=0)
    ap.add_argument("--out", default="gta_streams")
    ap.add_argument("--list-only", action="store_true", help="just print trending streams")
    a = ap.parse_args()

    streams = [s for s in search_live(a.query, 30) if s["viewers"] >= a.min_viewers][:a.top]
    if not streams:
        sys.exit(f"Không thấy live nào cho '{a.query}'.")
    if a.list_only:
        print(json.dumps(streams, ensure_ascii=False, indent=2))
        return
    out_dir = Path(a.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    for s in streams:
        s["recording"] = record(s, a.minutes, out_dir)
    print(json.dumps(streams, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
