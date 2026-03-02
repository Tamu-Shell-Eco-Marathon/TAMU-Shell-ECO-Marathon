import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import subprocess
import os
import glob

# Set the page layout to wide (more space for graphs)
st.set_page_config(layout="wide", page_title="DIS Telemetry Viewer")

st.title("🏎️ Shell Eco-marathon Telemetry")

# --- SIDEBAR: CONTROLS ---
st.sidebar.header("Data Management")

# 1. THE DOWNLOAD BUTTON
# This runs the terminal command safely from the UI
if st.sidebar.button("⬇️ Download Logs from Pico"):
    with st.spinner("Connecting to Pico via mpremote..."):
        try:
            # We create a local folder for logs if it doesn't exist
            if not os.path.exists("downloaded_logs"):
                os.makedirs("downloaded_logs")
            
            # The mpremote command to copy the Logs folder
            # Note: We use 'cp -r' to get the whole folder
            cmd = ["mpremote", "fs", "cp", "-r", ":Logs/", "downloaded_logs/"]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                st.sidebar.success("Download Complete!")
            else:
                st.sidebar.error(f"Error: {result.stderr}")
                
        except FileNotFoundError:
            st.sidebar.error("mpremote not found. Is it installed?")

# 2. FILE SELECTOR
# Look for CSVs in the local folder
log_files = glob.glob("downloaded_logs/Logs/*.csv")
# Sort by newest first so the latest run is at the top
log_files.sort(key=os.path.getmtime, reverse=True)

if not log_files:
    st.info("No logs found. Connect the Pico and click 'Download Logs'.")
    st.stop() # Stop the script here if no files

selected_file = st.sidebar.selectbox("Select Test Run:", log_files)

# --- MAIN AREA: DATA VISUALIZATION ---

# Load the data
# We use caching so switching graphs doesn't reload the file every time
@st.cache_data
def load_data(filepath):
    return pd.read_csv(filepath)

try:
    df = load_data(selected_file)
    
    # Check if 'Time' is in the columns, if not, create an index
    if 'Time' not in df.columns:
        df['Time'] = df.index

    # 3. SIGNAL SELECTOR
    # Let the user pick which columns to graph (excluding Time)
    all_signals = [col for col in df.columns if col != 'Time']
    
    # Default to showing the first 2 signals if available
    default_signals = all_signals[:2] if len(all_signals) >= 2 else all_signals
    
    selected_signals = st.multiselect(
        "Select Signals to Plot:", 
        options=all_signals,
        default=default_signals
    )

    if not selected_signals:
        st.warning("Please select at least one signal to plot.")
    else:
        # 4. PLOTLY GRAPHING
        # Create a subplot with shared X-axis (The "Periscope" feature)
        fig = make_subplots(
            rows=len(selected_signals), cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=selected_signals
        )

        for i, signal in enumerate(selected_signals):
            fig.add_trace(
                go.Scatter(x=df['Time'], y=df[signal], name=signal),
                row=i+1, col=1
            )

        fig.update_layout(
            height=300 * len(selected_signals), # Auto-scale height
            hovermode="x unified", # The vertical cursor line
            showlegend=False,
            template="plotly_dark" # Dark mode
        )

        st.plotly_chart(fig, use_container_width=True)

        # Show raw data table below just in case
        with st.expander("View Raw Data"):
            st.dataframe(df)

except Exception as e:
    st.error(f"Error reading file: {e}")