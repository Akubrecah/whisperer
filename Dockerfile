FROM python:3.11-slim

# Install system dependencies for GTK and Audio
RUN apt-get update && apt-get install -y \
    python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 \
    libgirepository1.0-dev gcc libcairo2-dev pkg-config \
    portaudio19-dev libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements (assuming you have a requirements.txt, if not we install manually)
COPY releases/whisper-dictator-core/pyproject.toml .
RUN pip install .

# Copy application code
COPY . .

# Set environment variables for display (requires running with X11 forwarding)
ENV DISPLAY=:0

CMD ["python3", "main.py"]
