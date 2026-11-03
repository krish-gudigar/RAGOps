"""RouteWise web page. Talks to the FastAPI backend.

Run from the project root (with the API already running):
    streamlit run frontend/streamlit_app.py
"""

import requests
import streamlit as st

st.set_page_config(page_title="RouteWise", layout="wide")

# ---------- sidebar ----------
st.sidebar.title("RouteWise")
api = st.sidebar.text_input("API address", "http://127.0.0.1:8000").rstrip("/")
strategy = st.sidebar.selectbox("Strategy", ["dynamic", "always_small", "always_strong"])
validate = st.sidebar.checkbox("Validate answers", value=True)
escalate = st.sidebar.checkbox("Escalate on failure", value=True)
max_esc = st.sidebar.slider("Max escalations", 0, 2, 2)
st.sidebar.caption(
    "Experimental educational prototype. Validation does not prove factual "
    "correctness, and costs are estimates from configured prices."
)


# ---------- helpers ----------
def call(method: str, path: str, payload: dict | None = None):
    """Call the API. Shows a friendly error and returns None on failure."""
    try:
        r = requests.request(method, api + path, json=payload, timeout=900)
    except requests.ConnectionError:
        st.error("Cannot reach the API. Start it with: "
                 "uvicorn app.main:app --app-dir backend")
        return None
    if r.status_code != 200:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        st.error(f"API error {r.status_code}: {detail}")
        return None
    return r.json()


def show_analysis(analysis: dict, decision: dict):
    st.subheader("Why this model?")
    st.info(decision["reason"])
    cols = st.columns(5)
    for col, (label, key) in zip(cols, [
        ("Complexity", "complexity_score"), ("Reasoning", "reasoning_score"),
        ("Context", "context_score"), ("Constraints", "constraints_score"),
        ("Reliability", "reliability_score"),
    ]):
        col.metric(label, f"{analysis[key]}/2")
    st.progress(min(analysis["total_score"] / 10, 1.0),
                text=f"Total score {analysis['total_score']}/10 "
                     f"({analysis['difficulty']} difficulty) | "
                     f"type: {analysis['task_type']} | "
                     f"selected tier: {decision['selected_tier']}")
    if analysis.get("detected_signals"):
        st.caption("Signals: " + "; ".join(analysis["detected_signals"]))


def show_execution(body: dict):
    result = body["result"]
    show_analysis(result["analysis"], result["decision"])

    st.subheader("Execution timeline")
    for step in body["timeline"]:
        st.write("•", step)
    for reason in body["escalation_reasons"]:
        st.warning(reason)

    st.subheader("Answer")
    st.write(result["final_response"])

    last = result["attempts"][-1]
    validation = last.get("validation")
    if validation is None:
        status = "validation off"
    else:
        status = "passed validation" if validation.get("valid") else "FAILED validation"
    st.caption(
        f"{result['final_tier']} tier | {result['total_latency_ms'] / 1000:.1f} s | "
        f"estimated cost ${result['total_estimated_cost']:.6f} | {status} | "
        f"attempts: {len(result['attempts'])}"
    )
    with st.expander("Raw result (JSON)"):
        st.json(result)


# ---------- tabs ----------
tab_run, tab_compare, tab_history = st.tabs(["Run", "Compare", "History & metrics"])

with tab_run:
    task = st.text_area("Task", height=120, key="run_task",
                        placeholder="e.g. Write a Python function that reverses a string.")
    left, right = st.columns(2)
    preview = left.button("Preview routing (no model call)")
    run = right.button("Run task", type="primary")

    if (preview or run) and not task.strip():
        st.warning("Type a task first.")
    elif preview:
        body = call("POST", "/api/analyze", {"task": task, "strategy": strategy})
        if body:
            show_analysis(body["analysis"], body["decision"])
    elif run:
        with st.spinner("Running... the first call to a local model can be slow."):
            body = call("POST", "/api/execute", {
                "task": task, "strategy": strategy,
                "enable_validation": validate,
                "enable_escalation": escalate,
                "max_escalations": max_esc,
            })
        if body:
            show_execution(body)

with tab_compare:
    st.write("Runs ONE task through always-small, always-strong and dynamic routing. "
             "Not saved to history. With a local model this can take minutes.")
    ctask = st.text_area("Task to compare", height=120, key="cmp_task")
    if st.button("Compare strategies", type="primary"):
        if not ctask.strip():
            st.warning("Type a task first.")
        else:
            with st.spinner("Running three strategies..."):
                body = call("POST", "/api/compare", {
                    "task": ctask,
                    "enable_validation": validate,
                    "enable_escalation": escalate,
                    "max_escalations": max_esc,
                })
            if body:
                rows = [{
                    "strategy": r["strategy"],
                    "final tier": r["final_tier"],
                    "model": r["final_model"],
                    "success": r["success"],
                    "validated": r["validated"],
                    "latency (s)": round(r["latency_ms"] / 1000, 1),
                    "est. cost ($)": round(r["estimated_cost"], 6),
                    "attempts": r["attempts"],
                    "escalations": r["escalations"],
                } for r in body["summary"]]
                st.dataframe(rows, use_container_width=True)
                for note in body["notes"]:
                    st.caption("• " + note)
                for name, response in body["results"].items():
                    with st.expander(f"Answer and details: {name}"):
                        show_execution(response)

with tab_history:
    if st.button("Refresh"):
        st.rerun()
    metrics = call("GET", "/api/metrics")
    if metrics:
        o = metrics["overall"]
        if o["total_tasks"] == 0:
            st.write("No runs saved yet. Run a task first.")
        else:
            c = st.columns(4)
            c[0].metric("Runs", o["total_tasks"])
            rate = o["success_rate"]
            c[1].metric("Observed success", f"{rate:.0%}" if rate is not None else "n/a")
            c[2].metric("Escalation rate", f"{o['escalation_rate']:.0%}")
            c[3].metric("Avg latency", f"{o['average_latency_ms'] / 1000:.1f} s")
            st.caption(metrics["note"])
            st.write("By strategy")
            st.dataframe([{"strategy": k, **{
                "runs": v["total_tasks"],
                "escalation rate": f"{v['escalation_rate']:.0%}",
                "avg cost ($)": round(v["average_estimated_cost"], 6),
            }} for k, v in metrics["by_strategy"].items()], use_container_width=True)
    history = call("GET", "/api/history?limit=20")
    if history:
        st.write("Recent runs")
        st.dataframe([{
            "time": h["timestamp"],
            "strategy": h["result"]["strategy"],
            "final tier": h["result"]["final_tier"],
            "success": h["result"]["success"],
            "task": h["result"]["task"][:80],
        } for h in history], use_container_width=True)