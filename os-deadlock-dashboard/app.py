"""AI-Assisted Dashboard Development and Deadlock Analysis (Streamlit).

UI only. All algorithms live in algorithms/ and simulation/, and the Test Bench calls the
same functions the dashboard uses.
"""
import math
import time
from copy import deepcopy

import pandas as pd
import streamlit as st

import testbench
from algorithms.bankers import (ValidationError, calculate_need, request_resources,
                                safety_algorithm, validate_state)
from algorithms.deadlock import detect_deadlock, find_wait_for_cycle
from algorithms.prevention import request_all_or_nothing, validate_resource_order
from simulation import engine
from simulation.scenarios import SIM_SCENARIOS, get_bankers_sample
from ui_graphs import STATUS_COLOR, rag_figure

st.set_page_config(page_title="OS Deadlock Lab", page_icon=":material/memory:", layout="wide")

PAGES = ["Overview", "Banker's Algorithm", "Deadlock Lab", "Prevention", "Test Bench",
         "AI Usage Record"]
PAGE_HELP = {
    "Overview": "Project summary and the live status of the current scenarios.",
    "Banker's Algorithm": "Deadlock AVOIDANCE: safety check and resource requests.",
    "Deadlock Lab": "Watch a deadlock form, be detected, and be recovered.",
    "Prevention": "Break a necessary condition so deadlock cannot occur.",
    "Test Bench": "Run real checks against the project's algorithms.",
    "AI Usage Record": "How AI was used and what was verified.",
}

st.markdown("""
<style>
.os-badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:0.8rem;
font-weight:600;border:1px solid transparent}
.os-green{background:#052e1a;color:#4ade80;border-color:#166534}
.os-amber{background:#3a2a05;color:#fbbf24;border-color:#92400e}
.os-red{background:#3b0d0d;color:#f87171;border-color:#991b1b}
.os-blue{background:#0b2447;color:#60a5fa;border-color:#1e40af}
.os-gray{background:#1f2937;color:#9ca3af;border-color:#374151}
</style>
""", unsafe_allow_html=True)


def badge(text, kind):
    return f'<span class="os-badge os-{kind}">{text}</span>'


ss = st.session_state

# ------------------------------------------------------------------ session init
if "bk" not in ss:
    ss.bk = get_bankers_sample()
    ss.bk_ver = 0
    ss.bk_n, ss.bk_m = 5, 3
    ss.bk_current = None
    ss.bk_req = None
if "sim" not in ss:
    ss.sim_key = "one_resource"
    ss.sim = engine.new_state("one_resource")
    ss.sim_msg = None
    ss.playing = False
if "tb" not in ss:
    ss.tb = {}
if "page" not in ss:
    ss.page = "Overview"


def go(page):
    ss.page = page


# ------------------------------------------------------------------ helpers
def rc(m):
    return [f"R{j + 1}" for j in range(m)]


def pc(n):
    return [f"P{i + 1}" for i in range(n)]


def matrix_df(mat, n=None, m=None):
    n = n or len(mat)
    m = m or (len(mat[0]) if mat else 0)
    return pd.DataFrame(mat, index=pc(n), columns=rc(m))


def vec_df(vec, label="Available"):
    return pd.DataFrame([vec], index=[label], columns=rc(len(vec)))


def df_to_matrix(df, label):
    errs, out = [], []
    for idx, row in df.iterrows():
        r = []
        for col, v in zip(df.columns, row.tolist()):
            if pd.isna(v):
                errs.append(f"{label}[{idx}][{col}] is empty. Enter a whole number (0 or more).")
                r.append(0)
            elif float(v) != int(float(v)):
                errs.append(f"{label}[{idx}][{col}] = {v} is not a whole number.")
                r.append(0)
            else:
                r.append(int(v))
        out.append(r)
    return out, errs


def sig(state):
    return repr((state["available"], state["allocation"], state["maximum"]))


def resize_bk(bk, n, m):
    def fit(row):
        return (list(row) + [0] * m)[:m]
    zeros = [0] * m
    alloc = [fit(r) for r in bk["allocation"][:n]] + [list(zeros) for _ in range(max(0, n - len(bk["allocation"])))]
    mx = [fit(r) for r in bk["maximum"][:n]] + [list(zeros) for _ in range(max(0, n - len(bk["maximum"])))]
    return {"available": fit(bk["available"]), "allocation": alloc, "maximum": mx}


def style_status(df, col="State"):
    def color(v):
        c = STATUS_COLOR.get(v)
        return f"background-color:{c}33;color:{c};font-weight:600" if c else ""
    return df.style.map(color, subset=[col])


def sim_status(sim):
    det = engine.live_detection(sim)
    st_ = sim["status"]
    if det["has_deadlock"]:
        names = ", ".join(sim["processes"][i] for i in det["deadlocked"])
        return "Deadlocked", "red", f"Deadlock exists among {names}."
    if any(s in engine.ACTIVE_WAIT for s in st_):
        return "Waiting (no deadlock)", "amber", "Some processes wait, but all can eventually finish."
    if all(s in (engine.COMPLETED, engine.TERMINATED) for s in st_):
        return "Finished", "green", "Every process has completed or been terminated."
    if all(s == engine.READY for s in st_):
        return "Not started", "gray", "No resources have been requested yet."
    return "Running", "blue", "Processes are running and nothing is waiting."


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("### OS Deadlock Lab")
    st.caption("AI-Assisted Dashboard Development and Deadlock Analysis")
    st.radio("Navigate", PAGES, key="page", label_visibility="collapsed")
    st.info(PAGE_HELP[ss.page])
    st.caption("Every result shown is computed by the real algorithms at run time.")

if ss.page != "Deadlock Lab":
    ss.playing = False


# ------------------------------------------------------------------ OVERVIEW
def page_overview():
    st.header("Overview")
    st.write("An **operating system** shares finite resources (memory, files, devices) among "
             "processes. A **deadlock** happens when a set of processes each hold a resource "
             "and wait for one held by another, so none can ever proceed. This dashboard "
             "shows how to **avoid** (Banker's algorithm), **prevent**, **detect** and "
             "**recover** from deadlocks, and checks the algorithms with a Test Bench.")

    bk = ss.bk_current or ss.bk
    errs = validate_state(bk["available"], bk["allocation"], bk["maximum"])
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.subheader("Banker's scenario")
            if errs:
                st.warning("The current Banker's input is invalid: " + " ".join(errs))
            else:
                res = safety_algorithm(bk["available"], bk["allocation"], bk["maximum"])
                a, b, c = st.columns(3)
                a.metric("Processes", len(bk["allocation"]))
                b.metric("Resource types", len(bk["available"]))
                c.metric("Available", str(bk["available"]))
                if res["safe"]:
                    st.markdown(badge("SAFE", "green") + " &nbsp; sequence "
                                + " → ".join(f"P{i + 1}" for i in res["safe_sequence"]),
                                unsafe_allow_html=True)
                else:
                    st.markdown(badge("UNSAFE", "red") + " &nbsp; no safe sequence exists",
                                unsafe_allow_html=True)
    sim = ss.sim
    label, kind, why = sim_status(sim)
    with c2:
        with st.container(border=True):
            st.subheader("Deadlock Lab scenario")
            st.caption(sim["name"])
            a, b, c = st.columns(3)
            a.metric("Processes", len(sim["processes"]))
            b.metric("Resource types", len(sim["resources"]))
            c.metric("Available", str(sim["available"]))
            st.markdown(badge(label.upper(), kind) + f" &nbsp; {why}", unsafe_allow_html=True)

    st.subheader("Current resource-allocation graph")
    fig = rag_figure(sim["processes"], sim["resources"], sim["total"], sim["available"],
                     sim["allocation"], sim["request"], sim["status"])
    fig.update_layout(height=340)
    st.plotly_chart(fig, width="stretch")
    st.caption("Drawn from the Deadlock Lab's live state. Go to the Deadlock Lab to change it.")

    st.subheader("Go to")
    cols = st.columns(4)
    for col, target in zip(cols, ["Banker's Algorithm", "Deadlock Lab", "Prevention", "Test Bench"]):
        col.button(target, key=f"nav_{target}", on_click=go, args=(target,), width="stretch")


# ------------------------------------------------------------------ BANKER'S
def _commit_request(res, process):
    ss.bk = {"available": res["new_available"], "allocation": res["new_allocation"],
             "maximum": ss.bk_current["maximum"]}
    ss.bk_ver += 1
    ss.bk_req = None


def _reset_sample():
    ss.bk = get_bankers_sample()
    ss.bk_n, ss.bk_m = 5, 3
    ss.bk_ver += 1
    ss.bk_req = None


def page_bankers():
    st.header("Banker's Algorithm")
    st.caption("Deadlock avoidance: grant a request only if the system stays in a safe state. "
               "Need = Maximum − Allocation.")
    top = st.columns([1, 1, 2])
    top[0].number_input("Processes", 1, 10, key="bk_n", step=1)
    top[1].number_input("Resource types", 1, 6, key="bk_m", step=1)
    top[2].button("Reset to sample scenario", on_click=_reset_sample)
    n, m = int(ss.bk_n), int(ss.bk_m)
    if len(ss.bk["allocation"]) != n or len(ss.bk["available"]) != m:
        ss.bk = resize_bk(ss.bk, n, m)
        ss.bk_ver += 1
        ss.bk_req = None
    v = ss.bk_ver
    cfg = {c: st.column_config.NumberColumn(c, step=1) for c in rc(m)}
    st.markdown("**Edit the state** (double-click a cell). Sample = classic textbook example.")
    av_df = st.data_editor(vec_df(ss.bk["available"]), key=f"av_{v}_{n}_{m}",
                           column_config=cfg, width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("Allocation (currently held)")
        al_df = st.data_editor(matrix_df(ss.bk["allocation"], n, m), key=f"al_{v}_{n}_{m}",
                               column_config=cfg, width="stretch")
    with c2:
        st.markdown("Maximum (declared worst case)")
        mx_df = st.data_editor(matrix_df(ss.bk["maximum"], n, m), key=f"mx_{v}_{n}_{m}",
                               column_config=cfg, width="stretch")
    available, e1 = df_to_matrix(av_df, "Available")
    allocation, e2 = df_to_matrix(al_df, "Allocation")
    maximum, e3 = df_to_matrix(mx_df, "Maximum")
    errs = e1 + e2 + e3
    if not errs:
        errs = validate_state(available[0], allocation, maximum)
    if errs:
        ss.bk_current = None
        for e in errs:
            st.error(e)
        st.info("Fix the highlighted values above. Allocation must not exceed Maximum, and every "
                "value must be a whole number of 0 or more.")
        return
    state = {"available": available[0], "allocation": allocation, "maximum": maximum}
    ss.bk_current = state
    res = safety_algorithm(state["available"], state["allocation"], state["maximum"])

    st.subheader("Result")
    if res["safe"]:
        st.success("SAFE state. Safe sequence: "
                   + " → ".join(f"P{i + 1}" for i in res["safe_sequence"]))
    else:
        st.error("UNSAFE state. No safe sequence exists.")
    st.write(res["explanation"])
    t1, t2, t3 = st.columns(3)
    t1.markdown("Allocation")
    t1.dataframe(matrix_df(allocation, n, m), width="stretch")
    t2.markdown("Maximum")
    t2.dataframe(matrix_df(maximum, n, m), width="stretch")
    t3.markdown("Need = Maximum − Allocation")
    t3.dataframe(matrix_df(res["need"], n, m), width="stretch")

    st.subheader("Safety algorithm, step by step")
    rows = []
    for s in res["steps"]:
        rows.append({"Step": s["step"],
                     "Process": "-" if s["process"] is None else f"P{s['process'] + 1}",
                     "Work before": str(s["work_before"]), "Work after": str(s["work_after"]),
                     "Finish": " ".join("T" if f else "F" for f in s["finish"]),
                     "What happened": s["note"]})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if not res["safe"]:
        st.warning("Unsafe is not the same as deadlocked: no process is necessarily waiting yet. "
                   "It means deadlock is possible if processes request their maximum.")

    st.subheader("Request resources")
    with st.form("req_form"):
        f1, f2 = st.columns([1, 3])
        proc = f1.selectbox("Process", list(range(n)), format_func=lambda i: f"P{i + 1}")
        vec_cols = f2.columns(m)
        vec = [vec_cols[j].number_input(f"R{j + 1}", value=0, step=1, key=f"rq_{j}")
               for j in range(m)]
        submitted = st.form_submit_button("Check request")
    if submitted:
        ss.bk_req = {"sig": sig(state), "p": proc, "vec": vec,
                     "res": request_resources(state["available"], state["allocation"],
                                              state["maximum"], proc, vec)}
    r = ss.bk_req
    if r and r["sig"] == sig(state):
        out = r["res"]
        text = f"P{r['p'] + 1} requests {r['vec']}. " + out["message"]
        if out["status"] == "granted":
            st.success(text)
        elif out["status"] == "waiting":
            st.warning(text)
        else:
            st.error(text)
        if out["safety"]:
            with st.expander("Safety check on the provisional state"):
                st.write(out["safety"]["explanation"])
                st.dataframe(pd.DataFrame([{
                    "Step": s["step"], "Work after": str(s["work_after"]), "Note": s["note"]}
                    for s in out["safety"]["steps"]]), hide_index=True, width="stretch")
        if out["granted"]:
            st.button("Commit this grant to the tables", on_click=_commit_request,
                      args=(out, r["p"]))
        else:
            st.caption("The tables above are unchanged (the provisional change was rolled back).")


# ------------------------------------------------------------------ DEADLOCK LAB
def _set_msg(kind, text):
    ss.sim_msg = (kind, text)


def cb_reset():
    ss.sim = engine.new_state(ss.sim_key)
    ss.playing = False
    _set_msg("info", "Scenario reset to its exact initial state.")


def cb_scenario():
    ss.sim_key = ss.sim_pick
    cb_reset()


def cb_start():
    ss.playing = True
    _set_msg("info", "Simulation running. Press Pause to stop.")


def cb_pause():
    ss.playing = False
    _set_msg("info", "Paused.")


def cb_step():
    ss.playing = False
    s, ok, msg = engine.step(ss.sim)
    ss.sim = s
    _set_msg("info" if ok else "warning", msg)


def cb_run():
    ss.playing = False
    s, msg = engine.run_to_deadlock(ss.sim)
    ss.sim = s
    _set_msg("warning" if "Deadlock" in msg else "info", msg)


def cb_detect():
    ss.playing = False
    s, msg = engine.detect(ss.sim)
    ss.sim = s
    _set_msg("error" if "detected" in msg and "No" not in msg else "success", msg)


def cb_recover():
    ss.playing = False
    mode = "all" if ss.rec_mode.startswith("Terminate all") else "one"
    s, msg = engine.recover(ss.sim, mode, ss.get("rec_victim"))
    ss.sim = s
    _set_msg("success" if "recovered" in msg else "warning", msg)


def page_lab():
    sim = ss.sim
    st.header("Deadlock Lab")
    keys = list(SIM_SCENARIOS)
    st.selectbox("Scenario", keys, index=keys.index(ss.sim_key), key="sim_pick",
                 format_func=lambda k: SIM_SCENARIOS[k]["name"], on_change=cb_scenario)
    st.caption(sim["description"])

    # stage timeline
    det = sim["detection"]
    stage = 0
    if sim["event_index"] > 0:
        stage = 1
    if any(s in engine.ACTIVE_WAIT for s in sim["status"]):
        stage = 2
    if det:
        stage = 3
    if sim["recovered"]:
        stage = 4
    names = ["1 Allocation", "2 Requests", "3 Waiting", "4 Detection", "5 Recovery"]
    st.markdown(" → ".join(f"**:blue[{x}]**" if i == stage else (x if i > stage else f"~~{x}~~")
                               for i, x in enumerate(names)))
    st.progress(min(sim["event_index"] / len(sim["events"]), 1.0),
                text=f"Scripted requests applied: {sim['event_index']} of {len(sim['events'])}")

    # controls
    live = engine.live_detection(sim)
    done = (sim["event_index"] >= len(sim["events"]) and
            not any(s in (engine.RUNNING,) + engine.ACTIVE_WAIT for s in sim["status"]))
    b = st.columns(4)
    b[0].button("Reset Scenario", on_click=cb_reset, width="stretch")
    b[1].button("Start Simulation", on_click=cb_start, disabled=done or ss.playing, width="stretch")
    b[2].button("Pause Simulation", on_click=cb_pause, disabled=not ss.playing, width="stretch")
    b[3].button("Next Step", on_click=cb_step, disabled=done, width="stretch")
    b2 = st.columns(4)
    b2[0].button("Run to Deadlock", on_click=cb_run, disabled=done, width="stretch",
                 help="Applies steps until a real deadlock exists in the state.")
    b2[1].button("Detect Deadlock", on_click=cb_detect, width="stretch")
    can_rec = live["has_deadlock"]
    b2[2].radio("Recovery method", ["Terminate selected process", "Terminate all deadlocked processes"],
                key="rec_mode", label_visibility="collapsed", disabled=not can_rec)
    with b2[3]:
        if can_rec:
            st.selectbox("Victim", live["deadlocked"], key="rec_victim",
                         format_func=lambda i: sim["processes"][i],
                         disabled=ss.get("rec_mode", "").startswith("Terminate all"))
        st.button("Recover from Deadlock", on_click=cb_recover, disabled=not can_rec, width="stretch")
    if not can_rec:
        st.caption("Recovery is available only while a real deadlock exists.")
    if ss.sim_msg:
        {"info": st.info, "warning": st.warning, "error": st.error,
         "success": st.success}[ss.sim_msg[0]](ss.sim_msg[1])

    left, right = st.columns([3, 2])
    with left:
        fig = rag_figure(sim["processes"], sim["resources"], sim["total"], sim["available"],
                         sim["allocation"], sim["request"], sim["status"])
        st.plotly_chart(fig, width="stretch")
        st.caption("Squares are resources (● held, ○ free). Circles are processes, "
                   "coloured by state. With several instances of a resource, a cycle alone does "
                   "not prove deadlock; the detection algorithm below decides.")
    with right:
        label, kind, why = sim_status(sim)
        st.markdown("**System status** " + badge(label.upper(), kind), unsafe_allow_html=True)
        last = sim["log"][-1]
        st.markdown(f"**Current event:** {last['event']}")
        st.caption(last["why"])
        st.markdown(f"**Next step:** {engine.next_hint(sim)}")
        st.markdown(f"**Available:** `{dict(zip(sim['resources'], sim['available']))}`")
        tbl = pd.DataFrame({
            "Process": sim["processes"], "State": sim["status"],
            "Holds": [engine.fmt_vec(a, sim["resources"]) for a in sim["allocation"]],
            "Requests": [engine.fmt_vec(r, sim["resources"]) for r in sim["request"]]})
        st.dataframe(style_status(tbl), hide_index=True, width="stretch")

    if det:
        st.subheader("Deadlock detection")
        if det["has_deadlock"]:
            st.error(det["explanation"])
            cyc = find_wait_for_cycle(sim["allocation"], sim["request"])
            if cyc:
                st.write("Circular wait: " + " → ".join(sim["processes"][i] for i in cyc)
                         + " (each waits for a resource held by the next).")
        else:
            st.success(det["explanation"])
        st.dataframe(pd.DataFrame([{
            "Step": s["step"],
            "Process": "-" if s["process"] is None else sim["processes"][s["process"]],
            "Work before": str(s["work_before"]), "Work after": str(s["work_after"]),
            "Finish": " ".join("T" if f else "F" for f in s["finish"]), "Note": s["note"]}
            for s in det["steps"]]), hide_index=True, width="stretch")
        st.caption("Detection uses Available, Allocation and outstanding Request. It is not the "
                   "Banker's safety algorithm, which uses worst-case Need.")

    st.subheader("Event log")
    st.dataframe(pd.DataFrame(sim["log"][::-1]).rename(
        columns={"n": "#", "event": "Event", "why": "Why it happened"}),
        hide_index=True, width="stretch")
    with st.expander("Waiting vs deadlock vs unsafe"):
        st.markdown(
            "- **Waiting**: a process is blocked for resources that will be freed by another "
            "process that can still finish. Temporary.\n"
            "- **Deadlock**: every process in a set waits on resources held only by others in "
            "the set. Permanent without outside intervention.\n"
            "- **Unsafe state**: a Banker's concept; deadlock is *possible*, but may not exist yet.")

    if ss.playing:
        s, ok, msg = engine.step(ss.sim)
        ss.sim = s
        if not ok:
            ss.playing = False
            _set_msg("warning", msg + " Playback stopped.")
        time.sleep(0.9)
        st.rerun()


# ------------------------------------------------------------------ PREVENTION
def page_prevention():
    st.header("Deadlock Prevention")
    st.write("Deadlock needs **all four** conditions at once. Prevention removes at least one.")
    conds = [
        ("Mutual exclusion", "A resource can be used by only one process at a time.",
         "A printer printing one job at a time.", "Make resources shareable (e.g. read-only files).",
         "Many resources (printers, locks) are inherently non-shareable."),
        ("Hold and wait", "A process holds some resources while waiting for others.",
         "P1 holds R1 and waits for R2.", "Request everything at once or hold nothing while waiting.",
         "Low utilisation and possible starvation."),
        ("No preemption", "Resources cannot be forcibly taken from a process.",
         "A process keeps a lock until it releases it.",
         "Allow the OS to preempt resources from waiting processes.",
         "Only works for resources whose state can be saved and restored."),
        ("Circular wait", "A cycle of processes each waits for a resource held by the next.",
         "P1 → P2 → P1.", "Impose a global order on resource types; request in increasing order.",
         "Hard to choose a natural order; may force early acquisition."),
    ]
    for name, d, ex, strat, trade in conds:
        with st.expander(name):
            st.markdown(f"**Definition:** {d}\n\n**Example:** {ex}\n\n**Prevention:** {strat}\n\n"
                        f"**Trade-off:** {trade}")

    st.subheader("Interactive: resource ordering (breaks circular wait)")
    order = ["R1", "R2", "R3", "R4"]
    st.caption("Global order: " + " < ".join(order) + ". Pick the order each process requests resources.")
    c1, c2 = st.columns(2)
    seq_a = c1.multiselect("Process P1 requests, in this order", order, default=["R1", "R2"], key="pa")
    seq_b = c2.multiselect("Process P2 requests, in this order", order, default=["R2", "R1"], key="pb")
    for name, seq in (("P1", seq_a), ("P2", seq_b)):
        r = validate_resource_order(order, seq)
        (st.success if r["valid"] else st.error)(f"{name}: {r['message']}")
    st.caption("P1 taking R1 then R2 while P2 takes R2 then R1 is the classic circular wait. "
               "Forcing both to follow the same order makes that cycle impossible.")

    st.subheader("Interactive: hold-and-wait prevention (all or nothing)")
    cols = st.columns(3)
    avail = [cols[j].number_input(f"Available R{j + 1}", 0, 5, 1 if j < 2 else 0, key=f"hwa{j}") for j in range(3)]
    need = [cols[j].number_input(f"Needs R{j + 1}", 0, 5, 1 if j < 2 else 0, key=f"hwn{j}") for j in range(3)]
    r = request_all_or_nothing(avail, need)
    (st.success if r["granted"] else st.warning)(r["message"] + f" Holds: {r['held']}.")

    st.subheader("Prevention vs avoidance vs detection vs recovery")
    st.dataframe(pd.DataFrame([
        {"Approach": "Prevention", "Idea": "Eliminate a necessary condition",
         "Cost": "Restricts how resources are requested"},
        {"Approach": "Avoidance", "Idea": "Grant a request only if the state stays safe (Banker's)",
         "Cost": "Needs advance maximum claims"},
        {"Approach": "Detection", "Idea": "Let deadlock happen, then find it", "Cost": "Periodic analysis"},
        {"Approach": "Recovery", "Idea": "Terminate or preempt to resolve an existing deadlock",
         "Cost": "Lost work"}]), hide_index=True, width="stretch")
    st.caption("No single technique is free or solves every case; real systems combine them.")


# ------------------------------------------------------------------ TEST BENCH
def _run_one(test_id):
    t = next(t for t in testbench.TESTS if t["id"] == test_id)
    ss.tb[test_id] = testbench.run_test(t)


def _run_all():
    ss.tb = {r["id"]: r for r in testbench.run_all()}


def _graph_for(inp):
    if not all(k in inp for k in ("allocation", "request", "available", "resources", "total")):
        return None
    det = detect_deadlock(inp["available"], inp["allocation"], inp["request"])
    status = []
    for i in range(len(inp["allocation"])):
        if i in det["deadlocked"]:
            status.append(engine.BLOCKED)
        elif any(inp["request"][i]):
            status.append(engine.WAITING)
        else:
            status.append(engine.RUNNING)
    fig = rag_figure([f"P{i + 1}" for i in range(len(status))], inp["resources"], inp["total"],
                     inp["available"], inp["allocation"], inp["request"], status)
    fig.update_layout(height=320)
    return fig


def page_testbench():
    st.header("Test Bench")
    st.caption("Each test calls the same functions the app uses. PASS means every check's actual "
               "result equals its expected result.")
    st.button("Run All Tests", on_click=_run_all, type="primary")
    done = list(ss.tb.values())
    if done:
        p = sum(1 for r in done if r["passed"])
        a, b, c = st.columns(3)
        a.metric("Run", f"{len(done)} / {len(testbench.TESTS)}")
        b.metric("Passed", p)
        c.metric("Failed", len(done) - p)
    for t in testbench.TESTS:
        r = ss.tb.get(t["id"])
        tag = "NOT RUN" if r is None else ("PASS" if r["passed"] else "FAIL")
        icon = {"NOT RUN": ":material/radio_button_unchecked:", "PASS": ":material/check_circle:",
                "FAIL": ":material/cancel:"}[tag]
        with st.expander(f"{t['id']} – {t['name']}  [{tag}]  ({t['category']})", icon=icon):
            st.write(f"**Purpose:** {t['purpose']}")
            st.write(f"**Expected:** {t['expected']}")
            st.button("Run this test", key=f"run_{t['id']}", on_click=_run_one, args=(t["id"],))
            if r is None:
                continue
            if r["error"]:
                st.error(r["error"])
            (st.success if r["passed"] else st.error)(
                f"{tag}. {r['explanation']}")
            st.dataframe(pd.DataFrame([{
                "Check": c["check"], "Expected": str(c["expected"]), "Actual": str(c["actual"]),
                "Result": "PASS" if c["passed"] else "FAIL"} for c in r["checks"]]),
                hide_index=True, width="stretch")
            with st.expander("Input scenario"):
                st.json(r["input"], expanded=False)
            if r["output"]:
                st.text(r["output"])
            fig = _graph_for(r["input"]) if isinstance(r["input"], dict) else None
            if fig:
                st.plotly_chart(fig, width="stretch", key=f"fig_{t['id']}")
            if r["steps"]:
                with st.expander("Algorithm steps"):
                    st.dataframe(pd.DataFrame([{
                        "Step": s["step"], "Work after": str(s["work_after"]), "Note": s["note"]}
                        for s in r["steps"]]), hide_index=True, width="stretch")


# ------------------------------------------------------------------ AI USAGE
def page_ai():
    st.header("AI Usage Record")
    st.markdown("""
**Where AI was used.** The assistant Claude (Anthropic) generated the code for this version of
the dashboard (algorithms, simulation engine, Streamlit UI, Test Bench and pytest suite) from a
written specification supplied by the student.

**How it was checked.**
- The algorithms are pure Python functions covered by an automated `pytest` suite in `tests/`.
  Run `pytest` to reproduce the results yourself.
- The in-dashboard Test Bench calls the same functions and compares expected with actual values.
- The five-process Banker's example matches the standard textbook example, and its safe
  sequence is re-verified by replaying it.

**Limitations.**
- The simulation uses fixed, scripted request sequences, not random workloads.
- Recovery supports process termination only (no preemption or rollback).
- Detection treats a request as all-or-nothing per process.
- The app has been tested locally and with Streamlit's test harness; a Render deployment must be
  checked by the student.

**Student to complete.** Record here, in your own words, which parts you reviewed, modified and
can explain. AI-generated code should be understood before being submitted.
""")


PAGE_FUNCS = {"Overview": page_overview, "Banker's Algorithm": page_bankers,
              "Deadlock Lab": page_lab, "Prevention": page_prevention,
              "Test Bench": page_testbench, "AI Usage Record": page_ai}

try:
    PAGE_FUNCS[ss.page]()
except ValidationError as exc:
    st.error(f"Invalid input: {exc}")
