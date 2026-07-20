import uvicorn
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import pjsua2 as pj
import threading
import time
import subprocess
import uuid
import os

app = FastAPI(title="PJSUA2 VoIP Call Agent API")

class CallRequest(BaseModel):
    target_uri: str  # Örn: "sip:1001@your-sip-domain.com"
    caller_id: str = "CallAgent"
    media_file_name: str = None  # Örn: "merhaba.mp3" veya "anons.wav"
    text: str = None  # Örn: "Merhaba İlker Bey, nasılsınız?"

# PJSUA2 Call Class Override to receive events
class MyCall(pj.Call):
    def __init__(self, acc, call_id=pj.PJSUA_INVALID_ID, audio_file=None):
        super().__init__(acc, call_id)
        self.sip_call_id = None
        self.is_disconnected = False
        self.audio_file = audio_file
        self.player = None  # Persistent player instance to prevent garbage collection

    def onCallState(self, prm):
        try:
            ci = self.getInfo()
            self.sip_call_id = ci.callIdString
            print(f"==========================================")
            print(f"CALL STATE UPDATE:")
            print(f"  SIP Call ID : {self.sip_call_id}")
            print(f"  State Name  : {ci.stateText}")
            print(f"  State Code  : {ci.state}")
            print(f"  Last Reason : {ci.lastReason}")
            if ci.state == pj.PJSIP_INV_STATE_DISCONNECTED:
                print(f"  Duration    : {ci.connectDuration.sec} seconds")
                self.is_disconnected = True
                if self.player:
                    self.player = None  # Release file resource
            print(f"==========================================")
        except Exception as e:
            print(f"Error in onCallState callback: {e}")

    def onCallMediaState(self, prm):
        try:
            ci = self.getInfo()
            for i in range(len(ci.media)):
                if ci.media[i].type == pj.PJMEDIA_TYPE_AUDIO:
                    aud_med = pj.AudioMedia.typecastFromMedia(self.getMedia(i))
                    
                    if self.audio_file and not self.player:
                        print(f"Call Media: Opening audio file {self.audio_file}...")
                        self.player = pj.AudioMediaPlayer()
                        try:
                            # Load and play the file once (no looping)
                            self.player.createPlayer(self.audio_file, pj.PJMEDIA_FILE_NO_LOOP)
                            self.player.startTransmit(aud_med)
                            print("Call Media: Audio transmission started successfully.")
                        except Exception as player_err:
                            print(f"Error creating audio player: {player_err}")
        except Exception as e:
            print(f"Error in onCallMediaState callback: {e}")

# Global Endpoint & Account Configuration
ep = pj.Endpoint()
ep.libCreate()
ep_cfg = pj.EpConfig()
# Configure PJSIP Threading (thread limit set to 1 for containerized setups)
ep_cfg.uaConfig.threadCnt = 1
ep.libInit(ep_cfg)
# Set the null audio device to avoid audio hardware errors in headless containers
ep.audDevManager().setNullDev()

# Transport Configuration (UDP port 5060 for SIP signaling)
transport_cfg = pj.TransportConfig()
transport_cfg.port = 5060
ep.transportCreate(pj.PJSIP_TRANSPORT_UDP, transport_cfg)

ep.libStart()

# Default Account (Needed for making outbound calls even without active SIP registration)
acc_cfg = pj.AccountConfig()
acc_cfg.idUri = "sip:callagent@localhost"
acc = pj.Account()
acc.create(acc_cfg)

def prepare_audio(media_file_name: str, text: str) -> str:
    """
    Prepares the audio file by running TTS (Piper) and/or FFmpeg conversion.
    Returns the absolute path to the ready-to-play WAV file, or None.
    """
    sounds_dir = "/app/sounds"
    os.makedirs(sounds_dir, exist_ok=True)
    
    # Case 1: TTS text is provided
    if text:
        # Determine the target filename
        if media_file_name:
            # Clean extension if provided, ensure it ends with .wav
            base_name = os.path.splitext(media_file_name)[0]
            final_name = f"{base_name}.wav"
        else:
            final_name = f"tts_{uuid.uuid4().hex}.wav"
            
        final_path = os.path.join(sounds_dir, final_name)
        temp_raw_path = os.path.join(sounds_dir, f"raw_{uuid.uuid4().hex}.wav")
        
        try:
            print(f"TTS: Generating speech for text: '{text}'...")
            # Run Piper to generate raw WAV (usually 22050Hz from Fahrettin model)
            piper_cmd = f'echo "{text}" | piper --model /app/models/tr_TR-fahrettin-medium.onnx --output_file {temp_raw_path}'
            subprocess.run(piper_cmd, shell=True, check=True)
            
            # Convert raw WAV to standard PJSIP format (PCM 8000Hz, mono)
            print(f"FFmpeg: Converting TTS audio to 8000Hz Mono WAV...")
            ffmpeg_cmd = f'ffmpeg -y -i {temp_raw_path} -acodec pcm_s16le -ac 1 -ar 8000 {final_path}'
            subprocess.run(ffmpeg_cmd, shell=True, check=True)
            
            # Clean up raw temp file
            if os.path.exists(temp_raw_path):
                os.remove(temp_raw_path)
                
            print(f"TTS: Final audio ready at {final_path}")
            return final_path
        except Exception as e:
            print(f"Error in TTS / FFmpeg generation: {e}")
            if os.path.exists(temp_raw_path):
                os.remove(temp_raw_path)
            return None

    # Case 2: Only media file is provided (needs check and potential conversion)
    elif media_file_name:
        input_path = os.path.join(sounds_dir, media_file_name)
        
        # If absolute path was sent directly
        if media_file_name.startswith("/"):
            input_path = media_file_name
            
        if not os.path.exists(input_path):
            print(f"Error: Input file {input_path} does not exist.")
            return None
            
        # Get extension
        ext = os.path.splitext(input_path)[1].lower()
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        final_name = f"{base_name}_converted.wav"
        final_path = os.path.join(sounds_dir, final_name)
        
        # If already converted and exists, we can reuse it
        if os.path.exists(final_path) and ext == ".wav":
            return final_path
            
        try:
            print(f"FFmpeg: Standardizing {os.path.basename(input_path)} to 8000Hz Mono WAV...")
            ffmpeg_cmd = f'ffmpeg -y -i {input_path} -acodec pcm_s16le -ac 1 -ar 8000 {final_path}'
            subprocess.run(ffmpeg_cmd, shell=True, check=True)
            print(f"FFmpeg: Conversion complete. Ready at {final_path}")
            return final_path
        except Exception as e:
            print(f"Error in FFmpeg conversion: {e}")
            return None
            
    return None

def make_call_thread(target_uri, media_file_name, text):
    # Register the Python background thread to the PJSIP engine
    ep.libRegisterThread("call_thread")
    audio_path = None
    try:
        # Prepare the audio in the background thread
        audio_path = prepare_audio(media_file_name, text)
        if not audio_path and (media_file_name or text):
            print("Worker: Failed to prepare audio. Proceeding with silent call.")
            
        call = MyCall(acc, audio_file=audio_path)
        call_prm = pj.CallOpParam(True)
        
        print(f"Worker: Initiating call to {target_uri}...")
        call.makeCall(target_uri, call_prm)
        
        # Keep the thread running until the call is disconnected
        while not call.is_disconnected:
            time.sleep(0.5)
        print(f"Worker: Call disconnected. Ending worker thread.")
        
        # Cleanup temporary TTS files (that start with tts_ and end with .wav)
        if audio_path and os.path.basename(audio_path).startswith("tts_"):
            try:
                print(f"Worker: Cleaning up temporary TTS file {audio_path}")
                os.remove(audio_path)
            except Exception as cleanup_err:
                print(f"Error cleaning up temp file: {cleanup_err}")
                
    except Exception as e:
        print(f"Exception in make_call_thread: {e}")
        if audio_path and os.path.basename(audio_path).startswith("tts_"):
            try:
                os.remove(audio_path)
            except:
                pass

@app.post("/api/call")
def trigger_call(request: CallRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(make_call_thread, request.target_uri, request.media_file_name, request.text)
    return {
        "status": "initiated",
        "target": request.target_uri,
        "media_file_name": request.media_file_name,
        "text": request.text,
        "message": "Call thread spawned. Audio preparation starting in background. Watch container logs for updates."
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
