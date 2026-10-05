FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/cocklebur/base
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY bootstrap /opt/cocklebur/bootstrap
RUN useradd -r -u 10001 popup && mkdir -p /data /opt/cocklebur && chown -R popup:popup /data /opt/cocklebur
USER popup
ENV POPUP_APP_MODE=server POPUP_DATA_DIR=/data POPUP_BASE_URL=http://127.0.0.1:8000 COCKLEBUR_MANAGED_RUNTIME=1 COCKLEBUR_RUNTIME_DIR=/data/.runtime
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=8s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["python","/opt/cocklebur/bootstrap/supervisor.py"]
