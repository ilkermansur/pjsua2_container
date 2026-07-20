# 🎙️ Piper TTS Tutorial: Metinden Sese Çevirme (Text-to-Speech)

Piper, yerel cihazlarda çok hızlı çalışabilen, yüksek kaliteli ve optimize edilmiş açık kaynaklı bir yapay zeka metin-ses sentezleme (TTS) motorudur. Konteyner içerisine gömülü olarak gelir.

---

## 1. Çalışma Mantığı ve Gerekli Dosyalar

Piper'ın çalışabilmesi için iki temel dosyaya ihtiyacı vardır:
1.  **`.onnx` Dosyası**: Eğitilmiş ses modelinin kendisidir (Örn: `tr_TR-fahrettin-medium.onnx`).
2.  **`.json` Dosyası**: Sentezleme hızı, ses perdesi gibi konfigürasyonları tutan ayar dosyasıdır.

Konteyner içerisinde bu modeller varsayılan olarak şu dizinde yer alır:
*   `/app/models/tr_TR-fahrettin-medium.onnx`
*   `/app/models/tr_TR-fahrettin-medium.onnx.json`

---

## 2. Temel Kullanım (CLI)

Konteyner içerisindeki bash veya terminal arayüzünde Piper'ı tek başına tetiklemek için aşağıdaki komut yapısını kullanabilirsiniz:

```bash
echo "Okutulacak Türkçe metin buraya yazılır." | piper \
  --model /app/models/tr_TR-fahrettin-medium.onnx \
  --output_file /app/sounds/cikti.wav
```

### Parametre Açıklamaları:
*   `echo "..."`: Okutulacak metni Piper CLI aracına girdi (input) olarak borular (pipe `|`).
*   `--model`: Kullanılacak Türkçe ses modelinin ONNX dosya yolunu belirtir.
*   `--output_file`: Üretilen ses dosyasının kaydedileceği konumu ve adını belirtir.

---

## 3. Konteyner Dışından (Docker ile) Doğrudan Çalıştırma

Eğer konteyneri çalışır durumda tutuyorsanız (`voip-agent` adıyla), Docker üzerinden komut göndererek yerel sisteminize sese çevrilmiş dosya ürettirebilirsiniz:

```bash
docker exec -it voip-agent sh -c 'echo "Merhaba, Piper sistemi başarıyla çalışıyor." | piper --model /app/models/tr_TR-fahrettin-medium.onnx --output_file /app/sounds/deneme.wav'
```

Bu komutu çalıştırdıktan sonra, bilgisayarınızda konteynere bind ettiğiniz `sounds` klasöründe **`deneme.wav`** dosyasının oluştuğunu göreceksiniz.

---

## 4. Dikkat Edilmesi Gerekenler

*   **Desteklenen Format**: Piper varsayılan olarak **22050Hz (veya modele göre 16000Hz) Mono WAV** ses çıktısı üretir.
*   **PJSIP Uyumluluğu**: Piper'ın ürettiği bu ham ses dosyası PJSIP tarafından doğrudan okunamaz (PJSIP 8000Hz PCM bekler). Bu nedenle Piper çıktısının her zaman bir sonraki adımda **FFmpeg** ile dönüştürülmesi gerekir.
