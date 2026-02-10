FROM python:3.12-slim

WORKDIR /app

ENV FOREST_TYPE="s3"

ADD src ./src
ADD pyproject.toml .
ADD setup.py .

RUN apt-get update
RUN apt install -y libpq-dev gcc
RUN pip install --upgrade pip
RUN pip install . --no-cache-dir

EXPOSE 8000
ENTRYPOINT ["sh", "-c", "panel serve src/aind_qc_portal/portal.py src/aind_qc_portal/view.py --plugins aind_qc_portal.plugin --static-dirs images=src/aind_qc_portal/images --oauth-optional --address 0.0.0.0 --port 8000 --allow-websocket-origin ${ALLOW_WEBSOCKET_ORIGIN} --oauth-redirect-uri ${OAUTH_REDIRECT} --keep-alive 10000 --index portal.py --num-threads $(nproc) --admin"]