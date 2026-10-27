"""Plotly resource-allocation graph, built from the live scenario state only."""
import plotly.graph_objects as go

STATUS_COLOR = {"Ready": "#64748b", "Running": "#3b82f6", "Waiting": "#f59e0b",
                "Blocked by deadlock": "#ef4444", "Completed": "#22c55e",
                "Terminated": "#6b7280"}
TEXT = "#e2e8f0"
BG = "#0f172a"


def _offset(p1, p2, d):
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = (dx ** 2 + dy ** 2) ** 0.5 or 1
    nx, ny = -dy / length, dx / length
    return (p1[0] + nx * d, p1[1] + ny * d), (p2[0] + nx * d, p2[1] + ny * d)


def _shrink(a, b, f0=0.12, f1=0.12):
    return ((a[0] + (b[0] - a[0]) * f0, a[1] + (b[1] - a[1]) * f0),
            (b[0] - (b[0] - a[0]) * f1, b[1] - (b[1] - a[1]) * f1))


def rag_figure(processes, resources, total, available, allocation, request, status):
    """Directed resource-allocation graph.

    Resource node -> process : allocation edge (label = instances held)
    Process -> resource node : request edge   (label = instances requested)
    """
    n, m = len(processes), len(resources)
    px = {i: (i + 0.5) / n * 10 for i in range(n)}
    rx = {j: (j + 0.5) / m * 10 for j in range(m)}
    ppos = {i: (px[i], 0.0) for i in range(n)}
    rpos = {j: (rx[j], 3.0) for j in range(m)}
    fig = go.Figure()
    anns = []

    def edge(a, b, color, dash, label, side):
        a2, b2 = _offset(a, b, side)
        s, e = _shrink(a2, b2)
        fig.add_trace(go.Scatter(x=[s[0], e[0]], y=[s[1], e[1]], mode="lines",
                                 line=dict(color=color, width=2.5, dash=dash),
                                 hoverinfo="skip", showlegend=False))
        anns.append(dict(x=e[0], y=e[1], ax=s[0] + (e[0] - s[0]) * 0.8, ay=s[1] + (e[1] - s[1]) * 0.8,
                         xref="x", yref="y", axref="x", ayref="y", showarrow=True,
                         arrowhead=2, arrowsize=1.6, arrowwidth=2.5, arrowcolor=color, text=""))
        mx, my = (s[0] + e[0]) / 2, (s[1] + e[1]) / 2
        anns.append(dict(x=mx, y=my, text=f"<b>{label}</b>", showarrow=False,
                         font=dict(color=color, size=12), bgcolor=BG, borderpad=1))

    for i in range(n):
        for j in range(m):
            if allocation[i][j] > 0:
                edge(rpos[j], ppos[i], "#60a5fa", "solid", allocation[i][j], 0.18)
            if request[i][j] > 0:
                col = "#ef4444" if status[i] == "Blocked by deadlock" else "#f59e0b"
                edge(ppos[i], rpos[j], col, "dash", request[i][j], 0.18)

    fig.add_trace(go.Scatter(
        x=[ppos[i][0] for i in range(n)], y=[ppos[i][1] for i in range(n)], mode="markers+text",
        text=[f"<b>{processes[i]}</b>" for i in range(n)], textfont=dict(color="white", size=14),
        marker=dict(size=58, color=[STATUS_COLOR[s] for s in status], line=dict(color=TEXT, width=2)),
        hovertext=[f"{processes[i]}: {status[i]}<br>Holds {allocation[i]}<br>Requests {request[i]}"
                   for i in range(n)], hoverinfo="text", showlegend=False))
    fig.add_trace(go.Scatter(
        x=[rpos[j][0] for j in range(m)], y=[rpos[j][1] for j in range(m)], mode="markers+text",
        text=[f"<b>{resources[j]}</b>" for j in range(m)], textfont=dict(color="white", size=14),
        marker=dict(size=58, symbol="square", color="#1e293b", line=dict(color="#94a3b8", width=2)),
        hovertext=[f"{resources[j]}: total {total[j]}, free {available[j]}" for j in range(m)],
        hoverinfo="text", showlegend=False))
    for j in range(m):
        held = total[j] - available[j]
        dots = "●" * held + "○" * available[j]
        anns.append(dict(x=rpos[j][0], y=rpos[j][1] + 0.62, showarrow=False,
                         text=f"{dots}<br>{available[j]}/{total[j]} free",
                         font=dict(color=TEXT, size=12)))
    # legend entries
    for name, color, dash in (("Allocation: resource → process (holds)", "#60a5fa", "solid"),
                              ("Request: process → resource (waits)", "#f59e0b", "dash"),
                              ("Request by deadlocked process", "#ef4444", "dash")):
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", name=name,
                                 line=dict(color=color, dash=dash, width=3)))
    fig.update_layout(
        annotations=anns, height=420, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor=BG, plot_bgcolor=BG, font=dict(color=TEXT),
        xaxis=dict(visible=False, range=[-0.5, 10.5]), yaxis=dict(visible=False, range=[-0.8, 4.0]),
        legend=dict(orientation="h", y=-0.02, x=0, font=dict(size=11)))
    return fig
