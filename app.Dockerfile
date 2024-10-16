FROM python:3.12-slim

USER root
RUN useradd -m -s /bin/bash app_user

RUN pip install uv

WORKDIR /app
COPY Readme.md pyproject.toml requirements.lock ./
RUN uv pip install --system -r requirements.lock

COPY src src
RUN uv pip install --system .

USER app_user
