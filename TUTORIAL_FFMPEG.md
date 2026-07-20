# 🎬 FFmpeg Tutorial: PJSIP Uyumlu Ses Dönüştürme

PJSIP kütüphanesi (ve SIP telefon hatları) ses dosyalarını oynatırken format konusunda son derece katıdır. Konteyner içerisindeki FFmpeg aracı, harici MP3 veya Piper tarafından üretilen ham WAV dosyalarını PJSIP standartlarına uygun hale getirmek için kullanılır.

---

## 1. PJSIP Ses Formatı Gereksinimi

PJSIP'in sorunsuz oynatabilmesi için ses dosyasının şu formatta olması şarttır:
*   **Format/Codec**: `PCM 16-bit signed Little-Endian (pcm_s16le)`
*   **Kanal Sayısı**: `1 (Mono)`
*   **Örnekleme Hızı (Sample Rate)**: `8000Hz` (G.711 standardı için) veya `16000Hz` / `32000Hz`
*   **Dosya Türü**: `.wav`

---

## 2. Temel Dönüştürme Komutu

Herhangi bir ses dosyasını (örneğin yüksek kaliteli bir `.mp3` veya Piper'ın ürettiği `.wav` dosyasını) PJSIP uyumlu formata çevirmek için aşağıdaki komutu kullanırız:

```bash
ffmpeg -y -i /app/sounds/girdi.mp3 \
  -acodec pcm_s16le \
  -ac 1 \
  -ar 8000 \
  /app/sounds/cikti.wav
```

### Parametrelerin Detaylı Açıklaması:
*   **`-y`**: Çıktı klasöründe aynı isimde bir dosya varsa sormadan üzerine yazar (Overwrite).
*   **`-i /app/sounds/girdi.mp3`**: Dönüştürülecek kaynak dosyanın yolunu belirtir (Girdi).
*   **`-acodec pcm_s16le`**: Ses sıkıştırma formatını PCM 16-bit Little-Endian olarak ayarlar.
*   **`-ac 1`**: Ses kanalını teke indirir (Mono). SIP çağrılarında çift kanal (stereo) ses desteklenmez.
*   **`-ar 8000`**: Ses örnekleme frekansını 8000Hz (8 kHz) yapar. Bu standart telefon bant genişliğidir.

---

## 3. Konteyner Dışından (Docker ile) Dönüştürme Yapmak

Bilgisayarınızdaki `sounds` klasörüne attığınız bir MP3 dosyasını konteyner içindeki FFmpeg aracılığıyla dönüştürmek için:

```bash
docker exec -it voip-agent ffmpeg -y -i /app/sounds/anons.mp3 -acodec pcm_s16le -ac 1 -ar 8000 /app/sounds/anons_hazir.wav
```

Bu işlem bittiğinde, klasörünüzde SIP aramalarında kullanıma hazır `anons_hazir.wav` dosyası oluşmuş olacaktır.
