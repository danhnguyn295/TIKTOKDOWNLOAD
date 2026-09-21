# ⚡ TikTok HD Downloader - Tải Video TikTok Chất Lượng Gốc (No Watermark)

Trang web cá nhân chạy trực tiếp trên máy của bạn (Local Server), hỗ trợ trích xuất và tải video TikTok với **đúng chất lượng cao nhất mà tác giả tải lên**, không bị nén, không có logo TikTok nhấp nháy, không bị dính outro.

---

## ✨ Tính năng nổi bật

- 🌟 **Chuẩn chất lượng gốc (Full HD / Original)**: Bóc tách luồng stream gốc cao nhất từ CDN của TikTok (1080p, 60fps tùy file gốc).
- 🚫 **Sạch sẽ 100% không Logo**: Không dính logo watermark TikTok ở 4 góc và không có logo cuối video.
- 🎵 **Tải âm thanh gốc (MP3)**: Trích xuất nhạc nền gốc chất lượng cao chỉ với 1 click.
- 📸 **Hỗ trợ Album ảnh (Slide ảnh TikTok)**: Xem trước và tải từng ảnh chất lượng cao.
- 🖼️ **Tải ảnh bìa HD (Cover Image)**.
- 📋 **Hỗ trợ mọi định dạng link**: Nhận diện link rút gọn (`https://vt.tiktok.com/...`, `https://vm.tiktok.com/...`) và link máy tính (`https://www.tiktok.com/@.../video/...`).
- 🎬 **Trình phát video trực tiếp**: Xem trước video ngay trên web trước khi bấm tải.
- 📋 **Sao chép Caption / Hashtag**: 1-click sao chép nội dung bài đăng.
- 🕒 **Lịch sử tải gần đây**: Tự động lưu lại danh sách video đã tải trong trình duyệt để bạn mở lại bất cứ lúc nào.
- 🔒 **Bảo mật & Tốc độ cao**: Chạy cục bộ trên máy tính của bạn, không quảng cáo, không theo dõi.

---

## 🚀 Hướng dẫn khởi chạy

### Cách 1: Trên Windows (1-Click Nhanh Nhất)
Chỉ cần nhấp đúp vào file:
👉 **`start.bat`** (hoặc `run.bat`)
Chương trình sẽ tự động kích hoạt môi trường, khởi động server và mở trình duyệt tại: **`http://localhost:8000`**

### Cách 2: Trên macOS / Linux
Mở Terminal trong thư mục dự án và chạy:
```bash
./run.sh
```

### Cách 3: Khởi động thủ công bằng Python
```bash
# Trên Windows:
venv\Scripts\activate
python main.py

# Trên macOS/Linux:
source venv/bin/activate
python3 main.py
```

---

## 🛠️ Cấu trúc dự án

```
Project/
├── backend/
│   ├── app.py              # Server FastAPI, định tuyến API & stream proxy tải file
│   ├── tiktok_parser.py    # Engine bóc tách luồng video HD không watermark
│   └── requirements.txt    # Các gói phụ thuộc (FastAPI, Uvicorn, yt-dlp, httpx)
├── frontend/
│   ├── index.html          # Giao diện web người dùng
│   ├── app.js              # Logic tương tác, gọi API, phát video & lưu lịch sử
│   └── styles.css          # Giao diện Dark Neon Glassmorphism
├── run.sh                  # Script khởi động 1-click
└── main.py                 # File thực thi khởi động server và mở trình duyệt
```
