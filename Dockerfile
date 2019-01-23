FROM python:3.7-slim

WORKDIR /app
COPY ./requirements.txt /app

RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
WORKDIR /app/image_mirror

ENV PYTHONPATH=/app/image_mirror
ENV PYTHONUNBUFFERED=0


EXPOSE 8000