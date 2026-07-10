FROM docker.cnb.cool/looc/default-dev-env:latest

ENV DEBIAN_FRONTEND=noninteractive
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV LANG=C.UTF-8

# Keep Python from the base image, then add the system toolchains used by OJ tasks.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    g++ \
    openjdk-17-jdk
