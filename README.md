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
Start the container exposing the FastAPI server on port `8000`. To play local audio files, map a folder containing your `.wav` files into the container:
```bash
docker run -d --name voip-agent -p 8000:8000 -v ./sounds:/app/sounds pjsua2-call-agent
```

---

## 📞 Usage & API Reference

### Trigger a Call

To initiate a SIP call, send an HTTP `POST` request to `/api/call`. The call runs **synchronously** and returns the final call outcome in the API response after the call ends.

#### Option A: Playing a Pre-recorded File
You can place any audio file (e.g., `.mp3`, `.wav`) in the `sounds/` directory. The container will automatically standardize it to the compliant format (`PCM 16-bit, 8000Hz, Mono WAV`) using **FFmpeg** before making the call:

```bash
curl -X POST http://localhost:8000/api/call \
  -H "Content-Type: application/json" \
  -d '{
    "target_uri": "sip:1001@your-sip-domain.com",
    "caller_id": "CustomAgent",
    "media_file_name": "announcement.mp3"
  }'
```

#### Option B: Synthesizing Text-to-Speech (TTS) with IVR
If you send raw text, the container will synthesize it into natural Turkish speech using **Piper TTS** (Fahrettin voice) and automatically append the interactive voice prompt: *"Kaydı tekrar dinlemek için 1'e basın, çağrıyı sonlandırmak için 0'a basın."*

```bash
curl -X POST http://localhost:8000/api/call \
  -H "Content-Type: application/json" \
  -d '{
    "target_uri": "sip:1001@your-sip-domain.com",
    "caller_id": "CustomAgent",
    "text": "Merhaba İlker Bey, sisteminiz başarıyla kuruldu."
  }'
```

---

### 🎛️ DTMF / IVR Interactive Behavior

*   **Key `1`**: Replays the audio message immediately.
*   **Key `0`**: Hangs up the call and returns `"0 a basıldı"` in the API response.
*   **No key pressed (Timeout)**: If the recording finishes and the user doesn't press anything within 4 seconds, the message **replays automatically** (defaulting to key `1`) and loops continuously.
*   **User hangs up**: If the recipient hangs up their phone without pressing `0`, the API returns `"kullanıcı tarafından kapatıldı"`.

---

### Response
```json
{
  "status": "completed",
  "target": "sip:1001@your-sip-domain.com",
  "result": "0 a basıldı"
}
```
*(Possible `result` outcomes: `"0 a basıldı"`, `"kullanıcı tarafından kapatıldı"`, `"cevap vermedi veya meşgul"`, or `"error: ..."`)*

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
