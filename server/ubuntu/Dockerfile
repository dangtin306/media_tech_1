FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    ROOT_PASSWORD=Matkhau@abc

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        openssh-server \
        bash \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /run/sshd

COPY entrypoint.sh /usr/local/bin/ubuntu-test-entrypoint
RUN chmod +x /usr/local/bin/ubuntu-test-entrypoint

EXPOSE 22

ENTRYPOINT ["/usr/local/bin/ubuntu-test-entrypoint"]
CMD ["/usr/sbin/sshd", "-D", "-e"]
