import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
import pjsua2 as pj
import time
import subprocess
import uuid
import os
import wave

app = FastAPI(title="PJSUA2 VoIP Call Agent API")

class CallRequest(BaseModel):
    target_uri: str  # Örn: "sip:1001@your-sip-domain.com"
    caller_id: str = "CallAgent"
    media_file_name: str = None  # Örn: "merhaba.mp3" veya "anons.wav"
    text: str = None  # Örn: "Merhaba İlker Bey, nasılsınız?"

# Helper to get WAV duration using standard wave module
def get_wav_duration(file_path):
    try:
        with wave.open(file_path, 'r') as f:
            frames = f.getnframes()
            rate = f.getframerate()
            duration = frames / float(rate)
            return duration
    except Exception as e:
        print(f"Error reading WAV duration: {e}")
        return 10.0  # fallback duration in seconds

# PJSUA2 Call Class Override to receive events and DTMF digits
class MyCall(pj.Call):
    def __init__(self, acc, call_id=pj.PJSUA_INVALID_ID, audio_file=None):
        super().__init__(acc, call_id)
        self.sip_call_id = None
        self.is_disconnected = False
        self.is_answered = False
        self.audio_file = audio_file
        self.player = None  # Persistent player instance to prevent garbage collection
        self.dtmf_action = None  # Tracks '0' or '1' keypresses
        self.pressed_1 = False  # Flag to track if user ever pressed 1 during the call

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
            
            if ci.state == pj.PJSIP_INV_STATE_CONFIRMED:
                self.is_answered = True
                
            elif ci.state == pj.PJSIP_INV_STATE_DISCONNECTED:
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

    def onDtmfDigit(self, prm):
        try:
            digit = prm.digit
            print(f"DTMF DIGIT RECEIVED: {digit}")
            if digit == '0':
                self.dtmf_action = '0'
                print("DTMF Action: User pressed 0. Hanging up the call.")
                # Hang up the call immediately
                call_prm = pj.CallOpParam(True)
                self.hangup(call_prm)
            elif digit == '1':
                self.dtmf_action = '1'
                self.pressed_1 = True
                print("DTMF Action: User pressed 1. Replay will trigger shortly.")
        except Exception as e:
            print(f"Error in onDtmfDigit callback: {e}")

    def replay_audio(self):
        try:
            ci = self.getInfo()
            for i in range(len(ci.media)):
                if ci.media[i].type == pj.PJMEDIA_TYPE_AUDIO:
                    aud_med = pj.AudioMedia.typecastFromMedia(self.getMedia(i))
                    
                    if self.player:
                        try:
                            self.player.stopTransmit(aud_med)
                        except:
                            pass
                        self.player = None
                        
                    print("Call Media: Replaying audio file...")
                    self.player = pj.AudioMediaPlayer()
                    self.player.createPlayer(self.audio_file, pj.PJMEDIA_FILE_NO_LOOP)
                    self.player.startTransmit(aud_med)
                    print("Call Media: Replay transmission started.")
        except Exception as e:
            print(f"Error in replay_audio: {e}")

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

def make_call_sync(target_uri, media_file_name, text):
    # Register the Python thread to the PJSIP engine
    ep.libRegisterThread("call_thread")
    
    # Append IVR prompt to text dynamically
    if text:
        text = text.strip()
        if not text.endswith(".") and not text.endswith("!"):
            text += "."
        text += " Kaydı tekrar dinlemek için bir e basın, çağrıyı sonlandırmak için sıfır a basın."
        
    attempts = 2  # Total attempts (1 original + 1 retry if fails/no-answer)
    audio_path = None
    
    for attempt in range(attempts):
        print(f"SyncCall: Attempt {attempt + 1}/{attempts} for target {target_uri}")
        
        # Prepare the audio file (run TTS and format conversion)
        audio_path = prepare_audio(media_file_name, text)
        if not audio_path:
            # Audio preparation failure counts as an error
            if attempt == attempts - 1:
                return "error"
            print("SyncCall: Audio preparation failed. Waiting 60 seconds to retry...")
            time.sleep(60)
            continue
            
        call = MyCall(acc, audio_file=audio_path)
        call_prm = pj.CallOpParam(True)
        
        try:
            print(f"SyncCall: Initiating call on attempt {attempt + 1}...")
            call.makeCall(target_uri, call_prm)
        except Exception as call_err:
            print(f"SyncCall: Exception during makeCall: {call_err}")
            if audio_path and os.path.basename(audio_path).startswith("tts_"):
                try: os.remove(audio_path)
                except: pass
                
            if attempt == attempts - 1:
                return "error"
            print("SyncCall: Call initiation failed. Waiting 60 seconds to retry...")
            time.sleep(60)
            continue
            
        # Monitor the call
        start_time = time.time()
        answered = False
        wav_duration = 10.0
        play_start = 0.0
        
        while not call.is_disconnected:
            time.sleep(0.1)
            
            # Detect call answer
            if call.is_answered and not answered:
                answered = True
                print("SyncCall: Call answered! Starting audio duration tracking.")
                wav_duration = get_wav_duration(audio_path)
                print(f"SyncCall: WAV Duration resolved to {wav_duration:.2f} seconds.")
                play_start = time.time()
                
            # If call is answered, monitor playback elapsed time
            if answered:
                elapsed = time.time() - play_start
                # Replay if user pressed 1 OR if playback reached the end (+ 4 seconds silence)
                if elapsed >= (wav_duration + 4.0) or call.dtmf_action == '1':
                    if call.dtmf_action == '1':
                        print("SyncCall: DTMF 1 detected. Replaying immediately.")
                    else:
                        print("SyncCall: Timeout reached. Replaying message by default.")
                        
                    call.replay_audio()
                    play_start = time.time()
                    call.dtmf_action = None  # Reset DTMF flag
            else:
                # Ringing timeout (45 seconds limit if not answered)
                if time.time() - start_time > 45:
                    print("SyncCall: Ringing timeout reached. Hanging up call.")
                    try:
                        call.hangup(pj.CallOpParam(True))
                    except:
                        pass
                    break
                    
        print(f"SyncCall: Attempt {attempt + 1} finished.")
        
        # Determine the outcome
        if call.dtmf_action == '0':
            result = "0 a basıldı"
        elif call.pressed_1:
            result = "1 e basıldı"
        elif answered:
            result = "kullanıcı tarafından kapatıldı"
        else:
            result = "cevap vermedi veya meşgul"
            
        # Cleanup temporary TTS files
        if audio_path and os.path.basename(audio_path).startswith("tts_"):
            try:
                print(f"SyncCall: Cleaning up temporary TTS file {audio_path}")
                os.remove(audio_path)
            except Exception as cleanup_err:
                print(f"Error cleaning up temp file: {cleanup_err}")
                
        # If call connected and successfully closed by user (cases 1, 2, 3), return immediately
        if result in ["0 a basıldı", "1 e basıldı", "kullanıcı tarafından kapatıldı"]:
            return result
            
        # Else if outcome is "cevap vermedi veya meşgul" (case 4) or "error" (case 5)
        # If this is the last attempt, return the result
        if attempt == attempts - 1:
            return result
            
        print(f"SyncCall: Call failed with status '{result}'. Waiting 60 seconds before retrying...")
        time.sleep(60)
        
    return "error"

@app.post("/api/call")
def trigger_call(request: CallRequest):
    # Execute the call synchronously and return the outcome
    result = make_call_sync(request.target_uri, request.media_file_name, request.text)
    return {
        "status": "completed",
        "target": request.target_uri,
        "result": result
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
