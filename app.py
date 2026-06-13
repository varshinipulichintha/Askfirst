import streamlit as st
import requests

API = "http://localhost:8000"

st.set_page_config(
    page_title="AskFirst Chat",
    page_icon="💬",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* ── global ── */
    html, body, [data-testid="stAppViewContainer"] {
        background: #0f1117;
        color: #e8eaf0;
        font-family: 'Inter', sans-serif;
    }
    [data-testid="stSidebar"] {
        background: #161b27;
        border-right: 1px solid #2a2f3e;
    }

    /* ── thread pills ── */
    .thread-pill {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 14px;
        border-radius: 10px;
        margin-bottom: 6px;
        cursor: pointer;
        background: #1e2333;
        border: 1px solid transparent;
        transition: all .15s;
    }
    .thread-pill:hover { border-color: #4f6ef7; }
    .thread-pill.active { background: #1a2455; border-color: #4f6ef7; }
    .thread-pill .badge {
        font-size: 10px;
        padding: 2px 7px;
        border-radius: 20px;
        font-weight: 600;
        letter-spacing: .5px;
        text-transform: uppercase;
    }
    .badge-reader  { background: #1a3a5c; color: #5bc0eb; }
    .badge-writer  { background: #1a3a2a; color: #5be07a; }
    .badge-memory  { background: #3a1a3a; color: #e05be0; }
    .badge-general { background: #2a2f3e; color: #a0a8c0; }

    /* ── chat bubbles ── */
    .bubble-wrap { display:flex; margin:6px 0; }
    .bubble-wrap.user  { justify-content: flex-end; }
    .bubble-wrap.assistant { justify-content: flex-start; }
    .bubble {
        max-width: 72%;
        padding: 12px 16px;
        border-radius: 14px;
        font-size: 14.5px;
        line-height: 1.55;
        white-space: pre-wrap;
        word-break: break-word;
    }
    .bubble.user      { background: #2a3f8f; color: #e8ecff; border-bottom-right-radius: 4px; }
    .bubble.assistant { background: #1e2333; color: #d8dce8; border-bottom-left-radius: 4px; }

    /* ── input bar ── */
    [data-testid="stTextInput"] input {
        background: #1e2333 !important;
        color: #e8eaf0 !important;
        border: 1px solid #2a2f3e !important;
        border-radius: 10px !important;
    }
    button[kind="primary"] {
        background: #4f6ef7 !important;
        border: none !important;
    }

    /* ── section header ── */
    .section-header {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        color: #5a6080;
        margin: 18px 0 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Helpers ───────────────────────────────────────────────────────
def fetch_threads():
    try:
        r = requests.get(f"{API}/threads", timeout=5)
        return r.json() if r.ok else []
    except Exception:
        return []


def fetch_messages(thread_id):
    try:
        r = requests.get(f"{API}/threads/{thread_id}/messages", timeout=5)
        return r.json() if r.ok else []
    except Exception:
        return []


def send_message(thread_id, user_msg):
    try:
        r = requests.post(
            f"{API}/chat",
            json={"thread_id": thread_id, "user_message": user_msg},
            timeout=30,
        )
        return r.json().get("reply", "⚠️ No reply") if r.ok else "⚠️ API error"
    except Exception as e:
        return f"⚠️ Connection error: {e}"


def create_thread(name, thread_type):
    try:
        r = requests.post(
            f"{API}/threads",
            json={"name": name, "thread_type": thread_type},
            timeout=5,
        )
        return r.json() if r.ok else None
    except Exception:
        return None


def delete_thread(thread_id):
    try:
        requests.delete(f"{API}/threads/{thread_id}", timeout=5)
    except Exception:
        pass


def fetch_memory():
    try:
        r = requests.get(f"{API}/memory", timeout=5)
        return r.json().get("memory", "") if r.ok else ""
    except Exception:
        return ""


def refresh_memory():
    try:
        r = requests.post(f"{API}/memory/refresh", timeout=30)
        return r.json().get("memory", "") if r.ok else ""
    except Exception as e:
        return f"Error: {e}"


BADGE = {
    "reader": ("📖", "badge-reader", "Reader"),
    "writer": ("✏️", "badge-writer", "Writer"),
    "memory": ("🧠", "badge-memory", "Memory"),
    "general": ("💬", "badge-general", "General"),
}

# ── Session state ─────────────────────────────────────────────────
if "active_thread" not in st.session_state:
    st.session_state.active_thread = None
if "show_memory" not in st.session_state:
    st.session_state.show_memory = False

# ── Sidebar ───────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        "<div style='font-size:22px;font-weight:800;color:#e8eaf0;margin-bottom:4px'>"
        "💬 AskFirst</div>"
        "<div style='font-size:12px;color:#5a6080;margin-bottom:18px'>Clary Team · Chat Engine</div>",
        unsafe_allow_html=True,
    )

    # Create thread form
    with st.expander("＋ New Thread", expanded=False):
        tname = st.text_input("Thread name", key="new_tname", placeholder="My thread…")
        ttype = st.selectbox(
            "Type",
            ["reader", "writer", "memory", "general"],
            format_func=lambda x: {"reader": "📖 Reader — reads data",
                                    "writer": "✏️ Writer — stores data",
                                    "memory": "🧠 Memory — cross-thread recall",
                                    "general": "💬 General"}[x],
            key="new_ttype",
        )
        if st.button("Create", use_container_width=True, type="primary"):
            if tname.strip():
                t = create_thread(tname.strip(), ttype)
                if t:
                    st.session_state.active_thread = t["id"]
                    st.rerun()
            else:
                st.warning("Enter a name.")

    st.markdown("<div class='section-header'>Threads</div>", unsafe_allow_html=True)

    threads = fetch_threads()
    if not threads:
        st.caption("No threads yet. Create one above.")
    else:
        for t in threads:
            icon, badge_cls, label = BADGE.get(t["thread_type"], ("💬", "badge-general", "General"))
            is_active = st.session_state.active_thread == t["id"]
            active_cls = "active" if is_active else ""

            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(
                    f"""<div class='thread-pill {active_cls}'>
                        {icon} <span style='flex:1;font-size:13.5px'>{t['name']}</span>
                        <span class='badge {badge_cls}'>{label}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )
                if st.button(
                    t["name"],
                    key=f"sel_{t['id']}",
                    use_container_width=True,
                    help=f"Switch to {t['name']}",
                ):
                    st.session_state.active_thread = t["id"]
                    st.rerun()
            with col2:
                if st.button("🗑️", key=f"del_{t['id']}", help="Delete thread"):
                    delete_thread(t["id"])
                    if st.session_state.active_thread == t["id"]:
                        st.session_state.active_thread = None
                    st.rerun()

    st.divider()
    if st.button("🧠 View Universal Memory", use_container_width=True):
        st.session_state.show_memory = not st.session_state.show_memory
    if st.button("🔄 Refresh Memory", use_container_width=True):
        refresh_memory()
        st.success("Memory refreshed!")

# ── Main area ─────────────────────────────────────────────────────
if st.session_state.show_memory:
    st.subheader("🧠 Universal Memory")
    mem = fetch_memory()
    if mem:
        st.info(mem)
    else:
        st.caption("No memory stored yet. Chat in a few threads first.")
    st.divider()

if st.session_state.active_thread is None:
    # Landing
    st.markdown(
        """
        <div style='text-align:center;padding:80px 0 40px'>
            <div style='font-size:52px'>💬</div>
            <h2 style='color:#e8eaf0;margin:12px 0 8px'>AskFirst Chat Engine</h2>
            <p style='color:#5a6080;font-size:15px'>
                Select or create a thread from the sidebar to start chatting.
            </p>
        </div>
        <div style='display:flex;gap:20px;justify-content:center;flex-wrap:wrap;margin-top:20px'>
            <div style='background:#1e2333;border:1px solid #2a2f3e;border-radius:14px;padding:20px 28px;min-width:200px'>
                <div style='font-size:28px'>📖</div>
                <div style='font-weight:700;margin:8px 0 4px;color:#5bc0eb'>Reader Thread</div>
                <div style='color:#6a7090;font-size:13px'>Reads & retrieves data from conversation history</div>
            </div>
            <div style='background:#1e2333;border:1px solid #2a2f3e;border-radius:14px;padding:20px 28px;min-width:200px'>
                <div style='font-size:28px'>✏️</div>
                <div style='font-weight:700;margin:8px 0 4px;color:#5be07a'>Writer Thread</div>
                <div style='color:#6a7090;font-size:13px'>Stores and structures new data & notes</div>
            </div>
            <div style='background:#1e2333;border:1px solid #2a2f3e;border-radius:14px;padding:20px 28px;min-width:200px'>
                <div style='font-size:28px'>🧠</div>
                <div style='font-weight:700;margin:8px 0 4px;color:#e05be0'>Memory Thread</div>
                <div style='color:#6a7090;font-size:13px'>Cross-thread recall — remembers everything</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# ── Active thread chat ────────────────────────────────────────────
active = next((t for t in threads if t["id"] == st.session_state.active_thread), None)
if not active:
    st.warning("Thread not found. Please select another.")
    st.stop()

icon, badge_cls, label = BADGE.get(active["thread_type"], ("💬", "badge-general", "General"))

st.markdown(
    f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:4px'>"
    f"<span style='font-size:24px'>{icon}</span>"
    f"<span style='font-size:20px;font-weight:700'>{active['name']}</span>"
    f"<span class='badge {badge_cls}' style='font-size:11px;padding:3px 10px;border-radius:20px'>{label}</span>"
    f"</div>",
    unsafe_allow_html=True,
)

TYPE_DESC = {
    "reader": "📖 This thread **reads data** — ask it to retrieve or summarise past info.",
    "writer": "✏️ This thread **writes data** — tell it what to record or structure.",
    "memory": "🧠 This thread **uses universal memory** — it knows everything from all threads.",
    "general": "💬 General purpose thread.",
}
st.caption(TYPE_DESC.get(active["thread_type"], ""))
st.divider()

# Message history
messages = fetch_messages(st.session_state.active_thread)
chat_container = st.container()

with chat_container:
    if not messages:
        st.markdown(
            "<div style='text-align:center;color:#3a4060;padding:40px 0'>No messages yet. Say hello!</div>",
            unsafe_allow_html=True,
        )
    else:
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            st.markdown(
                f"<div class='bubble-wrap {role}'>"
                f"<div class='bubble {role}'>{content}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

# Input bar
st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
col_inp, col_btn = st.columns([9, 1])
with col_inp:
    user_input = st.text_input(
        "Message",
        key="user_input",
        placeholder=f"Message {active['name']}…",
        label_visibility="collapsed",
    )
with col_btn:
    send = st.button("Send", type="primary", use_container_width=True)

if send and user_input.strip():
    with st.spinner("Thinking…"):
        send_message(st.session_state.active_thread, user_input.strip())
    st.rerun()
