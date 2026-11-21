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
python3 scripts/cut_highlights.py gta_streams/<file>.mp4 --clips 5 --length 30 --layout stack --facecam 0,0.14,0.25,0.33
```

## Output

```
gta_streams/
├── Kai_Cenat_Live_2026-11-21_105900_dSDUAAr-w_g.mp4      ← bản ghi (kênh_ngày_giờ_id), không bao giờ bị đè
├── Kai_Cenat_Live_2026-11-21_105900_dSDUAAr-w_g.json     ← link, tiêu đề, kênh, giờ ghi
└── Kai_Cenat_Live_2026-11-21_105900_dSDUAAr-w_g_clips/
    └── 2026-11-21_110412_stack/                         ← mỗi lần cắt một thư mục
        ├── clip_01_00-00-21.mp4
        ├── clip_01_00-00-21.jpg
        └── clips.json                                   ← nguồn, kiểu clip, mốc thời gian, điểm, tiêu đề gợi ý
```

## Bố cục clip (`--layout`)

| Kiểu | Mô tả |
|---|---|
| `wide` | Giữ nguyên 16:9 (mặc định) |
| `stack` | Dọc 9:16: facecam phía trên, gameplay phía dưới. Cần `--facecam` |
| `full` | Dọc 9:16: toàn bộ gameplay thu nhỏ trên nền mờ, facecam phía trên nếu có |
| `center` | Dọc 9:16: cắt dải giữa (stream không có facecam). `--vertical` là tên cũ của kiểu này |

`--facecam x,y,w,h` là vị trí ô facecam theo tỉ lệ 0..1 của khung hình. Chạy `--preview` để lấy một khung hình có lưới 10% và đọc vị trí; khi dùng qua Claude Code, Claude tự làm bước này.

## Thay webcam bằng hoạt hình

```bash
python3 scripts/cut_highlights.py <video> --layout stack --facecam 0,0.40,0.20,0.20 --cam-overlay assets/smiley.gif
```

`--cam-overlay` nhận PNG, GIF động hoặc video WebM/MOV có nền trong suốt. Ô webcam trong gameplay bị tô đen và đặt hoạt hình lên; phần facecam phía trên của `stack`/`full` dùng thẳng file hoạt hình nên vẫn nét. `assets/smiley.gif` là hoạt hình mặc định.

## Lưu ý bản quyền

Đăng lại clip từ stream của người khác có thể bị gậy bản quyền. Hãy xin phép streamer và ghi nguồn (tên kênh + link).
