FROM python:3.12-slim

WORKDIR /app

ENV FOREST_TYPE="s3"
ENV PYTHONPATH="/app/src"

ADD src ./src
ADD pyproject.toml .
ADD setup.py .

RUN apt-get update
RUN apt install -y libpq-dev gcc
RUN pip install --upgrade pip
RUN pip install . --no-cache-dir

EXPOSE 8000
ENTRYPOINT ["sh", "-c", "panel serve src/aind_qc_portal/portal.py src/aind_qc_portal/view.py src/aind_qc_portal/status.py --plugins aind_qc_portal.plugin --static-dirs images=src/aind_qc_portal/images --oauth-optional --address 0.0.0.0 --port 8000 --allow-websocket-origin ${ALLOW_WEBSOCKET_ORIGIN:-localhost:8000} --oauth-redirect-uri ${OAUTH_REDIRECT:-http://localhost:8000} --keep-alive 10000 --index portal.py --num-threads $(nproc) --admin"]