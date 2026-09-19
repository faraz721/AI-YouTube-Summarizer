(() => {
  "use strict";

  // Elements
  const urlInput = document.getElementById("youtube-url");
  const btnFetchInfo = document.getElementById("btn-fetch-info");
  const btnGenerate = document.getElementById("btn-generate");
  const videoInfoEl = document.getElementById("video-info");
  const videoThumb = document.getElementById("video-thumb");
  const videoTitle = document.getElementById("video-title");
  const videoChannel = document.getElementById("video-channel");
  const videoDuration = document.getElementById("video-duration");
  const languageSelect = document.getElementById("language");
  const formMessage = document.getElementById("form-message");
  const loadingEl = document.getElementById("loading");
  const resultsEl = document.getElementById("results");
  const summaryText = document.getElementById("summary-text");
  const keypointsList = document.getElementById("keypoints-list");
  const btnCopySummary = document.getElementById("btn-copy-summary");
  const btnCopyKeypoints = document.getElementById("btn-copy-keypoints");
  const copySummaryMsg = document.getElementById("copy-summary-msg");
  const copyKeypointsMsg = document.getElementById("copy-keypoints-msg");
  const btnDownload = document.getElementById("btn-download");
  const downloadMenu = document.getElementById("download-menu");
  const errorToast = document.getElementById("error-toast");

  // State
  let currentVideoInfo = null;
  let currentSummary = "";
  let currentKeyPoints = [];

  // Helpers
  function showMessage(text, type = "error") {
    formMessage.textContent = text;
    formMessage.className = `form-message ${type}`;
    formMessage.classList.remove("hidden");
  }

  function hideMessage() {
    formMessage.classList.add("hidden");
  }

  function showToast(text) {
    errorToast.textContent = text;
    errorToast.classList.remove("hidden");
    setTimeout(() => errorToast.classList.add("hidden"), 4000);
  }

  function getSelectedSize() {
    const checked = document.querySelector('input[name="size"]:checked');
    return checked ? checked.value : "";
  }

  function setLoading(isLoading) {
    if (isLoading) {
      loadingEl.classList.remove("hidden");
      resultsEl.classList.add("hidden");
      btnGenerate.disabled = true;
    } else {
      loadingEl.classList.add("hidden");
      btnGenerate.disabled = false;
    }
  }

  function renderSummary(text) {
    // Split into paragraphs for better readability
    const paragraphs = text
      .split(/\n+/)
      .map((p) => p.trim())
      .filter(Boolean);
    summaryText.innerHTML = paragraphs
      .map((p) => `<p>${escapeHtml(p)}</p>`)
      .join("");
  }

  function renderKeyPoints(points) {
    keypointsList.innerHTML = "";
    points.forEach((point) => {
      const li = document.createElement("li");
      li.textContent = point;
      keypointsList.appendChild(li);
    });
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function showCopyFeedback(el) {
    el.classList.remove("hidden");
    setTimeout(() => el.classList.add("hidden"), 2000);
  }

  // Fetch video info
  async function fetchVideoInfo() {
    const url = urlInput.value.trim();
    if (!url) {
      showMessage("Please enter a YouTube video URL.");
      return;
    }

    hideMessage();
    btnFetchInfo.disabled = true;
    btnFetchInfo.textContent = "Loading…";

    try {
      const res = await fetch("/api/video-info", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();

      if (!res.ok) {
        showMessage(data.error || "Could not fetch video information.");
        videoInfoEl.classList.add("hidden");
        currentVideoInfo = null;
        return;
      }

      currentVideoInfo = data;
      videoThumb.src = data.thumbnail;
      videoThumb.alt = data.title;
      videoTitle.textContent = data.title;
      videoChannel.textContent = data.channel;
      videoDuration.textContent = data.duration !== "N/A" ? `Duration: ${data.duration}` : "";
      videoInfoEl.classList.remove("hidden");
      hideMessage();
    } catch (err) {
      showMessage("Network error. Please check your connection and try again.");
      videoInfoEl.classList.add("hidden");
      currentVideoInfo = null;
    } finally {
      btnFetchInfo.disabled = false;
      btnFetchInfo.textContent = "Get Info";
    }
  }

  // Generate summary
  async function generateSummary() {
    const url = urlInput.value.trim();
    const size = getSelectedSize();
    const language = languageSelect.value;

    hideMessage();

    if (!url) {
      showMessage("Please enter a YouTube video URL.");
      return;
    }
    if (!size) {
      showMessage("Please select a summary size (Short, Medium, or Detailed).");
      return;
    }
    if (!language) {
      showMessage("Please select a language.");
      return;
    }

    setLoading(true);

    try {
      const res = await fetch("/api/summarize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, size, language }),
      });
      const data = await res.json();

      if (!res.ok) {
        showMessage(data.error || "Failed to generate summary.");
        setLoading(false);
        return;
      }

      currentVideoInfo = data.video_info;
      currentSummary = data.summary;
      currentKeyPoints = data.key_points || [];

      // Update video info display if not already shown
      videoThumb.src = data.video_info.thumbnail;
      videoTitle.textContent = data.video_info.title;
      videoChannel.textContent = data.video_info.channel;
      videoDuration.textContent =
        data.video_info.duration !== "N/A"
          ? `Duration: ${data.video_info.duration}`
          : "";
      videoInfoEl.classList.remove("hidden");

      renderSummary(currentSummary);
      renderKeyPoints(currentKeyPoints);

      setLoading(false);
      resultsEl.classList.remove("hidden");
      resultsEl.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      showMessage("Network error. Please check your connection and try again.");
      setLoading(false);
    }
  }

  // Copy helpers
  async function copyText(text, msgEl) {
    try {
      await navigator.clipboard.writeText(text);
      showCopyFeedback(msgEl);
    } catch {
      // Fallback
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      showCopyFeedback(msgEl);
    }
  }

  // Download
  async function downloadFile(format) {
    if (!currentSummary) {
      showToast("No summary available to download.");
      return;
    }

    downloadMenu.classList.add("hidden");

    try {
      const res = await fetch("/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          format,
          video_info: currentVideoInfo,
          summary: currentSummary,
          key_points: currentKeyPoints,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        showToast(data.error || "Download failed. Please try again.");
        return;
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download =
        format === "txt"
          ? "youtube_summary.txt"
          : format === "pdf"
          ? "youtube_summary.pdf"
          : "youtube_summary.docx";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      showToast("Download failed. Please try again.");
    }
  }

  // Event listeners
  btnFetchInfo.addEventListener("click", fetchVideoInfo);

  urlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      fetchVideoInfo();
    }
  });

  btnGenerate.addEventListener("click", generateSummary);

  btnCopySummary.addEventListener("click", () => {
    copyText(currentSummary, copySummaryMsg);
  });

  btnCopyKeypoints.addEventListener("click", () => {
    const text = currentKeyPoints.map((p, i) => `${i + 1}. ${p}`).join("\n");
    copyText(text, copyKeypointsMsg);
  });

  btnDownload.addEventListener("click", (e) => {
    e.stopPropagation();
    downloadMenu.classList.toggle("hidden");
  });

  downloadMenu.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      downloadFile(btn.dataset.format);
    });
  });

  document.addEventListener("click", (e) => {
    if (!btnDownload.contains(e.target) && !downloadMenu.contains(e.target)) {
      downloadMenu.classList.add("hidden");
    }
  });
})();
