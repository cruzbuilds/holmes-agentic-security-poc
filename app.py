"""Holmes — Security Investigation POC (Streamlit UI)."""

import asyncio
import json
import os
import time

import streamlit as st

import agent as holmes

st.set_page_config(page_title="Holmes", page_icon="🔎", layout="centered")
st.title("🔎 HOLMES — Security Investigation POC")
st.error("**SYNTHETIC DATA / SIMULATION ONLY / NO ACTIONS EXECUTED**")


@st.cache_resource
def mcp_client():
    return holmes.start_mcp_client()


ss = st.session_state
ss.setdefault("result", None)
ss.setdefault("tools", [])
ss.setdefault("chat", [])
ANALYST_MIN = int(os.getenv("HOLMES_ANALYST_MINUTES", "30"))  # est. manual triage time for comparison

SAMPLES = {p.stem.replace("event", "Event "): p for p in sorted((holmes.ROOT / "data" / "incidents").glob("*.json"))}

upload = st.file_uploader("Drop a synthetic incident JSON", type="json")
sample = st.radio("…or pick a sample", list(SAMPLES), horizontal=True, index=None, disabled=upload is not None)

raw = upload.getvalue() if upload else SAMPLES[sample].read_bytes() if sample else None
incident = None
if raw:
    try:
        incident = json.loads(raw)  # parsed as inert data only
        assert isinstance(incident, dict) and incident.get("simulation") is True
    except Exception:
        st.warning('Not a valid synthetic incident (must be a JSON object with "simulation": true).')
        incident = None
    if incident:
        with st.expander(f"Incident {incident.get('incident_id', '')} — raw evidence"):
            st.json(incident)

if st.button("Analyze", type="primary", disabled=incident is None):
    ss.agent = holmes.new_agent(mcp_client())
    ss.result, ss.tools, ss.chat = None, [], []

    async def run(status):
        async for kind, *data in holmes.investigate(ss.agent, incident):
            if kind == "tool_call":
                tool_id, name, args, why = data
                ss.tools.append({"id": tool_id, "tool": name, "input": args, "why": why, "result": None})
                if why:
                    status.markdown(f"💭 {why}")
                status.write(f"🔧 **{name}**(`{json.dumps(args)}`)")
            elif kind == "tool_result":
                tool_id, text = data
                for t in ss.tools:
                    if t["id"] == tool_id:
                        t["result"] = text
            elif kind == "done":
                ss.result, ss.cost = data

    with st.status("Holmes is investigating…", expanded=True) as status:
        status.write("🧠 Reviewing evidence with Claude (Bedrock)…")
        start = time.time()
        asyncio.run(run(status))
        ss.secs = time.time() - start
        status.update(label=f"Investigation complete — {len(ss.tools)} tool call(s)", state="complete", expanded=False)

r = ss.result
if r:
    color = {"benign": "green", "suspicious": "orange", "malicious": "red"}[r.verdict]
    st.header(f":{color}[{r.verdict.upper()}] · confidence {r.confidence}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("⏱️ Holmes", f"{ss.secs:.0f}s")
    c2.metric("🔧 Lookups", len(ss.tools))
    c3.metric("💰 Est. cost", f"${ss.cost:.2f}")
    c4.metric("🧑‍💻 Analyst (est.)", f"~{ANALYST_MIN} min")
    st.write(r.summary)

    with st.expander(f"🔧 Tool activity ({len(ss.tools)} local MCP lookups)"):
        for t in ss.tools:
            if t["why"]:
                st.markdown(f"💭 {t['why']}")
            st.markdown(f"**{t['tool']}** `{json.dumps(t['input'])}`")
            st.code(t["result"] or "", language="json")

    st.subheader("Evidence (observed)")
    st.markdown("\n".join(f"- {e}" for e in r.evidence))
    st.subheader("Tool findings")
    st.markdown("\n".join(f"- {e}" for e in r.tool_findings) or "_No tools needed._")
    if r.attack_pattern:
        st.subheader("Attack pattern (inferred)")
        st.markdown("\n".join(f"- {e}" for e in r.attack_pattern))

    st.subheader("Proposed actions")
    st.warning("**SIMULATION ONLY — NOT EXECUTED.** Holmes proposes; a human or policy engine decides.")
    for a in r.recommended_actions:
        icon = {"high": "🔴", "medium": "🟠", "low": "🟢"}[a.priority]
        st.markdown(f"{icon} **{a.action}** — _{a.priority}_  \n{a.reason}  \n`SIMULATION ONLY — NOT EXECUTED`")

    if r.limitations:
        st.subheader("Limitations")
        st.markdown("\n".join(f"- {e}" for e in r.limitations))

    st.divider()
    st.subheader("💬 Ask Holmes")
    for role, text in ss.chat:
        st.chat_message(role).write(text)
    quick = ["Why this verdict?", "What evidence mattered most?", "How do we prevent this next time?", "If you had response tools, what would you do?"]
    q = None
    for col, question in zip(st.columns(len(quick)), quick):
        if col.button(question, use_container_width=True):
            q = question
    if typed := st.chat_input("e.g. Why did you classify it this way?"):
        q = typed
    if q:
        st.chat_message("user").write(q)
        with st.spinner("Holmes is thinking…"):
            answer = holmes.ask(ss.agent, q)
        st.chat_message("assistant").write(answer)
        ss.chat += [("user", q), ("assistant", answer)]
