# Backend image: FastAPI + faster-whisper on the interpreter the test suite runs
# (3.11; every pinned dependency ships a cp311 wheel, so no compiler stage needed).
FROM python:3.11-slim

# Whisper models download into HF_HOME on first use; compose mounts a volume here
# so the ~1.5 GB medium model survives container rebuilds.
ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/cache/hf

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app

# Non-root: /data (sqlite) and /cache (whisper) must stay writable by this user,
# so create and chown them in the image; the named volumes inherit the ownership.
RUN useradd --create-home appuser \
    && mkdir -p /data /cache/hf \
    && chown -R appuser:appuser /data /cache /code
USER appuser

# stdlib healthcheck: slim has no curl/wget.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"]

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
