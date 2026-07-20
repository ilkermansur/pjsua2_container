# Standalone PJSUA2 VoIP Call Agent Container

This directory contains a standalone, API-driven VoIP calling agent container built on top of **PJSIP (PJSUA2)** and **FastAPI** in Python. It is optimized to run inside headless environments (like Docker containers or remote servers) without physical audio hardware.

For a detailed step-by-step walkthrough of how this PJSIP container is compiled and built, see [README_BUILD.md](README_BUILD.md).

---

## 🚀 Features

*   **PJSIP 2.14 Compilation**: Compiles the standard PJSIP library and its Python SWIG bindings directly from source on the target architecture (fully supports `x86_64` and `arm64/Apple Silicon`).
*   **Null Audio Device Enabler**: Automatically configures the endpoint with `audDevManager().setNullDev()` to prevent `PJMEDIA_EAUD_NODEFDEV` (Unable to find default audio device) crashes common in server environments.
*   **FastAPI REST API Interface**: Exposes a simple HTTP endpoint to trigger outbound SIP calls.
*   **Real-time Unbuffered Logs**: Configured with `PYTHONUNBUFFERED=1` to ensure PJSIP signaling and Python print logs are shown immediately in Docker outputs.
*   **Graceful Shut Down**: Background threads monitor call states and exit cleanly without causing session termination exceptions.

---

## 🛠️ Getting Started

### Prerequisites

*   Docker Desktop running on your machine.

### 1. Build the Docker Image
Navigate to this directory (or run from the project root referencing this folder) and build the image:
```bash
docker build -t pjsua2-call-agent .
```
*(Note: Compiling PJSIP from source will take 3-7 minutes during the initial build.)*

### 2. Run the Container
Start the container exposing the FastAPI server on port `8000`:
```bash
docker run -d --name voip-agent -p 8000:8000 pjsua2-call-agent
```

---

## 📞 Usage & API Reference

### Trigger a Call
To initiate a SIP call, send an HTTP `POST` request to `/api/call` with the target SIP URI:

```bash
curl -X POST http://localhost:8000/api/call \
  -H "Content-Type: application/json" \
  -d '{
    "target_uri": "sip:1001@your-sip-domain.com",
    "caller_id": "CustomAgent"
  }'
```

### Response
```json
{
  "status": "initiated",
  "target": "sip:1001@your-sip-domain.com",
  "message": "Call thread spawned. Watch container logs for SIP state updates."
}
```

### Inspect Call States (Logs)
To watch the call progression (INVITE, ringing, answer, duration, disconnect codes):
```bash
docker logs -f voip-agent
```

---

## 🐳 Docker Hub Publishing

To tag and upload this image to your Docker Hub repository:

1.  Log in to Docker Hub:
    ```bash
    docker login
    ```
2.  Tag the compiled image with your username:
    ```bash
    docker tag pjsua2-call-agent your-username/pjsua2-call-agent:latest
    ```
3.  Push the image to the repository:
    ```bash
    docker push your-username/pjsua2-call-agent:latest
    ```
