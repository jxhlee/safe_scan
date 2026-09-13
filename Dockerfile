FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt

COPY app ./app
COPY data ./data
COPY server.py ./

EXPOSE 7860

# Respects $PORT when the host platform injects one (Render, Railway, etc.);
# falls back to 7860 to match Hugging Face Spaces' app_port convention.
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-7860}"]
