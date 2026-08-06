FROM python:3.10-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    portaudio19-dev \
    libasound2-dev \
    ffmpeg \
    espeak \
    libespeak1 \
    tk-dev \
    libx11-xcb1 \
    libxcb-xfixes0 \
    libxrender1 \
    libxext6 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxcursor1 \
    libxi6 \
    libxinerama1 \
    libxft2 \
    libxss1 \
    libxtst6 \
    libxkbcommon-x11-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set python environment variables
ENV PYTHONUNBUFFERED=1

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download and cache model weights (Whisper & openWakeWord)
COPY download_models.py .
RUN python download_models.py && rm download_models.py

# Copy the rest of the project files
COPY . .

# Expose single-instance listener socket port
EXPOSE 54321

# Default command runs the main assistant loop
CMD ["python", "main.py"]
