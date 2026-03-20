# Fovea — Search Your Security Footage with Words

**Fovea is a free, open source desktop application that lets you search security camera footage using natural language — type what you saw, and Fovea finds it.**

---

📩 **Any bugs should be reported to: shamlancontact@gmail.com**

Instead of scrubbing through hours of recordings frame by frame, just describe what you're looking for — *"red car with white stripe"*, *"person in dark hoodie"* — and Fovea searches across all your cameras simultaneously to find it.

---

> **Website:** [fovea-ai.netlify.app](https://fovea-ai.netlify.app) &nbsp;|&nbsp; **Download:** [GitHub Releases](https://github.com/Fovea-ai/Fovea/releases)

---

## ✨ Features

- ✅ **Natural language search** — describe what you saw in plain English
- ✅ **Multi-camera search** — searches all connected cameras at once
- ✅ **Works completely offline** — built-in local AI with no API key required
- ✅ **Supports 5 AI providers** — ChatGPT, Gemini, Claude, Grok, DeepSeek
- ✅ **Any camera type** — webcams, USB, RTSP, HTTP/MJPEG, and phone cameras
- ✅ **100% local storage** — your footage never leaves your machine
- ✅ **AES-256-GCM encryption** — API keys stored securely
- ✅ **Timeline export** — export search results as timestamped photos
- ✅ **Community AI training** — contribute and vote on training data via global sync
- ✅ **Cross-platform** — Windows 10/11, macOS, Linux

---

## 🔍 How It Works

**1. Connect your cameras**
Add any camera — a USB webcam, an IP camera on your network, or your phone running IP Webcam. Fovea captures frames locally in the background.

**2. Describe what you're looking for**
Type a natural language description into the search bar. Fovea sends the query through your chosen AI provider (or runs local detection entirely offline) and scans your recorded frames.

**3. Review and export results**
Matching frames are displayed with timestamps. Export your results as a sorted photo timeline for easy review or record-keeping.

---

## 🤖 Supported AI Providers

| Provider | Model |
|---|---|
| OpenAI | GPT-4o |
| Google | Gemini 2.5 Flash |
| Anthropic | Claude |
| xAI | Grok |
| DeepSeek | DeepSeek |
| **Built-in (offline)** | Local color, person & vehicle detection — no API key needed |

---

## 📷 Supported Camera Types

| Type | Examples |
|---|---|
| Webcams & USB cameras | Any standard webcam |
| RTSP IP cameras | Hikvision, Dahua, Reolink, TP-Link Tapo |
| HTTP / MJPEG streams | Browser-accessible camera feeds |
| Phone cameras | Android via IP Webcam app |

---

## 🚀 Installation

### Windows

Download the pre-built installer from the [Releases page](https://github.com/Fovea-ai/Fovea/releases):

- **Option A:** Download `Fovea.exe` and run it directly.
- **Option B:** Download the repository and run `setup_and_run.bat` for automatic dependency setup and launch.

### macOS & Linux

**Requirements:** Python 3.13

```bash
# 1. Clone the repository
git clone https://github.com/Fovea-ai/Fovea.git
cd Fovea

# 2. Install dependencies
pip install PyQt6 opencv-python requests cryptography plyer numpy supabase

# 3. Run the app
python main.py
```

---

## ⚙️ First-Time Setup

1. **Accept the Terms of Use** when prompted on first launch.
2. **Set a Master Password** — go to Settings → Master Password.
3. **Approve your machine** — go to Settings → Approval Keys → Open Key Manager → Admin Panel → Approve My Machine.
4. **Add a camera** — connect a webcam, enter an RTSP URL, or add an HTTP stream.
5. **Start searching** — type a description and let Fovea do the rest.

---

## 🗂️ Project Structure

```
Fovea/
├── main.py              # Application entry point
├── core/
│   ├── storage.py       # Local data storage
│   ├── capture.py       # Camera capture engine
│   ├── ai_handler.py    # AI provider integration
│   ├── search_worker.py # Search orchestration
│   ├── local_search.py  # Offline detection (color, person, vehicle)
│   └── supabase_sync.py # Community training sync
└── ui/
    ├── dashboard.py     # Main dashboard
    ├── cameras.py       # Camera management
    ├── search.py        # Search interface
    ├── settings.py      # Settings & key management
    ├── training.py      # Community AI training
    ├── voting.py        # Training data voting
    └── terms.py         # Terms of use
```

---

## 🤝 Contributing

Contributions are welcome. Whether it's a bug fix, new camera integration, UI improvement, or documentation update — feel free to open an issue or submit a pull request.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to your branch: `git push origin feature/your-feature`
5. Open a Pull Request

Please check open issues before starting work on something new to avoid duplication.

---

## ⚠️ Disclaimer

- **AI accuracy is not guaranteed.** Search results depend on the quality of your camera feed, lighting conditions, and the AI model used. Fovea may miss relevant footage or return false matches.
- **Not for use as legal evidence.** Fovea is not designed or validated for evidentiary or forensic purposes. Do not rely on Fovea output in legal proceedings.
- **Know your local recording laws.** You are solely responsible for ensuring that your use of security cameras complies with applicable privacy and recording laws in your jurisdiction. Always obtain consent where required.
- **No warranty is provided.** Fovea is offered as-is. The developers accept no liability for any outcomes arising from its use.

---

## 🌍 The Mission

Fovea was built with one goal: **make security accessible to everyone.**

Security cameras have been shown to reduce crime by 13–20%. But footage is only useful if you can actually find what you're looking for — and that capability has historically been locked behind expensive professional systems. Fovea changes that. It's free, open source, and designed to work with the cameras people already have.

If Fovea helps someone stay safe, recover stolen property, or support a police investigation, it has done its job.

---

*Open Source · Free Forever*
