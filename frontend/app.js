let currentVideoData = null;

document.addEventListener("DOMContentLoaded", () => {
  renderHistory();

  const urlInput = document.getElementById("urlInput");
  const clearBtn = document.getElementById("clearBtn");

  urlInput.addEventListener("input", () => {
    if (urlInput.value.trim().length > 0) {
      clearBtn.classList.remove("hidden");
    } else {
      clearBtn.classList.add("hidden");
    }
  });
});

function clearInput() {
  const urlInput = document.getElementById("urlInput");
  urlInput.value = "";
  document.getElementById("clearBtn").classList.add("hidden");
  urlInput.focus();
}

async function pasteClipboard() {
  const urlInput = document.getElementById("urlInput");
  try {
    if (navigator.clipboard && navigator.clipboard.readText) {
      const text = await navigator.clipboard.readText();
      if (text && text.trim()) {
        urlInput.value = text.trim();
        document.getElementById("clearBtn").classList.remove("hidden");
        if (text.includes("tiktok.com")) {
          handleParseUrl();
        }
        return;
      }
    }
  } catch (err) {
    console.warn("Clipboard access denied or not supported:", err);
  }
  urlInput.focus();
}

function setInputUrl(url) {
  const urlInput = document.getElementById("urlInput");
  urlInput.value = url;
  document.getElementById("clearBtn").classList.remove("hidden");
  handleParseUrl();
}

function hideError() {
  document.getElementById("errorAlert").classList.add("hidden");
}

function showError(message) {
  const errorAlert = document.getElementById("errorAlert");
  const errorMessage = document.getElementById("errorMessage");
  errorMessage.textContent = message || "Đã xảy ra lỗi khi bóc tách video.";
  errorAlert.classList.remove("hidden");
  errorAlert.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function handleParseUrl() {
  const urlInput = document.getElementById("urlInput");
  const rawUrl = urlInput.value.trim();

  if (!rawUrl) {
    showError("Vui lòng dán liên kết TikTok trước khi tải.");
    return;
  }

  const cleanTestUrl = rawUrl.split("?")[0].replace(/\/+$/, "");
  if (/@[\w\.-]+\/(?:video|photo|phot|v)$/i.test(cleanTestUrl)) {
    showError("Đường dẫn bị thiếu mã số ID bài viết ở cuối (ví dụ thiếu dãy số như /photo/7412345678...). Bạn hãy nhấp hẳn vào mở bài viết trên TikTok rồi bấm Chia sẻ > Sao chép liên kết nhé!");
    return;
  }

  if (/@[\w\.-]+$/i.test(cleanTestUrl)) {
    showError("Đây là đường dẫn Trang cá nhân (Profile), không phải video. Bạn hãy nhấp vào một video cụ thể để sao chép liên kết nhé!");
    return;
  }

  hideError();
  document.getElementById("resultSection").classList.add("hidden");

  // Show loading
  const loadingSection = document.getElementById("loadingSection");
  const loadingStatusText = document.getElementById("loadingStatusText");
  const submitBtn = document.getElementById("submitBtn");
  const submitBtnText = document.getElementById("submitBtnText");

  loadingSection.classList.remove("hidden");
  loadingStatusText.textContent = "Đang kết nối đến máy chủ TikTok...";
  submitBtn.disabled = true;
  submitBtnText.textContent = "Đang xử lý...";

  const statusTimer = setTimeout(() => {
    loadingStatusText.textContent = "Đang tìm luồng Full HD gốc không dính logo...";
  }, 1200);

  try {
    const res = await fetch("/api/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: rawUrl }),
    });

    const data = await res.json();
    clearTimeout(statusTimer);

    if (!res.ok || !data.success) {
      throw new Error(data.detail || "Không thể phân tích video này.");
    }

    currentVideoData = data.data;
    displayResult(currentVideoData);
    saveToHistory(currentVideoData, rawUrl);
    renderHistory();
  } catch (err) {
    clearTimeout(statusTimer);
    console.error(err);
    showError(err.message || "Không thể kết nối đến máy chủ.");
  } finally {
    loadingSection.classList.add("hidden");
    submitBtn.disabled = false;
    submitBtnText.textContent = "Tải Ngay";
  }
}

function displayResult(item) {
  const resultSection = document.getElementById("resultSection");

  // Video & Slide preview
  const videoContainer = document.getElementById("videoContainer");
  const videoPlayer = document.getElementById("videoPlayer");
  const slideImagesContainer = document.getElementById("slideImagesContainer");
  const slideImagesGrid = document.getElementById("slideImagesGrid");
  const playerBadge = document.getElementById("playerBadge");

  if (item.is_slideshow && item.images && item.images.length > 0) {
    videoContainer.classList.add("hidden");
    slideImagesContainer.classList.remove("hidden");
    document.getElementById("photoCount").textContent = item.images.length;

    slideImagesGrid.innerHTML = item.images
      .map(
        (img, idx) => `
        <div class="relative group rounded-lg overflow-hidden border border-white/10 aspect-[3/4] bg-black/50">
          <img src="${img.url}" alt="Slide ${idx + 1}" class="w-full h-full object-cover">
          <a href="${img.download_url}" download class="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center text-xs font-semibold text-white transition-opacity">
            <span>Tải ảnh ${idx + 1}</span>
          </a>
        </div>
      `
      )
      .join("");
  } else {
    slideImagesContainer.classList.add("hidden");
    videoContainer.classList.remove("hidden");
    videoPlayer.src = item.preview_video || "";
    videoPlayer.poster = item.cover || "";
    playerBadge.textContent = "Chất lượng gốc HD";
  }

  // Author details
  document.getElementById("authorAvatar").src = item.author.avatar || "https://www.tiktok.com/favicon.ico";
  document.getElementById("authorName").textContent = item.author.name || "TikTok User";
  document.getElementById("authorUsername").textContent = `@${item.author.username || "tiktok_user"}`;

  // Video caption
  document.getElementById("videoTitle").textContent = item.title || "Không có tiêu đề";

  // Stats
  document.getElementById("statLikes").textContent = item.stats.likes || "0";
  document.getElementById("statComments").textContent = item.stats.comments || "0";
  document.getElementById("statShares").textContent = item.stats.shares || "0";
  document.getElementById("statViews").textContent = item.stats.views || "0";

  // Download buttons
  const buttonsList = document.getElementById("downloadButtonsList");
  buttonsList.innerHTML = "";

  if (item.downloads && item.downloads.length > 0) {
    item.downloads.forEach((dl) => {
      const btn = document.createElement("a");
      btn.href = dl.download_url;
      btn.setAttribute("download", "");
      btn.className = dl.is_best
        ? "btn-best-quality w-full p-3.5 rounded-xl flex items-center justify-between font-semibold group cursor-pointer block text-left"
        : "glass-card w-full p-3 rounded-xl flex items-center justify-between font-medium group cursor-pointer block text-left hover:border-white/20";

      btn.innerHTML = `
        <div class="flex items-center space-x-3">
          <div class="w-8 h-8 rounded-lg ${dl.is_best ? "bg-white/20" : "bg-white/5"} flex items-center justify-center flex-shrink-0">
            ${
              dl.type === "audio"
                ? `<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"></path></svg>`
                : `<svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>`
            }
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <span class="text-sm font-bold text-white">${dl.label}</span>
              ${
                dl.badge
                  ? `<span class="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${dl.is_best ? "bg-white text-black font-extrabold" : "bg-white/10 text-slate-300 font-semibold"}">${dl.badge}</span>`
                  : ""
              }
            </div>
            <p class="text-xs ${dl.is_best ? "text-white/80" : "text-slate-400"} mt-0.5">${dl.sublabel || ""}</p>
          </div>
        </div>
        <div class="text-right flex items-center space-x-2">
          ${dl.size ? `<span class="text-xs ${dl.is_best ? "text-white/90 font-bold" : "text-slate-400"}">${dl.size}</span>` : ""}
          <svg class="w-4 h-4 text-white transform group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
          </svg>
        </div>
      `;
      buttonsList.appendChild(btn);
    });
  }

  // Cover image download button
  if (item.origin_cover || item.cover) {
    const coverUrl = item.origin_cover || item.cover;
    const coverBtn = document.createElement("a");
    coverBtn.href = `/api/download?url=${encodeURIComponent(coverUrl)}&filename=${encodeURIComponent((item.title || "tiktok").slice(0, 30) + "_cover.jpg")}`;
    coverBtn.setAttribute("download", "");
    coverBtn.className = "glass-card w-full p-3 rounded-xl flex items-center justify-between font-medium group cursor-pointer block text-left hover:border-white/20";
    coverBtn.innerHTML = `
      <div class="flex items-center space-x-3">
        <div class="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center flex-shrink-0">
          <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
          </svg>
        </div>
        <div>
          <span class="text-sm font-bold text-white">Tải ảnh bìa HD (Cover)</span>
          <p class="text-xs text-slate-400 mt-0.5">Ảnh đại diện nguyên bản của video</p>
        </div>
      </div>
      <div class="text-right flex items-center space-x-2">
        <svg class="w-4 h-4 text-white transform group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
        </svg>
      </div>
    `;
    buttonsList.appendChild(coverBtn);
  }

  // Slide images bulk download button if slideshow
  if (item.is_slideshow && item.images && item.images.length > 0) {
    const slideNotice = document.createElement("div");
    slideNotice.className = "p-3 rounded-xl bg-[#25f4ee]/10 border border-[#25f4ee]/20 text-xs text-[#25f4ee] flex items-center space-x-2";
    slideNotice.innerHTML = `
      <span>💡</span>
      <span>Bài đăng này là dạng Album ảnh. Bạn có thể nhấn vào từng ảnh ở bên trái hoặc tải từng ảnh độ nét gốc.</span>
    `;
    buttonsList.appendChild(slideNotice);
  }

  resultSection.classList.remove("hidden");
  resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function copyCaption() {
  if (!currentVideoData || !currentVideoData.title) return;
  const copyBtnText = document.getElementById("copyCaptionText");
  try {
    await navigator.clipboard.writeText(currentVideoData.title);
    copyBtnText.textContent = "✓ Đã sao chép!";
    setTimeout(() => {
      copyBtnText.textContent = "Sao chép caption";
    }, 2000);
  } catch (err) {
    console.error("Copy failed", err);
  }
}

// Local Storage History Management
const HISTORY_KEY = "tiktok_hd_downloader_history";

function getHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveToHistory(item, originalUrl) {
  try {
    let history = getHistory();
    // Remove if already exists with same ID
    history = history.filter((h) => h.id !== item.id);

    const historyItem = {
      id: item.id,
      title: item.title,
      author: item.author.name || item.author.username,
      avatar: item.author.avatar,
      cover: item.cover,
      url: originalUrl,
      timestamp: new Date().toLocaleDateString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        day: "2-digit",
        month: "2-digit",
      }),
      cachedData: item,
    };

    history.unshift(historyItem);
    if (history.length > 12) {
      history.pop();
    }
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  } catch (e) {
    console.warn("Could not save to history:", e);
  }
}

function clearHistory() {
  localStorage.removeItem(HISTORY_KEY);
  renderHistory();
}

function renderHistory() {
  const historyList = document.getElementById("historyList");
  const history = getHistory();

  if (history.length === 0) {
    historyList.innerHTML = `
      <div class="col-span-full py-8 text-center text-xs text-slate-500">
        Chưa có video nào trong lịch sử tải.
      </div>
    `;
    return;
  }

  historyList.innerHTML = history
    .map(
      (h, idx) => `
      <div class="glass-card p-3 flex items-center space-x-3 cursor-pointer hover:border-[#fe2c55]/40 transition-all" onclick="loadHistoryItem(${idx})">
        <img src="${h.cover || h.avatar}" alt="Thumb" class="w-12 h-16 rounded-lg object-cover bg-black/40 border border-white/10 flex-shrink-0">
        <div class="flex-1 min-w-0">
          <h5 class="text-xs font-bold text-white truncate">${h.title || "TikTok Video"}</h5>
          <p class="text-[11px] text-slate-400 truncate mt-0.5">Bởi ${h.author}</p>
          <div class="flex items-center space-x-2 mt-2 text-[10px] text-slate-500">
            <span>🕒 ${h.timestamp}</span>
            <span class="text-[#fe2c55] font-semibold">Xem lại →</span>
          </div>
        </div>
      </div>
    `
    )
    .join("");
}

function loadHistoryItem(index) {
  const history = getHistory();
  const item = history[index];
  if (item && item.cachedData) {
    currentVideoData = item.cachedData;
    displayResult(currentVideoData);
    document.getElementById("urlInput").value = item.url;
    document.getElementById("clearBtn").classList.remove("hidden");
  } else if (item && item.url) {
    setInputUrl(item.url);
  }
}
