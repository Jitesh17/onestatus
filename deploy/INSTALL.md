# OneStatus install

Runs the app from prebuilt images. This folder (`docker-compose.yml`, `.env`,
this file) is all a machine needs; no source checkout required.

## 1. Docker Engine (skip if `docker --version` works)

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Log out and back in. Success signal: `docker run hello-world` prints
"Hello from Docker!".

## 2. Optional: NVIDIA GPU for the local model

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Success signal: `docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`
shows the GPU. The override file `docker-compose.gpu.yml` is already in this
folder; step 3 shows how to start with it.

## 3. Configure and start

```bash
cp .env.example .env
```

Edit `.env` and set `APP_PASSWORD`. The app refuses nobody without it; do not
skip this on a shared network.

```bash
docker compose up -d
docker compose exec ollama ollama pull qwen2.5:7b
```

With the GPU override:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

The model pull is one-time (about 4.7 GB, kept on a volume). Open
http://localhost:8080 and log in with the user and password from `.env`.
The first voice transcription downloads the speech model (about 1.5 GB);
later requests take seconds.

## 4. Operations

Update to the latest release:

```bash
docker compose pull && docker compose up -d
```

Logs:

```bash
docker compose logs -f backend
```

Back up the database (SQLite default):

```bash
docker compose cp backend:/data/onestatus.db ./onestatus-backup.db
```

Reset everything, deleting all entered data. Confirm before running:

```bash
docker compose down -v
```

## 5. If something does not work

| Symptom | Fix |
|---|---|
| Port 8080 already in use | set `FRONTEND_PORT` in `.env`, `docker compose up -d` |
| Login prompt loops | password changed in `.env` needs `docker compose up -d` to re-create the frontend container |
| Extraction errors mention the model | run the `ollama pull` command from step 3 |
| First voice request very slow | one-time speech model download; wait it out once |
