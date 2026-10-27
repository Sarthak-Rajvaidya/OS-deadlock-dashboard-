# AI-Assisted Dashboard Development and Deadlock Analysis

Streamlit dashboard for an Operating Systems assignment: Banker's Algorithm (avoidance),
Deadlock Lab (graphical simulation, detection, recovery), Prevention, Test Bench, AI Usage Record.

## Run locally
```
python -m venv .venv
.venv\Scripts\activate          # Windows  (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
```

## Run tests
```
pip install -r requirements-dev.txt
python -m pytest -q
```

## Deploy on Render (Web Service)
- Build command: `pip install -r requirements.txt`
- Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

## Structure
- `app.py` UI only; `ui_graphs.py` Plotly resource-allocation graph
- `algorithms/` bankers.py, deadlock.py, prevention.py (pure functions)
- `simulation/` scenarios.py, engine.py (deterministic step state machine)
- `testbench.py` in-dashboard tests (10 cases, same functions as the app); `tests/` pytest suite

## Demo script
1. Overview: read the summary and live status.
2. Banker's Algorithm: show Need, step table and safe sequence; request P2 [1,0,2] (granted),
   P5 [3,3,0] (denied, unsafe), P3 [4,0,0] (waiting).
3. Deadlock Lab (1 resource): Next Step x4 to watch Running -> Waiting; Detect Deadlock;
   point at the graph and the detection table; terminate P1; see P2 resume.
4. Reset, choose the 3-resource circular scenario, Run to Deadlock, Terminate all.
5. Test Bench: Run All Tests, open TC6 and TC7.
6. Prevention: show resource ordering rejecting R2 then R1.
