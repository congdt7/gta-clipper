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
3. Với mỗi file trong trường `recording`, làm phần B. Bản ghi tên `<kênh>_<ngày>_<giờ>_<id>.mp4`, kèm `<cùng tên>.json` chứa link, tiêu đề, kênh của stream.
   Nếu yt-dlp báo `Sign in to confirm you're not a bot`, YouTube đang tạm chặn máy này. Báo người dùng hai cách: đợi một lúc (hoặc đổi mạng) rồi thử lại, hoặc đăng nhập bằng tài khoản YouTube của chính họ qua cookie trình duyệt bằng cờ `--cookies-from-browser chrome` (hoặc `safari`, `firefox`; nên dùng tài khoản phụ vì YouTube có thể gắn cờ tài khoản tải nhiều). Chỉ thêm cờ này khi người dùng đồng ý trong lượt chat này; không tự lấy cookie.

## B. Cắt highlight từ một file video

1. Chọn bố cục (`--layout`). Mặc định `wide` (giữ nguyên 16:9). Với Shorts/TikTok/Reels (dọc 1080x1920):
   - `stack`: facecam phía trên, gameplay cắt giữa phía dưới. **Mặc định cho clip dọc khi stream có facecam.** Gameplay rõ, mất HUD ở mép.
   - `full`: toàn bộ khung gameplay thu nhỏ ở giữa nền mờ, facecam (nếu có) phía trên. Dùng khi người dùng muốn thấy toàn cảnh; chữ HUD sẽ nhỏ.
   - `center`: cắt dải 9:16 ở giữa. Dùng khi stream không có facecam.
2. Nếu dùng `stack` hoặc `full` với facecam, tìm vị trí facecam:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cut_highlights.py" "<video>" --preview
   ```
   Mở ảnh `_preview.jpg` vừa in ra. Ảnh có lưới đỏ, mỗi ô 10% chiều ngang/dọc. Ước lượng khung facecam (webcam hoặc avatar của streamer, không phải minimap hay HUD) thành 4 số tỉ lệ `x,y,w,h` (góc trên-trái, rộng, cao, đều 0..1), lấy sát mép **bên trong** ô webcam: thà hụt khoảng 0.5% còn hơn lố ra ngoài, vì phần game lọt vào sẽ thành dải màu lạ ở mép facecam. Không thấy facecam: dùng `center` hoặc `full` không có `--facecam`.
3. Chạy (mặc định 5 clip x 30 giây):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cut_highlights.py" "<video>" --clips 5 --length 30 --layout stack --facecam 0,0.14,0.25,0.33
   ```
   Mỗi lần cắt tạo một thư mục mới `<tên video>_clips/<ngày>_<giờ>_<layout>/` (in ra ở trường `folder`), nên không bao giờ đè lần cắt trước. Mở một thumbnail của clip đầu để kiểm tra facecam có được cắt đúng không; sai thì sửa `--facecam` và chạy lại.

   **Thay webcam bằng hoạt hình/icon** (khi người dùng muốn ẩn mặt streamer): thêm `--cam-overlay <file>` (cần `--facecam`). File có thể là PNG, GIF động, hoặc video WebM/MOV có nền trong suốt; GIF và video tự lặp. Ô webcam trong gameplay bị tô đen rồi đặt hoạt hình lên, và phần facecam phía trên (`stack`/`full`) dùng thẳng file hoạt hình. Người dùng không đưa file thì dùng mặt cười mặc định `${CLAUDE_PLUGIN_ROOT}/assets/smiley.gif`. Kiểm tra thumbnail: không được còn thấy mặt streamer ở bất kỳ đâu; nếu lộ mép thì nới `--facecam` ra một chút.
4. Xem thumbnail `.jpg` cùng tên từng clip, mô tả ngắn nội dung và đề xuất tiêu đề.
5. Ghi tiêu đề gợi ý vào `clips.json` của lần cắt đó (thêm trường `title` cho từng clip). Báo lại: thư mục clip, danh sách file, mốc thời gian, tiêu đề gợi ý, và nguồn (`source.channel` + `source.url` trong `clips.json`) để người dùng ghi nguồn khi đăng.

## Lưu ý bản quyền

Nhắc người dùng một lần: đăng lại clip từ stream của người khác có thể bị gậy bản quyền. Nên xin phép streamer và ghi nguồn (tên kênh + link) trong mô tả.
