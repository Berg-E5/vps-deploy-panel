FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends openssh-client ca-certificates \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /srv/vpsdeploy
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd --system --uid 10001 --create-home vpsdeploy \
 && mkdir -p /srv/vpsdeploy/data \
 && chown -R vpsdeploy:vpsdeploy /srv/vpsdeploy/data
USER vpsdeploy
EXPOSE 8787
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787", "--workers", "1"]
