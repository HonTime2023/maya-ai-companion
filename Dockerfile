# Containerizes the webapp (FastAPI WebSocket proxy + browser UI).
# The native voice pipeline (ai_companion/main.py) needs direct host
# microphone/speaker access and Raspberry Pi GPIO in some modes, so it's
# meant to run natively rather than in this container — see README.
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "webapp.server:app", "--host", "0.0.0.0", "--port", "8000"]
