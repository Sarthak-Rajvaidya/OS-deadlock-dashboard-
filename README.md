# OS Resource Manager

An interactive dashboard for OS IA Activity 2:
Deadlock Analysis and Resource Allocation.

## Features

- Banker's Algorithm and Need matrix
- Safe-state verification and safe sequences
- Resource-request validation
- Unsafe-state avoidance
- Separate deadlock detection and recovery
- Deadlock prevention policy demonstration
- Boundary and invalid-input testing
- AI usage record and test-case analysis

## Technology Stack

- Python
- Streamlit
- Pandas
- Plotly

## Run Locally

1. Create and activate a Python virtual environment.
2. Install dependencies:

   `python -m pip install -r requirements.txt`

3. Run the dashboard:

   `python -m streamlit run app.py`

## Run Algorithm Tests

`python -m unittest discover -s tests -v`