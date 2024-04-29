FROM python:3.11.4-slim-bullseye

RUN apt-get update && \
    apt-get install -y build-essential libffi-dev libssl-dev git make

ENV USER tycho
ENV HOME /home/$USER

RUN adduser --disabled-login --home $HOME --shell /bin/bash $USER

USER $USER
WORKDIR $HOME

ENV PATH=$HOME/.local/bin:$PATH

RUN mkdir app
COPY --chown=$USER . app/
WORKDIR $HOME/app

RUN /usr/bin/env python3 -m pip install --upgrade pip && \
	/usr/bin/env python3 -m pip install --upgrade wheel && \
	/usr/bin/env python3 -m pip install --upgrade setuptools && \
	/usr/bin/env python3 -m pip install -r requirements.txt && \
	/usr/bin/env python3 -m pip install .

ENV WORKERS=2
ENV APP_MODULE=tycho.api:app
ENV APP_NAME=tycho
ENV PORT=8099

ENV TYCHO=https://tycho.renci.org

ENTRYPOINT gunicorn --workers=$WORKERS --bind=0.0.0.0:$PORT --name=$APP_NAME --timeout=600 $APP_MODULE
