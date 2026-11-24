# Образ локального сайта «Флористический центр» (Flask + psycopg2).
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000
EXPOSE 8000

CMD ["python", "main.py"]
