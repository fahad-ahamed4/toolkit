FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends p7zip-full unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /toolkit
COPY . /toolkit
RUN chmod +x /toolkit/run.sh /toolkit/install-deps.sh

ENTRYPOINT ["python3", "/toolkit/re_toolkit.py"]
