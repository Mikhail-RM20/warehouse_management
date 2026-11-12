FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r /app/requirements.txt

COPY core /app/core/
COPY database /app/database/
COPY images /app/images
COPY routes /app/routes/
COPY schemas /app/schemas/
COPY src /app/src/
COPY templates /app/templates/

COPY main.py /app/main.py
COPY seed.py /app/seed.py

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]