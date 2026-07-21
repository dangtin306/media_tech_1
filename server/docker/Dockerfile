FROM ubuntu:22.04

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    QWEN_DOCKER=1 \
    CC=/usr/bin/gcc \
    CXX=/usr/bin/g++ \
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    QWEN_CPU_MAX_MEMORY=48GiB \
    QWEN_BASE_MODEL=/root/model/Qwen/Qwen3.5-4B \
    QWEN_BASE_MODEL_REPO=Qwen/Qwen3.5-4B \
    QWEN_LORA_ADAPTER=/root/model/Qwen/Qwen3.5-4B_vn_1/adapter \
    QWEN_OFFLOAD_DIR=/root/media_tech/ai/qwen/qwen3.5_4B_vn/server/offload

WORKDIR /root/media_tech

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        software-properties-common \
        gnupg gpg-agent \
        gcc g++ make curl openssh-client \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.11 python3.11-dev python3.11-venv \
    && ln -sf /usr/bin/python3.11 /usr/local/bin/python \
    && python -m ensurepip --upgrade \
    && rm -rf /var/lib/apt/lists/*

COPY server/docker/requirements.txt /tmp/requirements.txt

RUN mkdir -p /root/model/Qwen \
    /root/media_tech/ai/qwen/qwen3.5_4B_vn/server/offload

# Package the application source in the image; models and runtime data stay external.
COPY . /root/media_tech
COPY server/docker/adapter /opt/media-tech/adapter

WORKDIR /root/media_tech/ai/qwen/qwen3.5_4B_vn/server

COPY server/docker/entrypoint.sh /usr/local/bin/qwen-entrypoint
COPY server/docker/bootstrap_cuda.sh /usr/local/bin/bootstrap-cuda
RUN chmod +x /usr/local/bin/qwen-entrypoint
RUN chmod +x /usr/local/bin/bootstrap-cuda

EXPOSE 8005

ENTRYPOINT ["/usr/local/bin/qwen-entrypoint"]
CMD ["main.py"]
