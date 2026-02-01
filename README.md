# UniVR Chatbot 🎓

A beautiful RAG-powered chatbot for the University of Verona that helps students find information about scholarships, tuition, admissions, and more.

![Powered by Gemini AI](https://img.shields.io/badge/Powered%20by-Gemini%20AI-blue)
![Heroku Ready](https://img.shields.io/badge/Heroku-Ready-purple)

## ✨ Features

- 🤖 **AI-Powered Responses** - Uses Gemini with RAG for accurate answers
- 📚 **Document Search** - Searches university PDFs and announcements
- 🌍 **Bilingual** - Supports Italian and English
- 🎨 **Beautiful UI** - Glassmorphism design with dark mode
- 📱 **Responsive** - Works on mobile and desktop
- 🚀 **Heroku Ready** - One-click deployment

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.12+
- [UV Package Manager](https://github.com/astral-sh/uv) (recommended)
- Gemini API Key from [Google AI Studio](https://aistudio.google.com/)

### 2. Setup

```bash
# Clone and enter directory
cd univr-chatbot

# Copy environment template
cp .env.template .env

# Edit .env and add your GEMINI_API_KEY
nano .env

# Install dependencies
uv sync

# Run the server
uv run uvicorn app.main:app --reload --port 8000
```

### 3. Open in Browser

Visit **http://localhost:8000** and start chatting! 🎉

## 📁 Project Structure

```
univr-chatbot/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration
│   ├── api/
│   │   ├── chat.py          # Chat endpoints
│   │   └── admin.py         # Admin endpoints
│   ├── agents/
│   │   └── univr_agent.py   # RAG agent with Gemini
│   └── services/
│       └── store_manager.py # File Search Store management
├── static/                  # CSS, JS, images
├── templates/               # HTML templates
├── data/                    # Sample documents
├── Procfile                 # Heroku deployment
└── pyproject.toml           # Dependencies
```

## 🔧 Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Your Gemini API key | Required |
| `MODEL` | Gemini model to use | `gemini-2.5-flash` |
| `STORE_NAME` | File Search Store name | `univr-file-store` |

## 📚 Adding Documents

### Option 1: Admin API

```bash
curl -X POST http://localhost:8000/api/admin/upload \
  -F "file=@scholarship_info.pdf" \
  -F "department=scholarships"
```

### Option 2: Jupyter Notebook

Use the notebook in the reference `gemini-file-search-demo` project to manage your File Search Store.

## 🚀 Deploy to Heroku

```bash
# Login to Heroku
heroku login

# Create app
heroku create univr-chatbot

# Set environment variables
heroku config:set GEMINI_API_KEY=your-api-key
heroku config:set STORE_NAME=univr-file-store

# Deploy
git push heroku main
```

## 🎓 Demo Questions

Try asking:
- "What scholarships are available for international students?"
- "Quali sono le scadenze per le tasse universitarie?"
- "How do I apply for the Right to Education program?"
- "What documents do I need for admission?"

## 📄 License

MIT License - Built with ❤️ for University of Verona students
