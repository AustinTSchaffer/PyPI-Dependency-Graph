FROM python:3.12

USER root
RUN pip install poetry
RUN useradd -m -s /bin/bash app_user

USER app_user
WORKDIR /home/app_user/app
COPY poetry.lock .
COPY pyproject.toml .
RUN poetry install --no-root
COPY . .
RUN poetry install

CMD [ "poetry", "run", "python", "pipdepgraph/main.py" ]
