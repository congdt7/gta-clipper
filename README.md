# gta-clipper

Plugin Claude Code tự tìm các live stream GTA 6 đang thịnh hành trên YouTube, ghi lại và cắt clip highlight (đấu súng, cháy nổ, đâm xe) bằng ffmpeg. Có tuỳ chọn xuất clip dọc 9:16 cho Shorts/TikTok/Reels.

## Cài đặt

Trong Claude Code:

```
/plugin marketplace add congdt7/gta-clipper
/plugin install gta-clipper@gta-clipper
```

Repo này là private: bạn cần được mời vào repo và đã đăng nhập GitHub trên máy (SSH key hoặc `gh auth login`).

Cần có: `python3`, `ffmpeg`, `yt-dlp` và `deno` hoặc `node`.

```bash
brew install ffmpeg deno
python3 -m pip install --user "yt-dlp[default]" certifi
```

## Dùng

```
/gta-clipper:cut-gta-clips                      # tìm live hot, ghi, cắt clip
/gta-clipper:cut-gta-clips ~/Videos/gta.mp4 5 30   # cắt 5 clip x 30s từ video có sẵn
```

Hoặc chạy script trực tiếp:

```bash
python3 scripts/find_trending.py --top 5 --list-only
python3 scripts/find_trending.py --top 3 --minutes 20 --out gta_streams
python3 scripts/cut_highlights.py gta_streams/<file>.mp4 --clips 5 --length 30 --vertical
```

## Lưu ý bản quyền

Đăng lại clip từ stream của người khác có thể bị gậy bản quyền. Hãy xin phép streamer và ghi nguồn (tên kênh + link).
