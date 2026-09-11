FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV EXAMPLES_DIR=/srv/examples
ENV CATALOG_PATH=/srv/docs/prd_catalog.json
ENV OUTPUT_FOLDER=app/generated

COPY backend/requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

COPY backend/app /srv/app
COPY backend/prompts /srv/prompts
COPY examples /srv/examples
COPY docs /srv/docs

EXPOSE 9090
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9090"]
