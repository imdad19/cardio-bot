"""
dashboard.py — Generate visual dashboard charts for CardioBot
Uses matplotlib to create professional charts from patient data.
"""

import os
import io
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime
from collections import Counter


# ── Style config ──────────────────────────────────────────────────────────────

COLORS = ["#4A90D9", "#D94A4A", "#50C878", "#F5A623", "#9B59B6",
          "#1ABC9C", "#E74C3C", "#3498DB", "#2ECC71", "#E67E22"]
BG_COLOR = "#1E1E2E"
CARD_COLOR = "#2D2D44"
TEXT_COLOR = "#E0E0E0"
ACCENT_COLOR = "#4A90D9"


def generate_dashboard(stats: dict, output_path: str = None) -> str:
    """Generate a composite dashboard image and return the file path."""
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), "dashboard.png")

    fig = plt.figure(figsize=(14, 10), facecolor=BG_COLOR)

    # Title
    fig.suptitle("CardioBot  --  Tableau de Bord",
                 fontsize=20, fontweight="bold", color=TEXT_COLOR, y=0.97)

    # ── Row 1: Stat cards ────────────────────────────────────────────────────
    card_data = [
        ("Patients HDJ\n(Total)", str(stats.get("total_hdj", 0))),
        ("Patients HDJ\n(Ce mois)", str(stats.get("hdj_this_month", 0))),
        ("Operations Bloc\n(Total)", str(stats.get("total_bloc", 0))),
        ("Operations Bloc\n(Ce mois)", str(stats.get("bloc_this_month", 0))),
    ]

    for i, (label, value) in enumerate(card_data):
        ax = fig.add_axes([0.05 + i * 0.235, 0.78, 0.21, 0.14])
        ax.set_facecolor(CARD_COLOR)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.text(0.5, 0.65, value, fontsize=28, fontweight="bold",
                color=ACCENT_COLOR, ha="center", va="center")
        ax.text(0.5, 0.25, label, fontsize=10,
                color=TEXT_COLOR, ha="center", va="center")
        for spine in ax.spines.values():
            spine.set_color("#3D3D5C")
            spine.set_linewidth(1.5)
        ax.set_xticks([])
        ax.set_yticks([])

    # ── Row 2 Left: Exam distribution ────────────────────────────────────────
    ax1 = fig.add_axes([0.06, 0.38, 0.4, 0.35], facecolor=CARD_COLOR)
    exam_counts = stats.get("exam_counts", {})
    if exam_counts:
        labels = list(exam_counts.keys())
        values = list(exam_counts.values())
        bars = ax1.barh(labels, values, color=COLORS[:len(labels)], height=0.6)
        ax1.set_xlabel("Nombre", color=TEXT_COLOR, fontsize=9)
        for bar, val in zip(bars, values):
            ax1.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                     str(val), va="center", color=TEXT_COLOR, fontsize=10)
    else:
        ax1.text(0.5, 0.5, "Aucune donnee", ha="center", va="center",
                 color=TEXT_COLOR, fontsize=12)
    ax1.set_title("Repartition des Examens", color=TEXT_COLOR, fontsize=12, pad=10)
    ax1.tick_params(colors=TEXT_COLOR, labelsize=9)
    for spine in ax1.spines.values():
        spine.set_color("#3D3D5C")

    # ── Row 2 Right: Clinique distribution ───────────────────────────────────
    ax2 = fig.add_axes([0.56, 0.38, 0.4, 0.35], facecolor=CARD_COLOR)
    clinique_counts = stats.get("clinique_counts", {})
    if clinique_counts:
        labels = list(clinique_counts.keys())[:8]
        values = [clinique_counts[l] for l in labels]
        wedges, texts, autotexts = ax2.pie(
            values, labels=None, autopct="%1.0f%%",
            colors=COLORS[:len(labels)], startangle=90,
            textprops={"color": TEXT_COLOR, "fontsize": 9}
        )
        legend_patches = [mpatches.Patch(color=COLORS[i], label=l)
                          for i, l in enumerate(labels)]
        ax2.legend(handles=legend_patches, loc="center left",
                   bbox_to_anchor=(-0.35, 0.5), fontsize=8,
                   facecolor=CARD_COLOR, edgecolor="#3D3D5C",
                   labelcolor=TEXT_COLOR)
    else:
        ax2.text(0.5, 0.5, "Aucune donnee", ha="center", va="center",
                 color=TEXT_COLOR, fontsize=12)
    ax2.set_title("Repartition par Clinique", color=TEXT_COLOR, fontsize=12, pad=10)

    # ── Row 3: Top diagnoses ──────────────────────────────────────────────────
    ax3 = fig.add_axes([0.06, 0.04, 0.9, 0.28], facecolor=CARD_COLOR)
    diag_counts = stats.get("diag_counts", {})
    if diag_counts:
        # Top 10 diagnoses
        sorted_diags = sorted(diag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        labels = [d[0][:35] for d in sorted_diags]
        values = [d[1] for d in sorted_diags]
        bars = ax3.bar(range(len(labels)), values, color=COLORS[:len(labels)], width=0.6)
        ax3.set_xticks(range(len(labels)))
        ax3.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
        ax3.set_ylabel("Nombre", color=TEXT_COLOR, fontsize=9)
        for bar, val in zip(bars, values):
            ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1,
                     str(val), ha="center", color=TEXT_COLOR, fontsize=10)
    else:
        ax3.text(0.5, 0.5, "Aucune donnee", ha="center", va="center",
                 color=TEXT_COLOR, fontsize=12)
    ax3.set_title("Diagnostics les plus frequents", color=TEXT_COLOR, fontsize=12, pad=10)
    ax3.tick_params(colors=TEXT_COLOR, labelsize=9)
    for spine in ax3.spines.values():
        spine.set_color("#3D3D5C")

    # ── Save ──────────────────────────────────────────────────────────────────
    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)
    return output_path


def generate_dashboard_bytes(stats: dict) -> bytes:
    """Generate dashboard and return as bytes (for sending via Telegram)."""
    path = generate_dashboard(stats)
    with open(path, "rb") as f:
        return f.read()
