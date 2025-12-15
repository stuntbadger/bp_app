# Use official lightweight Python image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (for matplotlib/plotly image export)
RUN apt-get update && apt-get install -y \
    wget gnupg \
    build-essential \
    libgl1 \
    wget gnupg \
    && wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY bp_app.py .
COPY bp_readings.csv . 
# optional, if you want initial file

# Expose Streamlit default port
EXPOSE 8501

# Run the app
ENTRYPOINT ["streamlit", "run", "bp_app.py", "--server.port=8501", "--server.headless=true", "--server.enableCORS=false"]
