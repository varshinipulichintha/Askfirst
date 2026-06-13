# AskFirst Chat Engine — Setup & Run

## 1. Install dependencies
```bash
pip install -r requirements.txt
```

## 2. Configure your API key
```bash
cp .env.example .env
# Edit .env and paste your Groq API key
# Get a free key at https://console.groq.com
```

## 3. Run the backend (Terminal 1)
```bash
uvicorn main:app --reload --port 8000
```

## 4. Run the frontend (Terminal 2)
```bash
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

---

## Thread Types

| Type | Icon | Purpose |
|------|------|---------|
| **Reader** | 📖 | Reads & retrieves data from conversation history |
| **Writer** | ✏️ | Stores and structures new data entries / notes |
| **Memory** | 🧠 | Cross-thread recall — AI knows everything from all threads |
| **General** | 💬 | Standard chat |

## How Universal Memory Works
After every message, the backend automatically summarises **all threads** into a
compact memory blob stored in SQLite. Every subsequent request (in any thread) gets
this summary injected into the system prompt — so Thread 3 always knows what was
discussed in Thread 1 and Thread 2.

You can also manually trigger a refresh via **🔄 Refresh Memory** in the sidebar,
and inspect the current memory blob via **🧠 View Universal Memory**.
