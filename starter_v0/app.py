from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from env_loader import load_lab_env
from providers import make_provider
from providers.base import ToolCall
from tools import TOOL_FUNCTIONS, load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version

ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
TRANSCRIPTS_DIR = ROOT / "transcripts"
load_lab_env(ROOT)

PROVIDERS = ["openrouter", "openai", "anthropic", "gemini", "opencode"]
VERSIONS = ["v0", "v1", "v2", "v3"]

PAGE_STYLE = """
<style>
    .main-header {
        font-size: 1.8rem;
        font-weight: 700;
        padding: 0.5rem 0 1rem 0;
        border-bottom: 2px solid #e0e0e0;
        margin-bottom: 1.5rem;
    }
    .tool-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        background: #f0f0f0;
        color: #333;
        margin-right: 4px;
    }
    .tool-badge.error { background: #ffe0e0; color: #c00; }
    .tool-badge.success { background: #e0ffe0; color: #060; }
    .sidebar-section {
        padding: 0.5rem 0;
        border-bottom: 1px solid #e0e0e0;
        margin-bottom: 0.5rem;
    }
    .metric-box {
        background: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        margin: 0.25rem 0;
    }
    .metric-box .label { font-size: 0.7rem; color: #666; text-transform: uppercase; }
    .metric-box .value { font-size: 1.2rem; font-weight: 700; }
    .chat-container {
        max-width: 900px;
        margin: 0 auto;
    }
    footer { visibility: hidden; }
    .stChatMessage { padding: 1rem 1.5rem; }
</style>
"""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def json_text(value, max_chars: int = 24000) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    return text[:max_chars] + "\n...<truncated>" if len(text) > max_chars else text


def execute_tool_call(call: ToolCall) -> dict:
    func = TOOL_FUNCTIONS.get(call.name)
    if not func:
        return {"tool": call.name, "args": call.args, "result": {"error": "unknown_tool"}}
    try:
        result = func(**call.args)
    except Exception as exc:
        result = {"error": type(exc).__name__, "message": str(exc)}
    return {"tool": call.name, "args": call.args, "result": result}


def tool_results_message(events: list[dict]) -> dict:
    return {
        "role": "user",
        "content": (
            "TOOL_RESULTS_JSON:\n"
            f"{json_text(events)}\n\n"
            "Use only these tool results. If the user asked for a digest and the items are ready, "
            "call the formatting tool. Otherwise answer the user directly with cited sources when available."
        ),
    }


def assistant_tool_message(response_text: str | None, calls: list[ToolCall]) -> dict:
    call_summary = [{"name": c.name, "args": c.args} for c in calls]
    content = response_text or "I will call the selected tool(s)."
    return {"role": "assistant", "content": f"{content}\n\nTOOL_CALLS_JSON:\n{json_text(call_summary)}"}


def run_model_tool_loop(*, provider, messages, tools, model, max_tool_rounds=4):
    working_messages = list(messages)
    rounds = []
    all_tool_events = []

    for round_index in range(1, max_tool_rounds + 1):
        response = provider.complete(working_messages, tools, model=model, temperature=0.0)
        calls = response.tool_calls
        round_record = {
            "round": round_index,
            "assistant_text": response.text,
            "tool_calls": [{"name": c.name, "args": c.args} for c in calls],
            "tool_results": [],
        }

        if not calls:
            rounds.append(round_record)
            return {
                "status": "answered",
                "assistant_text": response.text or "",
                "rounds": rounds,
                "tool_events": all_tool_events,
            }

        working_messages.append(assistant_tool_message(response.text, calls))
        non_clarification_events = []

        for call in calls:
            event = execute_tool_call(call)
            round_record["tool_results"].append(event)
            all_tool_events.append(event)

            result = event.get("result", {})
            if isinstance(result, dict) and result.get("awaiting_user"):
                question = result.get("question") or call.args.get("question") or "Please provide more info."
                rounds.append(round_record)
                return {
                    "status": "waiting_for_user",
                    "assistant_text": question,
                    "rounds": rounds,
                    "tool_events": all_tool_events,
                }

            non_clarification_events.append(event)

        rounds.append(round_record)
        working_messages.append(tool_results_message(non_clarification_events))

    return {
        "status": "max_tool_rounds",
        "assistant_text": f"Stopped after {max_tool_rounds} tool rounds.",
        "rounds": rounds,
        "tool_events": all_tool_events,
    }


def render_tool_call(t: dict) -> None:
    has_error = isinstance(t.get("result"), dict) and "error" in t.get("result", {})
    badge_class = "error" if has_error else "success"
    args_str = json.dumps(t["args"], ensure_ascii=False)
    st.markdown(
        f'<span class="tool-badge {badge_class}">{t["name"]}</span>'
        f'<code style="font-size:0.8rem">{args_str}</code>',
        unsafe_allow_html=True,
    )
    if has_error:
        st.error(t["result"])
    elif t.get("result") and t["result"] != {}:
        with st.expander("Result"):
            st.json(t["result"])


# --- Page config & style ---
st.set_page_config(
    page_title="Research Agent",
    page_icon="R",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(PAGE_STYLE, unsafe_allow_html=True)

# --- Init session state ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "history" not in st.session_state:
    st.session_state.history = []
if "transcript_turns" not in st.session_state:
    st.session_state.transcript_turns = []
if "provider" not in st.session_state:
    st.session_state.provider = None
    st.session_state.provider_name = None

# --- Load artifacts ---
system_prompt = (ARTIFACTS_DIR / "system_prompt.md").read_text(encoding="utf-8")
tool_declarations = load_tool_declarations(ARTIFACTS_DIR / "tools.yaml")
openai_tools = to_openai_tools(tool_declarations)
_initial_artifact_version = build_artifact_version(VERSIONS[0], ARTIFACTS_DIR / "system_prompt.md", ARTIFACTS_DIR / "tools.yaml")

# --- Sidebar ---
with st.sidebar:
    st.markdown("## Configuration")

    provider_name = st.selectbox("Provider", PROVIDERS, index=4)
    version = st.selectbox("Version", VERSIONS)
    model = st.text_input("Model override", placeholder="Use provider default")
    max_rounds = st.slider("Max tool rounds", 1, 8, 4)
    artifact_version = build_artifact_version(version, ARTIFACTS_DIR / "system_prompt.md", ARTIFACTS_DIR / "tools.yaml")

    if st.session_state.provider_name != provider_name:
        try:
            st.session_state.provider = make_provider(provider_name)
            st.session_state.provider_name = provider_name
        except Exception as e:
            st.error(f"Provider init failed: {e}")
            st.stop()

    st.divider()
    st.markdown("### Session")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Clear chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.history = []
            st.session_state.transcript_turns = []
            st.rerun()
    with col2:
        has_turns = bool(st.session_state.get("transcript_turns"))
        if st.button("New session", use_container_width=True, disabled=not has_turns):
            st.session_state.messages = []
            st.session_state.history = []
            st.session_state.transcript_turns = []
            st.rerun()

    if st.session_state.get("transcript_turns"):
        st.divider()
        st.markdown("### Transcript")
        transcript = {
            **artifact_version_dict(artifact_version),
            "provider": provider_name,
            "model": model or "default",
            "turns": st.session_state.transcript_turns,
            "created_at": now_iso(),
        }
        transcript_json = json.dumps(transcript, ensure_ascii=False, indent=2, default=str)
        st.download_button(
            "Download transcript",
            data=transcript_json,
            file_name=f"transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )
        col_a, col_b = st.columns(2)
        col_a.metric("Turns", len(st.session_state.transcript_turns))
        col_b.metric("Tools called", sum(
            1 for t in st.session_state.transcript_turns
            for r in t.get("rounds", [])
            if r.get("tool_calls")
        ))

    st.divider()
    st.caption(f"Artifacts: system_prompt.md / tools.yaml @ {version}")

# --- Header ---
st.markdown('<div class="main-header">Research Agent</div>', unsafe_allow_html=True)

# --- Tool count summary ---
enabled = [t["name"] for t in tool_declarations]
with st.expander(f"Available tools ({len(enabled)})"):
    cols = st.columns(4)
    for i, name in enumerate(enabled):
        cols[i % 4].code(name, language=None)

# --- Chat area ---
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "tools_used" in msg and msg["tools_used"]:
            with st.expander("Tool execution details"):
                for t in msg["tools_used"]:
                    render_tool_call(t)

# --- Chat input ---
if user_input := st.chat_input("Type your request..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    trim_window = 5
    history_msgs = st.session_state.history[-trim_window * 2:]
    model_messages = [
        {"role": "system", "content": system_prompt},
        *history_msgs,
        {"role": "user", "content": user_input},
    ]

    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            try:
                result = run_model_tool_loop(
                    provider=st.session_state.provider,
                    messages=model_messages,
                    tools=openai_tools,
                    model=model or None,
                    max_tool_rounds=max_rounds,
                )
                assistant_text = result["assistant_text"]
                tools_used = []
                for r in result.get("rounds", []):
                    for i, tc in enumerate(r.get("tool_calls", [])):
                        tr = r["tool_results"][i]["result"] if i < len(r["tool_results"]) else {}
                        tools_used.append({"name": tc["name"], "args": tc["args"], "result": tr})

                st.markdown(assistant_text)
                if tools_used:
                    with st.expander("Tool execution details"):
                        for t in tools_used:
                            render_tool_call(t)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": assistant_text,
                    "tools_used": tools_used,
                })
                st.session_state.history.append({"role": "user", "content": user_input})
                st.session_state.history.append({"role": "assistant", "content": assistant_text})

                turn = {
                    "turn_index": len(st.session_state.transcript_turns) + 1,
                    "started_at": now_iso(),
                    "user": user_input,
                    "status": result.get("status", "answered"),
                    "assistant_text": assistant_text,
                    "rounds": result.get("rounds", []),
                    "tool_events": result.get("tool_events", []),
                }
                st.session_state.transcript_turns.append(turn)

            except Exception as e:
                st.error(f"Error: {e}")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"Error: {e}",
                    "tools_used": [],
                })

st.markdown("</div>", unsafe_allow_html=True)
