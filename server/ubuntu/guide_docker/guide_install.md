# Docker GPU Installation Guide

Guide for a real Ubuntu GPU VM or bare-metal host. The host must provide a working
NVIDIA driver and Docker daemon. A Clore marketplace container is not a Docker
host and cannot run Docker-in-Docker.

## 1. Check Ubuntu and NVIDIA

```bash
cat /etc/os-release
nvidia-smi
```

`nvidia-smi` must show the GPU before installing the Docker GPU runtime.

## 2. Install Docker Engine

Remove conflicting packages if present:

```bash
for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do
  sudo apt-get remove -y "$pkg" 2>/dev/null || true
done
```

Install Docker from the official Docker repository:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
```

Verify Docker:

```bash
sudo docker run --rm hello-world
```

Optional: use Docker without `sudo` after logging in again:

```bash
sudo usermod -aG docker "$USER"
newgrp docker
docker run --rm hello-world
```

## 3. Install NVIDIA Container Toolkit

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Test GPU access from a CUDA container:

```bash
sudo docker run --rm --gpus all \
  nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

## 4. Pull the Media Tech image

```bash
docker pull hustmedia/media-tech-qwen:latest
```

For reproducible deployments, prefer a version tag instead of `latest`.

## 5. Prepare the model directory

The image contains the application source but intentionally does not contain the
large model files. Prepare this layout on the Ubuntu host:

```text
/root/model/Qwen/Qwen3.5-4B
/root/model/Qwen/Qwen3.5-4B_vn_1/adapter
```

## 6. Run Flask

Set the application port outside this guide, for example with
`MEDIA_TECH_APP_PORT`, and keep the value consistent with the image/runtime.

```bash
docker run -d --name media-tech-qwen \
  --restart unless-stopped \
  --gpus all \
  -p "${MEDIA_TECH_APP_PORT}:${MEDIA_TECH_APP_PORT}" \
  -v /root/model:/root/model \
  hustmedia/media-tech-qwen:latest
```

The image entrypoint starts the CUDA/PyTorch bootstrap and then launches the
Qwen Flask service. The first start can take several minutes.

Check logs and the health endpoint:

```bash
docker logs -f media-tech-qwen
curl "http://127.0.0.1:${MEDIA_TECH_APP_PORT}/health"
```

## 7. SSH access

SSH is provided by the Ubuntu host or the cloud platform. Do not install a
second Docker daemon inside the Qwen container.

If a local Docker test container needs SSH, create it with the port mapping from
`config.json` at creation time:

```bash
docker run -d --name ubuntu-gpu-test \
  --gpus all \
  -p "${DOCKER_SSH_PORT_MAPPING}" \
  ubuntu:22.04 sleep infinity
```

To create and configure the test container automatically from `config.json`:

```powershell
$configPath = "D:\hustmedia\python\llms\media_tech\server\ubuntu\config.json"
$password = node -e "const c=require(process.argv[1]); process.stdout.write(c.ubuntu_test_password)" $configPath
$dockerPort = node -e "const c=require(process.argv[1]); process.stdout.write(c.ubuntu_test_dockerPort)" $configPath

docker run -d --name ubuntu-gpu-test --gpus all -p $dockerPort ubuntu:22.04 sleep infinity
docker exec ubuntu-gpu-test bash -lc "export DEBIAN_FRONTEND=noninteractive; apt-get update -qq && apt-get install -y -qq openssh-server && mkdir -p /run/sshd && echo 'root:$password' | chpasswd && printf '\\nPermitRootLogin yes\\nPasswordAuthentication yes\\n' >> /etc/ssh/sshd_config && /usr/sbin/sshd"
```

Enter it directly without SSH:

```bash
docker exec -it ubuntu-gpu-test bash
```

## 8. Local Docker Desktop Ubuntu test container

This section is for Docker Desktop on Windows, not for a Clore marketplace
container. Docker Desktop already owns the Docker daemon, so this Ubuntu test
container can use the host daemon through the Docker socket.

Recreate the test container with GPU access, the SSH mapping from `config.json`,
and Docker CLI access to the host daemon:

```powershell
docker rm -f ubuntu-gpu-test 2>$null

$configPath = "D:\hustmedia\python\llms\media_tech\server\ubuntu\config.json"
$dockerPort = node -e "const c=require(process.argv[1]); process.stdout.write(c.ubuntu_test_dockerPort)" $configPath

docker run -d --name ubuntu-gpu-test `
  --gpus all `
  --privileged `
  -p $dockerPort `
  -v /var/run/docker.sock:/var/run/docker.sock `
  ubuntu:22.04 sleep infinity
```

Enter the container:

```cmd
docker exec -it ubuntu-gpu-test bash
```

Install the full Docker package set. The container still uses the Docker
Desktop host daemon through the mounted socket; the inner daemon is not started.

```bash
apt-get update
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu jammy stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin \
  docker-compose-plugin
docker ps
docker pull hustmedia/media-tech-qwen:latest
```

Install and start SSH before attempting the SSH connection:

```bash
apt-get update
apt-get install -y openssh-server
mkdir -p /run/sshd
printf '\nPermitRootLogin yes\nPasswordAuthentication yes\n' >> /etc/ssh/sshd_config
sshd -t
pkill sshd || true
/usr/sbin/sshd
```

Set the root password from `config.json` without copying it into this guide:

```powershell
$configPath = "D:\hustmedia\python\llms\media_tech\server\ubuntu\config.json"
$password = node -e "const c=require(process.argv[1]); process.stdout.write(c.ubuntu_test_password)" $configPath
docker exec -e "ROOT_PASSWORD=$password" ubuntu-gpu-test bash -lc 'printf "root:%s\n" "$ROOT_PASSWORD" | chpasswd'
```

Test GPU access:

```bash
nvidia-smi
```

The socket mount lets the Ubuntu container control the Docker Desktop host. It
is intentionally powerful and must not be used with untrusted containers.

## 9. Remove the Ubuntu test container

Check the container before removing it:

```bash
docker ps -a --filter "name=ubuntu-gpu-test"
```

Stop and remove only this test container:

```bash
docker rm -f ubuntu-gpu-test
```

If the container was created with a different name, list all containers first:

```bash
docker ps -a
```

Optionally remove the Ubuntu base image after no container uses it:

```bash
docker image rm ubuntu:22.04
```

Do not run `docker system prune -a` unless all unused images and containers are
intended to be deleted.

If SSH needs to be configured again:

```bash
apt-get update
apt-get install -y openssh-server
mkdir -p /run/sshd
printf '\nPermitRootLogin yes\nPasswordAuthentication yes\n' >> /etc/ssh/sshd_config
pkill sshd || true
/usr/sbin/sshd
```

Set the root password from `config.json` instead of typing a second password:

```powershell
$configPath = "D:\hustmedia\python\llms\media_tech\server\ubuntu\config.json"
$password = node -e "const c=require(process.argv[1]); process.stdout.write(c.ubuntu_test_password)" $configPath
docker exec ubuntu-gpu-test bash -lc "echo 'root:$password' | chpasswd"
```

Connect from Windows through the mapped port:

```powershell
$configPath = "D:\hustmedia\python\llms\media_tech\server\ubuntu\config.json"
$sshCommand = node -e "const c=require(process.argv[1]); process.stdout.write(c.ubuntu_test_sshCommand)" $configPath
Invoke-Expression $sshCommand
```

All connection settings are defined in `config.json`; do not duplicate them in
this guide. Load the configuration from a Node.js script:

```javascript
const config = require("../config.json");
console.log(config.ubuntu_test_sshCommand);
```

## 10. Update workflow

Source-only changes can be tested directly on the host if the source is mounted.
Image changes require a new build and push:

```text
Windows: build image -> docker push
Cloud:   recreate/redeploy container -> Docker host pulls the new image
```

Pushing a new image does not modify an already-running container.
