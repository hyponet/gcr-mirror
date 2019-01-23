FROM python:3.7-slim

WORKDIR /app
COPY ./requirements.txt /app

RUN pip install -r requirements.txt
COPY . /app

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=0


EXPOSE 8000