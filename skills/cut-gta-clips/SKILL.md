---
name: cut-gta-clips
description: Tự tìm các live stream GTA 6 thịnh hành trên YouTube, ghi lại và cắt clip highlight; hoặc cắt highlight từ một file video có sẵn. Dùng khi người dùng muốn cắt clip, tìm highlight, làm Shorts/TikTok từ live stream hay video gameplay.
argument-hint: "[video có sẵn | từ khoá] [số clip] [độ dài giây]"
---

# Cắt clip highlight GTA 6

Highlight trong GTA thường là lúc âm thanh to nhất: đấu súng, cháy nổ, đâm xe, cảnh sát truy đuổi.
`cut_highlights.py` chấm điểm từng giây theo độ lớn âm thanh và mức chuyển cảnh, rồi cắt các đoạn điểm cao nhất, không chồng nhau.

Cần `ffmpeg`, `yt-dlp`, `python3` và một JS runtime (`deno` hoặc `node`) trong PATH; YouTube không trả luồng nếu thiếu JS runtime. Trên macOS: `brew install ffmpeg yt-dlp deno`. Nếu yt-dlp báo `CERTIFICATE_VERIFY_FAILED`, chạy `pip install certifi` cho Python đang chạy yt-dlp.

## A. Tự tìm live thịnh hành (mặc định khi `$ARGUMENTS` không phải file video)

1. Xem các live đang phát, xếp theo số người đang xem:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_trending.py" --query "GTA 6" --top 5 --list-only
   ```
   Dùng từ khoá trong `$ARGUMENTS` nếu có. Cho người dùng xem danh sách (tiêu đề, kênh, số người xem) và hỏi chọn stream nào, ghi bao nhiêu phút (mặc định 3 stream đầu, 20 phút).
2. Ghi lại (chạy nền, vì mất đúng số phút đã chọn):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/find_trending.py" --query "GTA 6" --top 3 --minutes 20 --out gta_streams
   ```
3. Với mỗi file trong trường `recording`, làm phần B.

## B. Cắt highlight từ một file video

1. Chạy (mặc định 5 clip x 30 giây; thêm `--vertical` cho Shorts/TikTok/Reels 9:16):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cut_highlights.py" "<video>" --clips 5 --length 30
   ```
   Clip được ghi vào `<tên video>_clips/` cạnh video gốc.
2. Xem thumbnail `.jpg` cùng tên từng clip, mô tả ngắn nội dung và đề xuất tiêu đề.
3. Báo lại: danh sách file, mốc thời gian, tiêu đề gợi ý, và kênh gốc của stream.

## Lưu ý bản quyền

Nhắc người dùng một lần: đăng lại clip từ stream của người khác có thể bị gậy bản quyền. Nên xin phép streamer và ghi nguồn (tên kênh + link) trong mô tả.
