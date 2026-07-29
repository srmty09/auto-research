import json
import sys
import os
import time
from datetime import datetime

import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from src.agent import Agent
from src.config import GROQ_MODEL
from src.session_store import SessionStore

st.set_page_config(page_title="Auto Research Agent", layout="wide")

store = SessionStore()

if "result" not in st.session_state:
    st.session_state.result = None
if "running" not in st.session_state:
    st.session_state.running = False
if "viewing_session" not in st.session_state:
    st.session_state.viewing_session = None
if "memory" not in st.session_state:
    st.session_state.memory = None
if "user" not in st.session_state:
    st.session_state.user = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

with st.sidebar:
    st.markdown("### User")
    user = st.text_input("Username", value=st.session_state.user or "default", key="user_input")
    st.session_state.user = user

    st.divider()

    st.markdown("### Configuration")
    st.text_input("Model", value=GROQ_MODEL, key="config_model")
    st.slider("Max Steps", min_value=5, max_value=30, value=15, key="config_steps")
    st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.7, step=0.1, key="config_temp")

    st.divider()

    st.markdown("### Past Sessions")
    sessions = store.list_sessions(limit=30, user=st.session_state.user)

    if sessions:
        for s in sessions:
            short = s["goal"][:55] + "..." if len(s["goal"]) > 55 else s["goal"]
            status = "OK" if s["success"] else "FAIL"
            label = f"[{status}] {short}"
            if st.button(label, key=f"sid_{s['id']}", use_container_width=True):
                full = store.get_session(s["id"])
                if full:
                    full["session_id"] = full["id"]
                    st.session_state.result = full
                    st.session_state.viewing_session = s["id"]
                    st.session_state.memory = None
                    st.session_state.chat_history = []
                    st.rerun()

        st.divider()

        col_new, col_clear = st.columns(2)
        with col_new:
            if st.button("New", use_container_width=True):
                st.session_state.result = None
                st.session_state.viewing_session = None
                st.session_state.memory = None
                st.session_state.chat_history = []
                st.rerun()
        with col_clear:
            if st.button("Clear All", use_container_width=True):
                store.clear_all()
                st.session_state.result = None
                st.session_state.viewing_session = None
                st.session_state.memory = None
                st.session_state.chat_history = []
                st.rerun()
    else:
        st.markdown("No past sessions.")

if st.session_state.viewing_session:
    sess = store.get_session(st.session_state.viewing_session)
    current_goal = sess["goal"] if sess else ""
else:
    current_goal = ""

st.title("Autonomous Research & Task Agent")
st.markdown(
    "Provide a high-level goal. The agent will plan, research, execute code, "
    "and deliver a structured report."
)

goal = st.text_area(
    "Goal",
    value=current_goal,
    height=150,
    placeholder="e.g. Research competitor pricing for product X and summarize into a report",
    disabled=st.session_state.running,
)

col1, col2 = st.columns([1, 5])
with col1:
    run = st.button("Run Agent", type="primary", disabled=st.session_state.running or not goal)

# --- New run ---
if run and goal:
    st.session_state.running = True
    st.session_state.result = None
    st.session_state.viewing_session = None
    st.session_state.memory = None
    st.session_state.chat_history = [{"role": "user", "content": goal}]

    status_container = st.status("Agent is working...", expanded=True)
    step_log = status_container.empty()

    agent = Agent()
    start = time.time()

    def on_step(step_info):
        tool = step_info.get("tool") or "thinking"
        thought = (step_info.get("thought") or "")[:120]
        step_log.markdown(f"**Step {step_info['step']}** — `{tool}`  \n{thought}")

    result = agent.run(goal, max_steps=st.session_state.config_steps, step_callback=on_step)
    elapsed = time.time() - start

    status_container.update(
        label=f"Completed in {elapsed:.1f}s — {result['steps']} steps",
        state="complete" if result["success"] else "error",
    )

    session_id = store.add_session(
        {
            "goal": goal,
            "success": result["success"],
            "steps": result["steps"],
            "time": round(elapsed, 2),
            "timestamp": datetime.now().isoformat(),
            "final_answer": result["final_answer"],
            "log": result["log"],
        },
        user=st.session_state.user,
    )
    result["session_id"] = session_id

    st.session_state.result = result
    st.session_state.memory = agent._last_memory
    st.session_state.chat_history.append({"role": "assistant", "content": result["final_answer"]})
    st.session_state.running = False
    st.rerun()

# --- Display results ---
if st.session_state.result:
    result = st.session_state.result
    session_id = result.get("session_id", None)
    is_historical = st.session_state.viewing_session is not None

    if is_historical:
        st.info("Viewing a past session.")

    tab1, tab2, tab3 = st.tabs(["Final Answer", "Reasoning Trace", "Summary"])

    with tab1:
        st.markdown(result["final_answer"])
        st.download_button(
            label="Download Report",
            data=result["final_answer"],
            file_name=f"report_{goal.strip()[:30].replace(' ', '_').replace('/', '_')}.md",
            mime="text/markdown",
        )

    with tab2:
        for step in result["log"]:
            label = f"Step {step['step']}: {step['tool'] or 'Final Answer'}"
            with st.expander(label, expanded=False):
                if step.get("thought"):
                    st.markdown(f"**Thought:**\n\n{step['thought']}")
                if step.get("tool"):
                    st.markdown(f"**Tool:** `{step['tool']}`")
                    st.markdown("**Input:**")
                    st.code(
                        json.dumps(step["input"], indent=2) if step["input"] else "N/A",
                        language="json",
                    )
                    st.markdown("**Output:**")
                    st.text((step["output"] or "N/A")[:2000])

    with tab3:
        tool_calls = sum(1 for s in result["log"] if s.get("tool"))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Steps", result["steps"])
        c2.metric("Tool Calls", tool_calls)
        c3.metric("Status", "Success" if result["success"] else "Failed")

        if session_id:
            s = store.get_session(session_id)
            if s:
                c4.metric("Time", f"{s['time']}s")

        if session_id:
            st.caption(f"Session: `{session_id}`")

        error_steps = [s for s in result["log"] if "error" in (s.get("output") or "").lower()]
        if error_steps:
            st.markdown("**Errors recovered:**")
            for s in error_steps:
                st.text(f"Step {s['step']} ({s['tool']}): {s['output'][:200]}")

    # --- Follow-up chat ---
    if not is_historical and st.session_state.memory and not st.session_state.running:
        st.divider()
        st.markdown("### Continue Conversation")
        follow_up = st.chat_input("Ask a follow-up question...")
        if follow_up:
            memory = st.session_state.memory
            st.session_state.chat_history.append({"role": "user", "content": follow_up})

            status_container = st.status("Agent is thinking...", expanded=True)
            step_log = status_container.empty()

            agent = Agent()

            def on_followup_step(step_info):
                tool = step_info.get("tool") or "thinking"
                thought = (step_info.get("thought") or "")[:120]
                step_log.markdown(f"**Step {step_info['step']}** — `{tool}`  \n{thought}")

            new_result = agent.continue_run(
                memory,
                follow_up,
                max_steps=st.session_state.config_steps,
                step_callback=on_followup_step,
            )

            status_container.update(
                label=f"Completed — {new_result['steps']} total steps",
                state="complete" if new_result["success"] else "error",
            )

            new_result["session_id"] = session_id
            st.session_state.result = new_result
            st.session_state.memory = memory
            st.session_state.chat_history.append({"role": "assistant", "content": new_result["final_answer"]})

            if session_id:
                sess = store.get_session(session_id)
                if sess:
                    sess["final_answer"] = new_result["final_answer"]
                    sess["log"] = new_result["log"]
                    sess["steps"] = new_result["steps"]
                    store._save()

            st.rerun()
else:
    st.info("Enter a goal above and click **Run Agent** to start.")
