FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persist SQLite DB outside the container
VOLUME ["/root/.agentixlens"]

EXPOSE 4317

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4317"]
