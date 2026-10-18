
import streamlit as st
import pandas as pd
import plotly.express as px
from copy import deepcopy

from algorithms.bankers import (
    calculate_need,
    safety_algorithm,
    request_resources,
)
from algorithms.deadlock import (
    detect_deadlock,
    recover_by_terminating,
)


# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(
    page_title="OS Resource Manager",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp {
        background: #0b1120;
        color: #e5e7eb;
    }
    [data-testid="stSidebar"] {
        background: #111827;
    }
    [data-testid="stMetric"] {
        background: #151f32;
        border: 1px solid #29364d;
        padding: 16px;
        border-radius: 12px;
    }
    div[data-testid="stDataFrame"],
    div[data-testid="stDataEditor"] {
        border: 1px solid #29364d;
        border-radius: 10px;
    }
    .hero {
        background: linear-gradient(120deg, #172554, #172033);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
    }
    .hero h1 {
        margin: 0;
        color: #f8fafc;
        font-size: 30px;
    }
    .hero p {
        color: #cbd5e1;
        margin-bottom: 0;
    }
    .small-note {
        color: #94a3b8;
        font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# DEMONSTRATION DATA
# ---------------------------------------------------------
INITIAL_AVAILABLE = [3, 3, 2]

INITIAL_ALLOCATION = [
    [0, 1, 0],
    [2, 0, 0],
    [3, 0, 2],
    [2, 1, 1],
    [0, 0, 2],
]

INITIAL_MAXIMUM = [
    [7, 5, 3],
    [3, 2, 2],
    [9, 0, 2],
    [2, 2, 2],
    [4, 3, 3],
]

RESOURCE_NAMES = ["Resource A", "Resource B", "Resource C"]


def reset_main_state():
    st.session_state.available = INITIAL_AVAILABLE.copy()
    st.session_state.allocation = deepcopy(INITIAL_ALLOCATION)
    st.session_state.maximum = deepcopy(INITIAL_MAXIMUM)
    st.session_state.editor_version = (
        st.session_state.get("editor_version", 0) + 1
    )
    st.session_state.last_request = None


if "available" not in st.session_state:
    reset_main_state()

if "deadlock_available" not in st.session_state:
    st.session_state.deadlock_available = [0]
    st.session_state.deadlock_allocation = [[1], [1]]
    st.session_state.deadlock_request = [[1], [1]]
    st.session_state.deadlock_recovered = False


# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------
def matrix_df(matrix):
    return pd.DataFrame(
        matrix,
        index=[f"P{i}" for i in range(len(matrix))],
        columns=RESOURCE_NAMES,
    )


def show_matrix(title, matrix):
    st.markdown(f"**{title}**")
    st.dataframe(
        matrix_df(matrix),
        use_container_width=True,
    )


def show_vector(title, vector):
    st.markdown(f"**{title}**")
    st.dataframe(
        pd.DataFrame([vector], columns=RESOURCE_NAMES),
        hide_index=True,
        use_container_width=True,
    )


def resource_bar_chart(available, allocation):
    totals = [
        available[j] + sum(row[j] for row in allocation)
        for j in range(len(available))
    ]

    rows = []
    for j, name in enumerate(RESOURCE_NAMES[:len(available)]):
        rows.append({
            "Resource": name,
            "Allocated": sum(row[j] for row in allocation),
            "Available": available[j],
            "Total": totals[j],
        })

    df = pd.DataFrame(rows)
    fig = px.bar(
        df,
        x="Resource",
        y=["Allocated", "Available"],
        barmode="stack",
        title="Current Resource Distribution",
        color_discrete_sequence=["#6366f1", "#22c55e"],
    )
    fig.update_layout(
        paper_bgcolor="#0b1120",
        plot_bgcolor="#0b1120",
        font_color="#e5e7eb",
        legend_title_text="Resource state",
        margin=dict(l=10, r=10, t=55, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def policy_check(order):
    """Check whether resource acquisitions follow A < B < C."""
    ranks = {"A": 0, "B": 1, "C": 2}

    if not order or any(resource not in ranks for resource in order):
        return False

    if len(order) != len(set(order)):
        return False

    return all(
        ranks[order[i]] < ranks[order[i + 1]]
        for i in range(len(order) - 1)
    )


# ---------------------------------------------------------
# HEADER AND NAVIGATION
# ---------------------------------------------------------
st.markdown("""
<div class="hero">
    <h1>🖥️ OS Resource Manager</h1>
    <p>Deadlock Analysis • Resource Allocation • Banker's Algorithm</p>
    <p class="small-note">
        Operating Systems IA Activity 2 | Interactive simulation and verification
    </p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("Navigation")
    page = st.radio(
        "Choose a module",
        [
            "Overview",
            "Banker's Algorithm",
            "Deadlock Lab",
            "Prevention",
            "Test Bench",
            "AI Usage Record",
        ],
    )

    st.divider()
    st.caption("Simulation controls")

    if st.button("Reset main simulation", use_container_width=True):
        reset_main_state()
        st.rerun()

    st.caption("Resetting the main simulation does not change the separate deadlock lab.")


# ---------------------------------------------------------
# COMPUTE CURRENT MAIN STATE
# ---------------------------------------------------------
available = st.session_state.available
allocation = st.session_state.allocation
maximum = st.session_state.maximum

try:
    need = calculate_need(allocation, maximum)
    safety = safety_algorithm(available, allocation, maximum)
    state_valid = True
    validation_error = None
except (ValueError, TypeError, IndexError) as exc:
    need = []
    safety = None
    state_valid = False
    validation_error = str(exc)


# ---------------------------------------------------------
# OVERVIEW
# ---------------------------------------------------------
if page == "Overview":
    st.subheader("System Overview")
    st.caption(
        "Metrics below are calculated from the current simulation state."
    )

    if not state_valid:
        st.error(f"Invalid system configuration: {validation_error}")
    else:
        allocated_count = sum(sum(row) for row in allocation)
        available_count = sum(available)
        total_count = allocated_count + available_count

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Processes", len(allocation))
        c2.metric("Resource Types", len(available))
        c3.metric("Allocated Units", allocated_count)
        c4.metric("Available Units", available_count)

        if safety["safe"]:
            st.success(
                "SAFE STATE — all processes can complete in a safe sequence."
            )
            st.markdown(
                "**Safe sequence:** "
                + " → ".join(safety["sequence"])
            )
        else:
            st.warning(
                "UNSAFE STATE — no complete safe sequence was found."
            )
            st.write(
                "Processes that could not finish:",
                ", ".join(safety["unfinished"]),
            )

        st.progress(
            allocated_count / total_count if total_count else 0.0,
            text="Allocated resource units",
        )

        resource_bar_chart(available, allocation)

        left, right = st.columns(2)
        with left:
            show_vector("Available Vector", available)
            show_matrix("Allocation Matrix", allocation)
        with right:
            show_matrix("Maximum Matrix", maximum)
            show_matrix("Need Matrix", need)

    st.info(
        "An unsafe state is not automatically a deadlock. "
        "Use Deadlock Lab for the separate detection algorithm."
    )


# ---------------------------------------------------------
# BANKER'S ALGORITHM
# ---------------------------------------------------------
elif page == "Banker's Algorithm":
    st.subheader("Banker's Algorithm")
    st.write(
        "Edit the resource matrices, calculate Need, verify safety, "
        "and submit resource requests."
    )

    st.info(
        "Need = Maximum − Allocation. "
        "Changes to the matrices are applied to this simulation when you click Apply."
    )

    if not state_valid:
        st.error(f"Current state is invalid: {validation_error}")
        if st.button("Restore valid demonstration state"):
            reset_main_state()
            st.rerun()

    else:
        version = st.session_state.editor_version

        with st.expander("Edit Available Vector", expanded=False):
            available_inputs = st.columns(len(available))
            edited_available = []

            for j, col in enumerate(available_inputs):
                with col:
                    edited_available.append(
                        st.number_input(
                            RESOURCE_NAMES[j],
                            min_value=0,
                            max_value=100000,
                            value=int(available[j]),
                            step=1,
                            key=f"avail_{version}_{j}",
                        )
                    )

        left, right = st.columns(2)

        with left:
            st.markdown("#### Allocation Matrix")
            edited_allocation_df = st.data_editor(
                matrix_df(allocation),
                key=f"allocation_editor_{version}",
                use_container_width=True,
                num_rows="fixed",
            )

        with right:
            st.markdown("#### Maximum Matrix")
            edited_maximum_df = st.data_editor(
                matrix_df(maximum),
                key=f"maximum_editor_{version}",
                use_container_width=True,
                num_rows="fixed",
            )

        if st.button("Apply matrices and verify", type="primary"):
            try:
                new_allocation = edited_allocation_df.values.tolist()
                new_maximum = edited_maximum_df.values.tolist()

                new_allocation = [
                    [int(x) for x in row] for row in new_allocation
                ]
                new_maximum = [
                    [int(x) for x in row] for row in new_maximum
                ]
                new_available = [int(x) for x in edited_available]

                # Validate before saving anything.
                check = safety_algorithm(
                    new_available, new_allocation, new_maximum
                )

                st.session_state.available = new_available
                st.session_state.allocation = new_allocation
                st.session_state.maximum = new_maximum
                st.session_state.editor_version += 1
                st.session_state.last_request = None

                st.success("Matrices applied and validated.")
                st.rerun()

            except (ValueError, TypeError, OverflowError) as exc:
                st.error(f"Changes were not applied: {exc}")

        st.divider()
        st.markdown("### Calculated Need Matrix")
        need = calculate_need(allocation, maximum)
        show_matrix("Need = Maximum − Allocation", need)

        st.markdown("### Safety Check")
        safety = safety_algorithm(available, allocation, maximum)

        if safety["safe"]:
            st.success("SAFE: a complete safe sequence exists.")
            st.code(" → ".join(safety["sequence"]))
        else:
            st.error("UNSAFE: no complete safe sequence exists.")
            st.write(
                "Unfinished processes:",
                ", ".join(safety["unfinished"]),
            )
            st.write(
                "Partial sequence (not a complete safe sequence):",
                " → ".join(safety["partial_sequence"]) or "None",
            )

        if safety["trace"]:
            st.markdown("#### Work Vector Trace")
            trace_rows = []

            for step in safety["trace"]:
                trace_rows.append({
                    "Process": step["process"],
                    "Need": step["need"],
                    "Work Before": step["work_before"],
                    "Released Allocation": step["released_allocation"],
                    "Work After": step["work_after"],
                })

            st.dataframe(
                pd.DataFrame(trace_rows),
                hide_index=True,
                use_container_width=True,
            )

        st.divider()
        st.markdown("### Resource Request Simulator")
        st.caption(
            "A granted request updates the main simulation. "
            "Rejected requests leave the original state unchanged."
        )

        with st.form("resource_request_form"):
            selected_process = st.selectbox(
                "Process requesting resources",
                list(range(len(allocation))),
                format_func=lambda i: f"P{i}",
            )

            request_cols = st.columns(len(available))
            request = []

            for j, col in enumerate(request_cols):
                with col:
                    request.append(
                        st.number_input(
                            RESOURCE_NAMES[j],
                            min_value=0,
                            max_value=100000,
                            value=0,
                            step=1,
                            key=f"request_input_{j}",
                        )
                    )

            submitted = st.form_submit_button("Evaluate request")

        if submitted:
            before = deepcopy(
                (
                    st.session_state.available,
                    st.session_state.allocation,
                    st.session_state.maximum,
                )
            )

            result = request_resources(
                int(selected_process),
                [int(x) for x in request],
                st.session_state.available,
                st.session_state.allocation,
                st.session_state.maximum,
            )

            st.session_state.last_request = result

            if result["status"] == "GRANTED":
                st.session_state.available = result["available"]
                st.session_state.allocation = result["allocation"]
                st.success(result["reason"])
                st.rerun()

            elif result["status"] == "WAIT":
                st.warning(result["reason"])

            elif result["status"] == "DENIED_UNSAFE":
                st.error(result["reason"])

            else:
                st.error(result["reason"])

            after = (
                st.session_state.available,
                st.session_state.allocation,
                st.session_state.maximum,
            )

            if result["status"] != "GRANTED":
                st.write(
                    "Verification — original state unchanged:",
                    before == after,
                )


# ---------------------------------------------------------
# DEADLOCK LAB
# ---------------------------------------------------------
elif page == "Deadlock Lab":
    st.subheader("Deadlock Detection and Recovery")
    st.warning(
        "This is a separate, deliberately constructed detection scenario. "
        "It is not the Banker's Algorithm demonstration."
    )

    st.markdown("### Current Detection Scenario")
    st.write(
        "Two processes each hold one instance of Resource R and request "
        "one additional instance. No instances are currently available."
    )

    st.write("Available:", st.session_state.deadlock_available)
    show_matrix(
        "Current Allocation",
        st.session_state.deadlock_allocation,
    )
    show_matrix(
        "Outstanding Request",
        st.session_state.deadlock_request,
    )

    detection = detect_deadlock(
        st.session_state.deadlock_available,
        st.session_state.deadlock_allocation,
        st.session_state.deadlock_request,
    )

    if detection["deadlocked"]:
        st.error(
            "Deadlock detected under this scenario's stated resource assumptions."
        )
        st.write(
            "Unfinished processes:",
            ", ".join(detection["deadlocked_processes"]),
        )
    else:
        st.success("No deadlocked processes were identified.")

    st.markdown("#### Detection Trace")
    if detection["trace"]:
        st.dataframe(
            pd.DataFrame(detection["trace"]),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.write("No processes could complete in this detection run.")

    st.divider()
    st.markdown("### Recovery")

    if not st.session_state.deadlock_recovered:
        recovery_process = st.selectbox(
            "Select a process to terminate",
            list(range(len(st.session_state.deadlock_allocation))),
            format_func=lambda i: f"P{i}",
            key="recovery_process",
        )

        if st.button("Terminate process and release resources", type="primary"):
            recovered = recover_by_terminating(
                recovery_process,
                st.session_state.deadlock_available,
                st.session_state.deadlock_allocation,
                st.session_state.deadlock_request,
            )

            st.session_state.deadlock_available = recovered["available"]
            st.session_state.deadlock_allocation = recovered["allocation"]
            st.session_state.deadlock_request = recovered["request"]
            st.session_state.deadlock_recovered = True
            st.success(
                f"{recovered['terminated']} terminated; its resources were released."
            )
            st.rerun()
    else:
        st.success("Recovery has been simulated.")
        st.write(
            "Updated Available:",
            st.session_state.deadlock_available,
        )

        after_recovery = detect_deadlock(
            st.session_state.deadlock_available,
            st.session_state.deadlock_allocation,
            st.session_state.deadlock_request,
        )

        st.write(
            "Remaining deadlocked processes:",
            after_recovery["deadlocked_processes"] or "None",
        )

        if st.button("Reset deadlock scenario"):
            st.session_state.deadlock_available = [0]
            st.session_state.deadlock_allocation = [[1], [1]]
            st.session_state.deadlock_request = [[1], [1]]
            st.session_state.deadlock_recovered = False
            st.rerun()

    st.caption(
        "The recovery operation is a simulation. In a real OS, process "
        "termination and resource release depend on the resource and process model."
    )


# ---------------------------------------------------------
# DEADLOCK PREVENTION
# ---------------------------------------------------------
elif page == "Prevention":
    st.subheader("Deadlock Prevention")
    st.write(
        "Prevention changes the resource-acquisition policy so at least "
        "one necessary deadlock condition cannot arise under that policy."
    )

    st.markdown("### Policy 1: Fixed Resource Ordering")
    st.write("Rule: acquire resources in the global order A → B → C.")

    acquisition_order = st.multiselect(
        "Select an example acquisition order",
        ["A", "B", "C"],
        default=["A", "B"],
    )

    if policy_check(acquisition_order):
        st.success(
            "The selected order follows the fixed ordering rule."
        )
    else:
        st.error(
            "The selected order violates the fixed ordering rule. "
            "For example, acquiring B before A violates A → B → C."
        )

    st.info(
        "A global order prevents circular wait when all participating "
        "processes obey the same order. It does not guarantee maximum "
        "resource utilization."
    )

    st.divider()
    st.markdown("### Policy 2: Eliminate Hold and Wait")
    st.write(
        "Require a process to request all resources it needs before it "
        "begins execution, instead of holding some while waiting for others."
    )

    st.markdown("""
    **Advantages**
    - Removes the hold-and-wait condition under the stated policy.
    - Makes resource acquisition easier to reason about.

    **Trade-offs**
    - Resources may remain idle while reserved.
    - A process may wait longer before it can start.
    - Concurrent execution and resource utilization may decrease.
    """)

    st.divider()
    st.markdown("### Compare the Policies")

    st.dataframe(
        pd.DataFrame([
            {
                "Policy": "Fixed resource ordering",
                "Condition addressed": "Circular wait",
                "Trade-off": "Resource order may constrain execution",
            },
            {
                "Policy": "Request all resources before execution",
                "Condition addressed": "Hold and wait",
                "Trade-off": "Lower utilization and concurrency",
            },
        ]),
        hide_index=True,
        use_container_width=True,
    )


# ---------------------------------------------------------
# TEST BENCH
# ---------------------------------------------------------
elif page == "Test Bench":
    st.subheader("IA Test Bench — TC1 to TC6")
    st.write(
        "Run the scenarios against the algorithm implementations. "
        "Results are computed when you press the button."
    )

    if st.button("Run all six test scenarios", type="primary"):
        results = []

        # TC1: safe state
        safe_result = safety_algorithm(
            INITIAL_AVAILABLE,
            INITIAL_ALLOCATION,
            INITIAL_MAXIMUM,
        )
        results.append({
            "Test": "TC1",
            "Scenario": "Safe state",
            "Actual Result": (
                "SAFE: " + " → ".join(safe_result["sequence"])
                if safe_result["safe"] else "UNSAFE"
            ),
            "Expected Behavior Met": safe_result["safe"],
            "Analysis": "Complete safe sequence verified.",
        })

        # TC2: exceeds Available, but does not exceed Need
        tc2 = request_resources(
            0, [0, 0, 3],
            INITIAL_AVAILABLE, INITIAL_ALLOCATION, INITIAL_MAXIMUM,
        )
        results.append({
            "Test": "TC2",
            "Scenario": "Request exceeds Available",
            "Actual Result": tc2["status"],
            "Expected Behavior Met": tc2["status"] == "WAIT",
            "Analysis": tc2["reason"],
        })

        # TC3: request is within Need and Available but unsafe
        tc3 = request_resources(
            4, [3, 3, 0],
            INITIAL_AVAILABLE, INITIAL_ALLOCATION, INITIAL_MAXIMUM,
        )
        results.append({
            "Test": "TC3",
            "Scenario": "Request produces unsafe state",
            "Actual Result": tc3["status"],
            "Expected Behavior Met": tc3["status"] == "DENIED_UNSAFE",
            "Analysis": tc3["reason"],
        })

        # TC4: separate deadlock detection scenario
        tc4 = detect_deadlock(
            [0],
            [[1], [1]],
            [[1], [1]],
        )
        results.append({
            "Test": "TC4",
            "Scenario": "Deadlock detection",
            "Actual Result": (
                "DEADLOCK: " + ", ".join(tc4["deadlocked_processes"])
                if tc4["deadlocked"] else "NO DEADLOCK"
            ),
            "Expected Behavior Met": (
                tc4["deadlocked"]
                and set(tc4["deadlocked_processes"]) == {"P0", "P1"}
            ),
            "Analysis": "Current outstanding requests cannot be satisfied.",
        })

        # TC5: resource ordering policy
        tc5 = policy_check(["A", "B", "C"])
        results.append({
            "Test": "TC5",
            "Scenario": "Prevention policy",
            "Actual Result": (
                "ORDER VALID" if tc5 else "ORDER VIOLATION"
            ),
            "Expected Behavior Met": tc5,
            "Analysis": "Acquisition order follows A → B → C.",
        })

        # TC6: boundary and invalid-input cases
        invalid_checks = {}

        try:
            zero_available = safety_algorithm(
                [0, 0, 0],
                INITIAL_ALLOCATION,
                INITIAL_MAXIMUM,
            )
            invalid_checks["Zero Available handled"] = (
                isinstance(zero_available["safe"], bool)
            )
        except (ValueError, TypeError, IndexError):
            invalid_checks["Zero Available handled"] = False

        zero_need = request_resources(
            3, [0, 1, 1],
            INITIAL_AVAILABLE, INITIAL_ALLOCATION, INITIAL_MAXIMUM,
        )
        invalid_checks["Zero remaining Need"] = (
            zero_need["status"] == "GRANTED"
        )

        invalid_id = request_resources(
            99, [0, 0, 0],
            INITIAL_AVAILABLE, INITIAL_ALLOCATION, INITIAL_MAXIMUM,
        )
        invalid_checks["Invalid process ID"] = (
            invalid_id["status"] == "INVALID"
        )

        negative = request_resources(
            0, [-1, 0, 0],
            INITIAL_AVAILABLE, INITIAL_ALLOCATION, INITIAL_MAXIMUM,
        )
        invalid_checks["Negative request"] = (
            negative["status"] == "INVALID"
        )

        try:
            bad_allocation = deepcopy(INITIAL_ALLOCATION)
            bad_allocation[0][0] = INITIAL_MAXIMUM[0][0] + 1
            safety_algorithm(
                INITIAL_AVAILABLE, bad_allocation, INITIAL_MAXIMUM
            )
            invalid_checks["Allocation above Maximum"] = False
        except ValueError:
            invalid_checks["Allocation above Maximum"] = True

        tc6_pass = all(invalid_checks.values())

        results.append({
            "Test": "TC6",
            "Scenario": "Boundary and invalid inputs",
            "Actual Result": (
                f"{sum(invalid_checks.values())}/{len(invalid_checks)} checks passed"
            ),
            "Expected Behavior Met": tc6_pass,
            "Analysis": "; ".join(
                f"{name}: {'PASS' if passed else 'FAIL'}"
                for name, passed in invalid_checks.items()
            ),
        })

        st.session_state.test_results = results

    if "test_results" in st.session_state:
        test_df = pd.DataFrame(st.session_state.test_results)
        st.dataframe(test_df, hide_index=True, use_container_width=True)

        passed = int(test_df["Expected Behavior Met"].sum())
        total = len(test_df)

        c1, c2, c3 = st.columns(3)
        c1.metric("Scenarios", total)
        c2.metric("Expected Behaviors Met", passed)
        c3.metric("Scenarios Needing Review", total - passed)

        if passed == total:
            st.success(
                "All six scenario-level checks passed. "
                "Review the detailed analysis before submitting."
            )
        else:
            st.error(
                "One or more scenarios failed. Inspect the result table "
                "and fix the implementation before claiming completion."
            )

        st.download_button(
            "Download analytical results CSV",
            data=test_df.to_csv(index=False).encode("utf-8"),
            file_name="os_ia_test_results.csv",
            mime="text/csv",
        )
    else:
        st.info("Run the scenarios to generate the analytical results table.")


# ---------------------------------------------------------
# AI USAGE RECORD
# ---------------------------------------------------------
elif page == "AI Usage Record":
    st.subheader("AI Usage Record")
    st.write(
        "Document the tools actually used and verify their outputs. "
        "Edit the student-verification column to reflect your group's real work."
    )

    ai_df = pd.DataFrame([
        {
            "AI Tool Used": "ChatGPT",
            "Purpose": "Algorithm guidance and debugging",
            "Output Generated": "Code suggestions and test design",
            "Student Verification": "To be completed by group",
        },
        {
            "AI Tool Used": "ChatGPT",
            "Purpose": "Dashboard design assistance",
            "Output Generated": "UI layout and implementation guidance",
            "Student Verification": "To be completed by group",
        },
    ])

    edited_ai_df = st.data_editor(
        ai_df,
        num_rows="dynamic",
        use_container_width=True,
        key="ai_usage_editor",
    )

    st.download_button(
        "Download AI usage record CSV",
        data=edited_ai_df.to_csv(index=False).encode("utf-8"),
        file_name="ai_usage_record.csv",
        mime="text/csv",
    )

    st.caption(
        "Record only tools your group actually used. Verify algorithm "
        "behavior yourselves and be ready to explain the implementation."
    )


# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------
st.divider()
st.caption(
    "OS Resource Manager | IA Activity 2 | "
    "Educational simulation — results depend on the current scenario."
)
