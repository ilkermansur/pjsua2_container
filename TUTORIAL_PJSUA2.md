# 📞 PJSUA2 Python Tutorial: Arama Yapma ve Ses Oynatma

PJSUA2, PJSIP VoIP kütüphanesinin C++ tabanlı nesne yönelimli API'sidir ve Python SWIG sarmalayıcısı (wrapper) ile Python üzerinden kontrol edilir.

Bu dökümanda, herhangi bir web API'si (FastAPI) olmadan, doğrudan Python üzerinden PJSIP ile nasıl arama yapılacağını, ses dosyasının nasıl oynatılacağını ve DTMF tuş vuruşlarının nasıl yakalanacağını öğreneceksiniz.

---

## 1. Temel Bileşenler ve Yaşam Döngüsü

Bir PJSUA2 uygulamasının çalışması için sırasıyla şu adımların atılması gerekir:

1.  **Endpoint (`pj.Endpoint`)**: PJSIP'in kalbidir. Kütüphane oluşturulur, başlatılır ve start edilir.
2.  **Null Audio Device**: Konteyner/sunucu ortamlarında ses kartı bulunmadığı için PJSIP'in çökmesini önlemek üzere sanal bir boş ses cihazı tanımlanır.
3.  **Transport**: SIP sinyalleşmesini taşımak için UDP (port 5060) tanımlanır.
4.  **Account (`pj.Account`)**: Dışarı arama yapabilmek için en az bir hesap tanımlanmalıdır (SIP sunucusuna kayıt olmak şart değildir, anonim hesap kullanılabilir).
5.  **Call (`pj.Call`)**: Arama nesnesidir. Çağrı durum güncellemelerini almak için bu sınıf miras alınarak genişletilir.

---

## 2. Yalın Arama Scripti (Standalone Python Örneği)

Aşağıdaki scripti projenizdeki `sounds` klasöründe hazır bir `.wav` dosyası varken çalıştırabilirsiniz. Bu kod FastAPI bağımlılığı olmadan doğrudan çağrı başlatır:

```python
import pjsua2 as pj
import time
import sys

# 1. Custom Call Sınıfı Tanımlama (Olayları Yakalamak İçin)
class MyCall(pj.Call):
    def __init__(self, acc, call_id=pj.PJSUA_INVALID_ID, audio_file=None):
        super().__init__(acc, call_id)
        self.audio_file = audio_file
        self.player = None
        self.is_disconnected = False

    # Arama Durum Güncellemeleri
    def onCallState(self, prm):
        ci = self.getInfo()
        print(f"-> Arama Durumu: {ci.stateText} (Kod: {ci.state})")
        if ci.state == pj.PJSIP_INV_STATE_DISCONNECTED:
            self.is_disconnected = True
            if self.player:
                self.player = None  # Kaynağı serbest bırak

    # Medya Durum Güncellemeleri (Arama Cevaplandığında)
    def onCallMediaState(self, prm):
        ci = self.getInfo()
        for i in range(len(ci.media)):
            # Audio kanalını bul
            if ci.media[i].type == pj.PJMEDIA_TYPE_AUDIO:
                # Çağrının ses kanalını al
                aud_med = pj.AudioMedia.typecastFromMedia(self.getMedia(i))
                
                # Ses oynatıcıyı başlat
                if self.audio_file and not self.player:
                    print(f"-> Arama açıldı. {self.audio_file} çalınıyor...")
                    self.player = pj.AudioMediaPlayer()
                    self.player.createPlayer(self.audio_file, pj.PJMEDIA_FILE_NO_LOOP)
                    # Oynatıcıyı çağrının ses kanalına bağla (Transmit)
                    self.player.startTransmit(aud_med)

    # DTMF Tuşlama Yakalama
    def onDtmfDigit(self, prm):
        print(f"-> Kullanıcı tuşa bastı: {prm.digit}")
        if prm.digit == '0':
            print("-> 0 basıldı, kapatılıyor...")
            self.hangup(pj.CallOpParam(True))

# 2. PJSIP Motorunun Başlatılması
ep = pj.Endpoint()
ep.libCreate()

ep_cfg = pj.EpConfig()
ep_cfg.uaConfig.threadCnt = 1  # Konteyner için tek iş parçacığı
ep.libInit(ep_cfg)

# Headless ortamlar için ses kartını sanallaştır
ep.audDevManager().setNullDev()

# Transport oluştur
transport_cfg = pj.TransportConfig()
transport_cfg.port = 5060
ep.transportCreate(pj.PJSIP_TRANSPORT_UDP, transport_cfg)

# Motoru çalıştır
ep.libStart()

# 3. Anonim Çıkış Hesabı Tanımlama
acc_cfg = pj.AccountConfig()
acc_cfg.idUri = "sip:callagent@localhost"
acc = pj.Account()
acc.create(acc_cfg)

# 4. Aramayı Tetikleme
target_sip_uri = "sip:1001@192.168.60.6"  # Hedef SIP adresi
wav_file_path = "/app/sounds/anons.wav"    # Çalınacak dosya (pcm 8000hz)

# Thread kaydı yap (Python arka plan işlemleri için zorunludur)
ep.libRegisterThread("main_thread")

call = MyCall(acc, audio_file=wav_file_path)
call_prm = pj.CallOpParam(True)

print(f"Arama başlatılıyor: {target_sip_uri}")
call.makeCall(target_sip_uri, call_prm)

# Çağrı sonlanana kadar scripti açık tut
while not call.is_disconnected:
    try:
        time.sleep(0.5)
    except KeyboardInterrupt:
        print("Kullanıcı tarafından kesildi. Çağrı kapatılıyor...")
        call.hangup(pj.CallOpParam(True))
        break

# PJSIP motorunu temiz kapat
ep.libDestroy()
```

---

## 3. Kod İçerisindeki Kritik Metotlar

*   **`pj.AudioMediaPlayer()`**: Disk üzerindeki bir `.wav` dosyasını okuyup PJSUA2 konferans köprüsüne (Conference Bridge) aktaran sınıftır.
*   **`player.createPlayer(path, options)`**: Oynatılacak ses dosyasını yükler. İkinci parametre `pj.PJMEDIA_FILE_NO_LOOP` verilirse ses tek sefer çalınır, `0` verilirse sonsuz döngüde çalar.
*   **`player.startTransmit(call_audio_media)`**: Oynatıcıyı (Source), hedefin ses kanalına (Sink/Destination) bağlar. Sesin karşı tarafa akmasını sağlayan asıl komut budur.
*   **`ep.libRegisterThread("thread_name")`**: C++ tabanlı PJSIP kütüphanesi iş parçacığı güvenliğine (thread-safety) çok önem verir. Python'da yeni bir thread açıp içinde PJSIP komutları (arama yapma, ses çalma vb.) çalıştıracaksanız, o thread'i mutlaka PJSIP motoruna kaydettirmelisiniz. Aksi halde C++ seviyesinde segfault çökmesi yaşanır.
