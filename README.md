# AI YouTube Video Summarizer

A clean, professional web app that summarizes YouTube videos using AI (Google Gemini).  
Paste a YouTube URL → get video details → choose summary length & language → receive a clear summary and key points → copy or download as TXT / PDF / Word.

Built for portfolio and GitHub. Simple stack, no unnecessary features.

---

## Features

- Paste any public YouTube video URL
- Fetch thumbnail, title, channel name, and duration
- Choose summary size: **Short**, **Medium**, or **Detailed**
- Choose language: English, Urdu, Roman Urdu, German, Spanish, French, Arabic
- AI-generated **Video Summary** (well-written paragraphs)
- Separate **Key Points** list with clean bullets
- Copy Summary / Copy Key Points buttons
- Download as **TXT**, **PDF**, or **Word (.docx)** with professional formatting
- Responsive design (desktop, tablet, mobile)
- Clear error messages for missing transcript, invalid URL, API issues, etc.
- API key kept server-side only (`.env`)

---

## Technologies

| Layer     | Stack                                      |
|-----------|--------------------------------------------|
| Frontend  | HTML5, CSS3, Vanilla JavaScript             |
| Backend   | Python, Flask                              |
| AI        | Google Gemini API (`gemini-1.5-flash`)     |
| Transcript| `youtube-transcript-api`                   |
| Metadata  | `yt-dlp`                                   |
| PDF       | ReportLab                                  |
| Word      | python-docx                                |

---

## Folder Structure

```
AI-YouTube-Summarizer/
├── app.py                 # Flask backend (all routes & logic)
├── requirements.txt       # Python dependencies
├── .env.example           # Template for environment variables
├── .gitignore
├── README.md
├── templates/
│   └── index.html         # Main page
├── static/
│   ├── css/
│   │   └── style.css      # Styles
│   ├── js/
│   │   └── script.js      # Frontend logic
│   └── assets/            # (optional images)
└── downloads/             # Temporary download folder (gitignored content)
```

---

## Local Setup (Windows + PowerShell)

### 1. Open the project in VS Code
- Extract or clone the project folder
- Open the folder in VS Code: `File → Open Folder`

### 2. Open Terminal
- In VS Code: `Terminal → New Terminal` (or `` Ctrl+` ``)
- Make sure the terminal is **PowerShell**

### 3. Create a virtual environment
```powershell
python -m venv venv
```

### 4. Activate the virtual environment
```powershell
.\venv\Scripts\Activate
```
You should see `(venv)` at the start of the prompt.

### 5. Install requirements
```powershell
pip install -r requirements.txt
```

### 6. Create the `.env` file
```powershell
Copy-Item .env.example .env
```

### 7. Add your Gemini API key
- Open `.env` in VS Code
- Get a free key from [Google AI Studio](https://aistudio.google.com/apikey)
- Edit the file so it looks like:
```
GEMINI_API_KEY=your_actual_api_key_here
```
- Save the file  
**Never commit `.env` or share your key.**

### 8. Start the Flask server
```powershell
python app.py
```

### 9. Open the website
- Open your browser and go to:  
  **http://127.0.0.1:5000**

### 10. Stop the server
- In the terminal press `Ctrl + C`

---

## How to Use the App

1. Paste a YouTube video URL
2. (Optional) Click **Get Info** to preview title, channel, thumbnail, duration
3. Select **Summary Size** (required)
4. Select **Language** (required)
5. Click **Generate Summary**
6. Read the **Video Summary** and **Key Points**
7. Use **Copy** buttons or **Download** (TXT / PDF / Word)

---

## Push to GitHub

```powershell
# Initialize (if not already a git repo)
git init

# Make sure .env is ignored
git status   # .env should NOT appear

# Add all files
git add .

# Commit
git commit -m "Initial commit: AI YouTube Video Summarizer"

# Create a new repository on GitHub (via website or GitHub CLI)
# Then connect and push (replace with your repo URL):
git remote add origin https://github.com/faraz721/AI-YouTube-Summarizer.git
git branch -M main
git push -u origin main
```

**Important:** Never push the `.env` file. It is already listed in `.gitignore`.

---

## Free Deployment (Render)

Render currently offers a free tier for web services (with cold starts after ~15 minutes of inactivity). No credit card required for the free plan.

### Steps

1. Create a free account at [https://render.com](https://render.com)
2. Click **New → Web Service**
3. Connect your GitHub account and select the repository `AI-YouTube-Summarizer`
4. Configure:
   - **Name**: anything (e.g. `ai-youtube-summarizer`)
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: Free
5. Under **Environment** add:
   - Key: `GEMINI_API_KEY`
   - Value: your Gemini API key
6. Click **Create Web Service**
7. Wait for the deploy to finish (a few minutes)
8. You will receive a public URL such as:  
   `https://ai-youtube-summarizer.onrender.com`
9. Open the URL in a browser or phone and test with a YouTube video that has captions

### Notes about free tier
- The service sleeps after ~15 minutes of no traffic
- First request after sleep can take 30–60 seconds (cold start)
- Suitable for portfolio demos and personal use

---

## Environment Variables

| Variable         | Required | Description                    |
|------------------|----------|--------------------------------|
| `GEMINI_API_KEY` | Yes      | Your Google Gemini API key     |
| `PORT`           | No       | Used by hosting platforms      |

---

## Limitations

- Only works with videos that have available transcripts/captions
- Private, age-restricted, or region-blocked videos may fail
- Very long videos may be truncated for the AI prompt (first ~50k characters of transcript)
- Gemini free tier has rate limits
- Free hosting (Render) has cold starts

---

## License

MIT – feel free to use this project in your portfolio.

---

**Built by [Faraz721](https://github.com/faraz721)**
