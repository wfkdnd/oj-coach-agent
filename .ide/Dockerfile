FROM cnbcool/default-dev-env:latest

USER root

RUN echo "CUSTOM_DOCKERFILE_BUILD_MARKER"

ENV DEBIAN_FRONTEND=noninteractive
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV LANG=C.UTF-8
ENV LANGUAGE=C.UTF-8

# Keep Python from the base image, then add the system toolchains used by OJ tasks.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    openjdk-17-jdk

RUN python3 --version \
    && g++ --version \
    && java -version \
    && javac -version
