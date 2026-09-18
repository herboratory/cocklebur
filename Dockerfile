FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd -r -u 10001 popup && mkdir -p /data && chown -R popup:popup /data /app
USER popup
ENV POPUP_APP_MODE=server POPUP_DATA_DIR=/data POPUP_BASE_URL=http://127.0.0.1:8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--workers","1","--proxy-headers"]
