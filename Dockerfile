FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY tender_monitor ./tender_monitor
ENV TZ=Asia/Jakarta PYTHONUNBUFFERED=1
CMD ["python", "-m", "tender_monitor", "-c", "/app/config.yaml", "loop"]
