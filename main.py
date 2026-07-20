import uvicorn
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import pjsua2 as pj
import threading
import time

app = FastAPI(title="PJSUA2 VoIP Call Agent API")

class CallRequest(BaseModel):
    target_uri: str  # Örn: "sip:1001@your-sip-domain.com"
    caller_id: str = "CallAgent"

# PJSUA2 Call Class Override to receive events
class MyCall(pj.Call):
    def __init__(self, acc, call_id=pj.PJSUA_INVALID_ID):
        super().__init__(acc, call_id)
        self.sip_call_id = None
        self.is_disconnected = False

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
            print(f"==========================================")
        except Exception as e:
            print(f"Error in onCallState callback: {e}")

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

def make_call_thread(target_uri):
    # Register the Python background thread to the PJSIP engine
    ep.libRegisterThread("call_thread")
    try:
        call = MyCall(acc)
        call_prm = pj.CallOpParam(True)
        
        print(f"Worker: Initiating call to {target_uri}...")
        call.makeCall(target_uri, call_prm)
        
        # Keep the thread running until the call is disconnected
        while not call.is_disconnected:
            time.sleep(0.5)
        print(f"Worker: Call disconnected. Ending worker thread.")
    except Exception as e:
        print(f"Exception in make_call_thread: {e}")

@app.post("/api/call")
def trigger_call(request: CallRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(make_call_thread, request.target_uri)
    return {
        "status": "initiated",
        "target": request.target_uri,
        "message": "Call thread spawned. Watch container logs for SIP state updates."
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
