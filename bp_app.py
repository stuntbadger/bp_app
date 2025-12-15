import io
import os
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.express as px
import matplotlib.pyplot as plt

CSV_PATH = "bp_readings.csv"

st.set_page_config(page_title="Blood Pressure Monitor", page_icon="🩺", layout="wide")
st.title("Blood Pressure Monitoring")

# ---------- Data utilities ----------
def load_data():
    if not os.path.exists(CSV_PATH):
        df = pd.DataFrame(columns=["datetime", "systolic", "diastolic", "pulse", "notes"])
        df.to_csv(CSV_PATH, index=False)
        return df
    df = pd.read_csv(CSV_PATH)
    if not df.empty:
        # Ensure types
        df["datetime"] = pd.to_datetime(df["datetime"])
        for col in ["systolic", "diastolic", "pulse"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def save_data(df):
    df.to_csv(CSV_PATH, index=False)

def add_reading(dt, sys, dia, pulse, notes):
    df = load_data()
    new = pd.DataFrame([{
        "datetime": dt,
        "systolic": int(sys),
        "diastolic": int(dia),
        "pulse": int(pulse),
        "notes": notes
    }])
    df = pd.concat([df, new], ignore_index=True)
    save_data(df)
    return df

def validate(sys, dia, pulse):
    # Simple sanity checks (general info only)
    if not (50 <= sys <= 250): st.warning("Systolic looks unusual. Check entry.")
    if not (30 <= dia <= 150): st.warning("Diastolic looks unusual. Check entry.")
    if not (30 <= pulse <= 200): st.warning("Pulse looks unusual. Check entry.")

# ---------- Sidebar: Settings ----------
st.sidebar.header("Settings")
target_sys_max = st.sidebar.number_input("Alert systolic above", value=140, step=1)
target_dia_max = st.sidebar.number_input("Alert diastolic above", value=90, step=1)
rolling_days = st.sidebar.number_input("Rolling average (days)", value=7, min_value=1, step=1)

# ---------- Entry form ----------
st.subheader("Add a reading")
col1, col2 = st.columns(2)

with col1:
    d = st.date_input("Date", value=datetime.now().date())
    t = st.time_input("Time", value=datetime.now().time().replace(microsecond=0))
with col2:
    sys = st.number_input("Systolic (mmHg)", min_value=0, max_value=300, step=1)
    dia = st.number_input("Diastolic (mmHg)", min_value=0, max_value=200, step=1)
pulse = st.number_input("Pulse (bpm)", min_value=0, max_value=250, step=1)
notes = st.text_input("Notes (optional)")

if st.button("Save reading"):
    validate(sys, dia, pulse)
    dt = datetime.combine(d, t)
    df = add_reading(dt, sys, dia, pulse, notes)
    st.success("Saved!")
else:
    df = load_data()

# ---------- Filter and table ----------
st.subheader("Your readings")
if df.empty:
    st.info("No readings yet. Add your first one above.")
else:
    colf1, colf2, colf3, colf4 = st.columns(4)
    with colf1:
        start_date = st.date_input("Start date", value=df["datetime"].min().date())
    with colf2:
        end_date = st.date_input("End date", value=df["datetime"].max().date())
    with colf3:
        am_pm = st.selectbox("Time of day", ["All", "AM (00:00–11:59)", "PM (12:00–23:59)"])
    with colf4:
        show_pulse = st.checkbox("Show pulse", value=True)

    mask = (df["datetime"].dt.date >= start_date) & (df["datetime"].dt.date <= end_date)
    if am_pm == "AM (00:00–11:59)":
        mask &= (df["datetime"].dt.hour < 12)
    elif am_pm == "PM (12:00–23:59)":
        mask &= (df["datetime"].dt.hour >= 12)
    view = df.loc[mask].copy().sort_values("datetime")

    #st.dataframe(view, use_container_width=True)
    edited_view = st.data_editor(
        view,
        use_container_width=True,
        num_rows="dynamic",
        disabled=["datetime"], 
        key="editor"
    )
    if st.button("Save edits"):
       # Keep only rows still present after editing
       df = df.merge(
           edited_view,
           on=["datetime", "systolic", "diastolic", "pulse", "notes"],
           how="right"
    )

    # Ensure correct dtypes
    df["datetime"] = pd.to_datetime(df["datetime"])
    for col in ["systolic", "diastolic", "pulse"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    save_data(df)
    st.success("Edits & deletions saved")

    # ---------- Derived metrics ----------
    daily = view.copy()
    daily["date"] = daily["datetime"].dt.date

    # Ensure numeric types before grouping (fixes dtype->object issues)
    for col in ["systolic", "diastolic", "pulse"]:
        daily[col] = pd.to_numeric(daily[col], errors="coerce")

    daily_avg = daily.groupby("date")[["systolic", "diastolic", "pulse"]].mean().reset_index()

    # Rolling average (on daily averages)
    rolling = None
    if not daily_avg.empty:
        daily_avg = daily_avg.set_index(pd.to_datetime(daily_avg["date"]))
        daily_avg.index.name = "date_index"   # avoid clash with 'date' column
        daily_avg.sort_index(inplace=True)
        rolling = daily_avg[["systolic", "diastolic"]].rolling(f"{rolling_days}D").mean()

    # ---------- Graphs ----------
    st.subheader("Graphs")
    tabs = st.tabs(["All readings", "Daily averages", f"Rolling {rolling_days}-day", "Pulse"])

    # All readings tab
    with tabs[0]:
        if view.empty:
            st.info("No readings available in this range.")
        else:
            fig = px.scatter(
                view, x="datetime", y="systolic", color_discrete_sequence=["#1f77b4"],
                labels={"systolic":"Systolic (mmHg)", "datetime":"Date/Time"},
                title="Systolic vs time"
            )
            fig.add_scatter(x=view["datetime"], y=view["diastolic"],
                            name="Diastolic", mode="markers", marker=dict(color="#ff7f0e"))
            fig.add_hline(y=target_sys_max, line_dash="dot", line_color="#1f77b4", annotation_text="Systolic alert")
            fig.add_hline(y=target_dia_max, line_dash="dot", line_color="#ff7f0e", annotation_text="Diastolic alert")
            st.plotly_chart(fig, use_container_width=True)

            # Export PNG for this chart
            buf_png = io.BytesIO()
            fig.write_image(buf_png, format="png")
            st.download_button("Download PNG (all readings)", data=buf_png.getvalue(), file_name="bp_all_readings.png")

    # Daily averages tab
    with tabs[1]:
        if daily_avg.empty:
            st.info("Not enough data for daily averages.")
        else:
            fig2 = px.line(
                daily_avg.reset_index(),
                x="date_index", y=["systolic", "diastolic"],
                labels={"value":"mmHg", "date_index":"Date"},
                title="Daily average blood pressure"
            )
            st.plotly_chart(fig2, use_container_width=True)
            buf_png2 = io.BytesIO()
            fig2.write_image(buf_png2, format="png")
            st.download_button("Download PNG (daily averages)", data=buf_png2.getvalue(), file_name="bp_daily_avg.png")

    # Rolling averages tab
    with tabs[2]:
        if daily_avg.empty or rolling is None:
            st.info("Not enough data for rolling averages.")
        else:
            fig3 = px.line(
                rolling.reset_index(),
                x="date_index", y=["systolic", "diastolic"],
                labels={"value":"mmHg", "date_index":"Date"},
                title=f"Rolling {rolling_days}-day average"
            )
            st.plotly_chart(fig3, use_container_width=True)
            buf_png3 = io.BytesIO()
            fig3.write_image(buf_png3, format="png")
            st.download_button("Download PNG (rolling averages)", data=buf_png3.getvalue(), file_name="bp_rolling_avg.png")

    # Pulse tab
    with tabs[3]:
        if not show_pulse or view.empty:
            st.info("Enable 'Show pulse' and ensure data is available.")
        else:
            fig4 = px.line(view, x="datetime", y="pulse",
                           labels={"pulse":"Pulse (bpm)", "datetime":"Date/Time"},
                           title="Pulse trend")
            st.plotly_chart(fig4, use_container_width=True)
            buf_png4 = io.BytesIO()
            fig4.write_image(buf_png4, format="png")
            st.download_button("Download PNG (pulse)", data=buf_png4.getvalue(), file_name="pulse_trend.png")

# ---------- Printable report (PDF) ----------
st.subheader("Printable report")
if df.empty:
    st.info("Add readings to generate a report.")
else:
    include_notes = st.checkbox("Include latest notes", value=True)
    report_btn = st.button("Generate PDF report")
    if report_btn:
        view = df.sort_values("datetime").copy()
        # Ensure numeric types for summary stats
        for col in ["systolic", "diastolic", "pulse"]:
            view[col] = pd.to_numeric(view[col], errors="coerce")

        sys_mean = view["systolic"].mean()
        dia_mean = view["diastolic"].mean()
        pulse_mean = view["pulse"].mean()

        sys_max = view["systolic"].max()
        dia_max = view["diastolic"].max()
        pulse_max = view["pulse"].max()

        # Matplotlib A4 portrait figure
        fig, ax = plt.subplots(2, 1, figsize=(8.27, 11.69))
        ax[0].plot(view["datetime"], view["systolic"], label="Systolic", color="#1f77b4")
        ax[0].plot(view["datetime"], view["diastolic"], label="Diastolic", color="#ff7f0e")
        ax[0].plot(view["datetime"], view["pulse"], label="Pulse", color="#2ca02c")
        ax[0].axhline(target_sys_max, ls="--", color="#1f77b4")
        ax[0].axhline(target_dia_max, ls="--", color="#ff7f0e")
        ax[0].set_title("Blood Pressure Over Time")
        ax[0].set_ylabel("mmHg / bpm")
        ax[0].legend()

        ax[1].axis("off")
        lines = [
            "Summary:",
            f"- Average BP: {sys_mean:.1f}/{dia_mean:.1f} mmHg",
            f"- Average Pulse: {pulse_mean:.1f} bpm",
            f"- Highest BP: {sys_max:.0f}/{dia_max:.0f} mmHg",
            f"- Highest Pulse: {pulse_max:.0f} bpm",
            f"- Readings: {len(view)}",
        ]
        if include_notes:
            last_notes = view.iloc[-1]["notes"] if len(view) and isinstance(view.iloc[-1]["notes"], str) else ""
            if last_notes:
                lines.append(f"- Latest notes: {last_notes}")

        text = "\n".join(lines)
        ax[1].text(0.02, 0.98, text, va="top", ha="left", fontsize=11)

        pdf_bytes = io.BytesIO()
        fig.tight_layout()
        fig.savefig(pdf_bytes, format="pdf")
        plt.close(fig)
        st.download_button(
            "Download PDF report",
            data=pdf_bytes.getvalue(),
            file_name="bp_report.pdf",
            mime="application/pdf"
        )

