FROM python:3.12-slim

USER root
RUN pip install poetry
RUN useradd -m -s /bin/bash app_user

USER app_user
WORKDIR /home/app_user/app
COPY poetry.lock .
COPY pyproject.toml .

RUN poetry install --only main --no-root
COPY . .
RUN poetry install --only main

CMD [ "poetry", "run", "python", "pipdepgraph/main.py" ]
