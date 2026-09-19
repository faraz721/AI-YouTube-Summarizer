import os
import re
import io
import json
import urllib.request
import urllib.parse
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.enums import TA_LEFT
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

load_dotenv()

app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPADATA_API_KEY = os.getenv("SUPADATA_API_KEY")  # optional free transcript API for cloud
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Supported languages
SUPPORTED_LANGUAGES = {
    "english": "English",
    "urdu": "Urdu",
    "roman_urdu": "Roman Urdu",
    "german": "German",
    "spanish": "Spanish",
    "french": "French",
    "arabic": "Arabic",
}

SUMMARY_SIZES = {
    "short": "SHORT: Write a concise but useful summary (about 150-250 words). Focus on the core message and main takeaways only.",
    "medium": "MEDIUM: Write a balanced explanation (about 300-500 words). Cover the important ideas and key details clearly.",
    "detailed": "DETAILED: Write a comprehensive explanation (about 600-900 words). Cover the important content, concepts, and supporting points thoroughly so the reader understands the video without watching it.",
}


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    if not url:
        return None
    patterns = [
        r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url.strip())
        if match:
            return match.group(1)
    return None


def get_video_info(video_id: str) -> dict:
    """Fetch basic video metadata. Uses oEmbed first (reliable), then optional yt-dlp for duration."""
    title = "Unknown Title"
    channel = "Unknown Channel"
    thumbnail = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    duration_str = "N/A"
    url = f"https://www.youtube.com/watch?v={video_id}"

    # 1) oEmbed – lightweight and works more often
    try:
        oembed_url = (
            f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        )
        req = urllib.request.Request(
            oembed_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            title = data.get("title") or title
            channel = data.get("author_name") or channel
            if data.get("thumbnail_url"):
                thumbnail = data["thumbnail_url"]
    except Exception:
        pass

    # 2) Optional: yt-dlp for duration (may fail on some networks)
    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info.get("title"):
                title = info["title"]
            if info.get("uploader") or info.get("channel"):
                channel = info.get("uploader") or info.get("channel")
            if info.get("thumbnail"):
                thumbnail = info["thumbnail"]
            duration = info.get("duration")
            if duration:
                mins, secs = divmod(int(duration), 60)
                hours, mins = divmod(mins, 60)
                if hours:
                    duration_str = f"{hours}:{mins:02d}:{secs:02d}"
                else:
                    duration_str = f"{mins}:{secs:02d}"
    except Exception:
        pass

    return {
        "title": title,
        "channel": channel,
        "thumbnail": thumbnail,
        "duration": duration_str,
        "url": url,
    }


def _transcript_via_api(video_id: str) -> str | None:
    """Try youtube-transcript-api (works best on local / residential IPs)."""
    try:
        try:
            ytt = YouTubeTranscriptApi()
            try:
                fetched = ytt.fetch(video_id, languages=["en", "en-US", "en-GB"])
            except Exception:
                fetched = ytt.fetch(video_id)
            parts = []
            for snippet in fetched:
                if hasattr(snippet, "text"):
                    parts.append(snippet.text)
                elif isinstance(snippet, dict) and "text" in snippet:
                    parts.append(snippet["text"])
            text = " ".join(parts)
        except AttributeError:
            try:
                data = YouTubeTranscriptApi.get_transcript(
                    video_id, languages=["en", "en-US", "en-GB"]
                )
            except Exception:
                data = YouTubeTranscriptApi.get_transcript(video_id)
            text = " ".join(entry["text"] for entry in data)

        text = re.sub(r"\s+", " ", (text or "")).strip()
        return text if len(text) >= 50 else None
    except Exception:
        return None


def _transcript_via_ytdlp(video_id: str) -> str | None:
    """Fallback: extract auto/manual subtitles with yt-dlp."""
    try:
        import yt_dlp
        import tempfile

        url = f"https://www.youtube.com/watch?v={video_id}"
        with tempfile.TemporaryDirectory() as tmp:
            outtmpl = os.path.join(tmp, "subs")
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": ["en", "en-US", "en-GB"],
                "subtitlesformat": "vtt",
                "outtmpl": outtmpl,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            for name in os.listdir(tmp):
                if name.endswith(".vtt"):
                    fpath = os.path.join(tmp, name)
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        raw = f.read()
                    lines = []
                    for line in raw.splitlines():
                        line = line.strip()
                        if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
                            continue
                        if "-->" in line or line.isdigit():
                            continue
                        line = re.sub(r"<[^>]+>", "", line)
                        if line:
                            lines.append(line)
                    text = re.sub(r"\s+", " ", " ".join(lines)).strip()
                    if len(text) >= 50:
                        return text
        return None
    except Exception:
        return None


def _transcript_via_supadata(video_id: str) -> str | None:
    """Cloud-friendly fallback using Supadata free API (100 req/month)."""
    if not SUPADATA_API_KEY:
        return None
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        api_url = (
            "https://api.supadata.ai/v1/transcript?url="
            + urllib.parse.quote(url, safe="")
            + "&text=true"
        )
        req = urllib.request.Request(
            api_url,
            headers={
                "x-api-key": SUPADATA_API_KEY,
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data.get("content")
        if isinstance(content, str) and len(content.strip()) >= 50:
            return content.strip()
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("text"):
                    parts.append(item["text"])
                elif isinstance(item, str):
                    parts.append(item)
            text = re.sub(r"\s+", " ", " ".join(parts)).strip()
            return text if len(text) >= 50 else None
        return None
    except Exception as e:
        print(f"SUPADATA ERROR: {type(e).__name__}: {e}")
        return None


def get_transcript(video_id: str) -> str:
    """Get transcript: Supadata first (cloud) → API → yt-dlp."""
    # Cloud pe pehle Supadata try karo (Render/datacenter IPs ke liye best)
    text = _transcript_via_supadata(video_id)
    if text:
        return text

    text = _transcript_via_api(video_id)
    if text:
        return text

    text = _transcript_via_ytdlp(video_id)
    if text:
        return text

    raise ValueError(
        "No transcript is available for this video, or YouTube blocked the request. "
        "Please try a video that has captions enabled."
    )


def generate_summary_and_keypoints(
    transcript: str, size: str, language: str
) -> tuple[str, list[str]]:
    """Call Gemini to produce summary and key points."""
    if not GEMINI_API_KEY:
        raise ValueError(
            "Gemini API key is not configured. Please set GEMINI_API_KEY in .env"
        )

    size_instruction = SUMMARY_SIZES.get(size, SUMMARY_SIZES["medium"])
    lang_name = SUPPORTED_LANGUAGES.get(language, "English")

    prompt = f"""You are a professional video content summarizer.

Your task is to read the YouTube video transcript below and produce:
1. A clear, well-written summary of the video content.
2. A list of key points.

RULES:
- Use ONLY information that is present in the transcript. Do NOT invent facts, numbers, or claims.
- The summary must explain the important ideas clearly enough that a reader can understand the main content without watching the video.
- Write the entire response in {lang_name}.
- Follow the size instruction strictly.

SIZE INSTRUCTION:
{size_instruction}

OUTPUT FORMAT (strictly follow this structure):
===SUMMARY===
[Write the summary here in well-formed paragraphs. Do not use bullet points in the summary.]

===KEY_POINTS===
- [Key point 1]
- [Key point 2]
- [Key point 3]
(Add as many relevant key points as needed, typically 5-12 depending on content length)

TRANSCRIPT:
{transcript[:30000]}
"""

    try:
        # Valid Gemini models (as of 2025/2026)
        model_names = [
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.8-flash",
        ]
        last_error = None
        text = None
        for name in model_names:
            try:
                model = genai.GenerativeModel(name)
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.4,
                        max_output_tokens=2048,
                    ),
                )
                text = response.text.strip()
                break
            except Exception as e:
                last_error = e
                print(f"GEMINI MODEL {name} FAILED: {e}")
                continue

        if text is None:
            err_msg = str(last_error)[:120] if last_error else "Unknown error"
            raise ValueError(
                f"AI summarization failed. Please try again later. ({err_msg})"
            )
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(
            f"AI summarization failed. Please try again later. ({str(e)[:80]})"
        )

    # Parse response
    summary = ""
    key_points = []

    if "===SUMMARY===" in text and "===KEY_POINTS===" in text:
        parts = text.split("===KEY_POINTS===")
        summary_part = parts[0].replace("===SUMMARY===", "").strip()
        points_part = parts[1].strip() if len(parts) > 1 else ""
        summary = summary_part
        for line in points_part.splitlines():
            line = line.strip()
            if line.startswith("-") or line.startswith("•") or line.startswith("*"):
                point = re.sub(r"^[-•*]\s*", "", line).strip()
                if point:
                    key_points.append(point)
            elif line and not line.startswith("="):
                # Sometimes models omit the dash
                key_points.append(line)
    else:
        # Fallback parsing
        summary = text
        key_points = []

    if not summary:
        summary = "Summary could not be generated from the transcript."
    if not key_points:
        key_points = ["No distinct key points could be extracted."]

    return summary, key_points


def create_txt(video_info: dict, summary: str, key_points: list) -> bytes:
    lines = [
        "AI YouTube Video Summarizer",
        "=" * 40,
        "",
        f"Video Title: {video_info.get('title', 'N/A')}",
        f"Channel: {video_info.get('channel', 'N/A')}",
        f"Video URL: {video_info.get('url', 'N/A')}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "-" * 40,
        "VIDEO SUMMARY",
        "-" * 40,
        "",
        summary,
        "",
        "-" * 40,
        "KEY POINTS",
        "-" * 40,
        "",
    ]
    for i, point in enumerate(key_points, 1):
        lines.append(f"{i}. {point}")
    lines.append("")
    lines.append("=" * 40)
    lines.append("Generated by AI YouTube Video Summarizer")
    return "\n".join(lines).encode("utf-8")


def create_pdf(video_info: dict, summary: str, key_points: list) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=6,
        textColor="#1a1a1a",
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=14,
        spaceAfter=8,
        textColor="#c4302b",
    )
    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=6,
        alignment=TA_LEFT,
    )
    meta_style = ParagraphStyle(
        "Meta",
        parent=styles["Normal"],
        fontSize=9,
        textColor="#555555",
        spaceAfter=3,
    )

    story = []
    story.append(Paragraph("AI YouTube Video Summarizer", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>Title:</b> {video_info.get('title', 'N/A')}", meta_style))
    story.append(Paragraph(f"<b>Channel:</b> {video_info.get('channel', 'N/A')}", meta_style))
    story.append(Paragraph(f"<b>URL:</b> {video_info.get('url', 'N/A')}", meta_style))
    story.append(
        Paragraph(
            f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", meta_style
        )
    )
    story.append(Spacer(1, 12))

    story.append(Paragraph("Video Summary", heading_style))
    for para in summary.split("\n"):
        para = para.strip()
        if para:
            story.append(Paragraph(para, body_style))

    story.append(Paragraph("Key Points", heading_style))
    items = []
    for point in key_points:
        items.append(ListItem(Paragraph(point, body_style), leftIndent=10, bulletColor="#c4302b"))
    story.append(ListFlowable(items, bulletType="bullet", start="•"))

    story.append(Spacer(1, 20))
    story.append(
        Paragraph(
            "Generated by AI YouTube Video Summarizer",
            ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8, textColor="#888888"),
        )
    )

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def create_docx(video_info: dict, summary: str, key_points: list) -> bytes:
    doc = Document()

    # Title
    title = doc.add_heading("AI YouTube Video Summarizer", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # Meta
    p = doc.add_paragraph()
    run = p.add_run(f"Video Title: ")
    run.bold = True
    p.add_run(video_info.get("title", "N/A"))

    p = doc.add_paragraph()
    run = p.add_run(f"Channel: ")
    run.bold = True
    p.add_run(video_info.get("channel", "N/A"))

    p = doc.add_paragraph()
    run = p.add_run(f"Video URL: ")
    run.bold = True
    p.add_run(video_info.get("url", "N/A"))

    p = doc.add_paragraph()
    run = p.add_run(f"Generated: ")
    run.bold = True
    p.add_run(datetime.now().strftime("%Y-%m-%d %H:%M"))

    doc.add_paragraph()

    # Summary
    heading = doc.add_heading("Video Summary", level=1)
    for run in heading.runs:
        run.font.color.rgb = RGBColor(0xC4, 0x30, 0x2B)

    for para in summary.split("\n"):
        para = para.strip()
        if para:
            p = doc.add_paragraph(para)
            p.paragraph_format.space_after = Pt(8)

    # Key Points
    heading = doc.add_heading("Key Points", level=1)
    for run in heading.runs:
        run.font.color.rgb = RGBColor(0xC4, 0x30, 0x2B)

    for point in key_points:
        doc.add_paragraph(point, style="List Bullet")

    doc.add_paragraph()
    footer = doc.add_paragraph("Generated by AI YouTube Video Summarizer")
    footer.runs[0].font.size = Pt(9)
    footer.runs[0].font.color.rgb = RGBColor(0x88, 0x88, 0x88)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/api/video-info", methods=["POST"])
def video_info():
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "Please enter a YouTube video URL."}), 400

    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL. Please check the link and try again."}), 400

    try:
        info = get_video_info(video_id)
        info["video_id"] = video_id
        return jsonify(info)
    except Exception:
        return jsonify({"error": "Could not fetch video information. Please try another video."}), 400


@app.route("/api/summarize", methods=["POST"])
def summarize():
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    size = data.get("size", "").strip().lower()
    language = data.get("language", "").strip().lower()

    if not url:
        return jsonify({"error": "Please enter a YouTube video URL."}), 400
    if size not in SUMMARY_SIZES:
        return jsonify({"error": "Please select a summary size (Short, Medium, or Detailed)."}), 400
    if language not in SUPPORTED_LANGUAGES:
        return jsonify({"error": "Please select a language."}), 400

    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL. Please check the link and try again."}), 400

    try:
        video_info_data = get_video_info(video_id)
        transcript = get_transcript(video_id)
        summary, key_points = generate_summary_and_keypoints(transcript, size, language)

        return jsonify(
            {
                "video_info": video_info_data,
                "summary": summary,
                "key_points": key_points,
            }
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"SUMMARIZE ERROR: {type(e).__name__}: {e}")
        return jsonify(
            {"error": f"Something went wrong: {str(e)[:150]}"}
        ), 500


@app.route("/api/download", methods=["POST"])
def download():
    data = request.get_json() or {}
    fmt = data.get("format", "txt").lower()
    video_info = data.get("video_info") or {}
    summary = data.get("summary", "")
    key_points = data.get("key_points") or []

    if not summary:
        return jsonify({"error": "No summary available to download."}), 400

    try:
        if fmt == "txt":
            content = create_txt(video_info, summary, key_points)
            mimetype = "text/plain"
            filename = "youtube_summary.txt"
        elif fmt == "pdf":
            content = create_pdf(video_info, summary, key_points)
            mimetype = "application/pdf"
            filename = "youtube_summary.pdf"
        elif fmt == "docx":
            content = create_docx(video_info, summary, key_points)
            mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            filename = "youtube_summary.docx"
        else:
            return jsonify({"error": "Unsupported format. Choose txt, pdf, or docx."}), 400

        return send_file(
            io.BytesIO(content),
            mimetype=mimetype,
            as_attachment=True,
            download_name=filename,
        )
    except Exception:
        return jsonify({"error": "Failed to generate the download file. Please try again."}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)