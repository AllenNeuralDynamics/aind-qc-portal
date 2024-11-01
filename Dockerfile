FROM python:3.11-slim

WORKDIR /app

ADD src ./src
ADD pyproject.toml .
ADD setup.py .

RUN apt-get update
RUN pip install --upgrade pip
RUN pip install . --no-cache-dir

EXPOSE 8000
ENTRYPOINT ["sh", "-c", "panel serve src/aind_qc_portal/qc_portal_app.py src/aind_qc_portal/qc_asset_app.py src/aind_qc_portal/qc_app.py --static-dirs images=src/aind_qc_portal/images --oauth-optional --address 0.0.0.0 --port 8000 --allow-websocket-origin ${ALLOW_WEBSOCKET_ORIGIN} --keep-alive 10000"]