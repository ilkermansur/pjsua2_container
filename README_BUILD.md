# PJSIP & PJSUA2 Docker Konteyneri Derleme Rehberi

Bu belge, oluşturduğumuz bağımsız **`pjsua2-call-agent`** Docker konteynerinin mimari kararlarını, derleme adımlarını ve VoIP süreçlerinin Docker ortamında kararlı çalışabilmesi için uygulanan çözümleri teknik detaylarıyla açıklamaktadır.

---

## 1. Mimari Kararlar ve İşletim Sistemi Seçimi

### Neden Alpine Değil de Debian Slim?
*   **Alpine Kısıtlamaları**: Alpine Linux, hafif olması için `musl libc` kullanır. Ancak PJSIP ve SWIG kütüphaneleri, C++ standart kütüphane bağlantılarını yaparken `musl` ile derleme aşamasında (özellikle Python bindings bağlarken) çok sık bellek hatası (segmentation fault) veya uyumsuzluk çıkarır.
*   **Debian Slim Kararlılığı**: `python:3.11-slim-bookworm` imajı, glibc tabanlıdır. PJSIP ve C++ derleyicileri ile %100 uyumludur. Gereksiz GUI ve ses sürücüsü paketlerini barındırmadığı için hem hafiftir hem de derleme sürecini sorunsuz tamamlar.

---

## 2. Derleme Bağımlılıkları (Prerequisites)

Konteynerin PJSIP'i kaynak kodundan derleyebilmesi için `apt-get` ile kurulan paketler ve görevleri:

*   **`build-essential`**: `gcc`, `g++` ve `make` araçlarını barındırır. C++ kaynak kodunu derlemek için zorunludur.
*   **`swig`**: PJSIP'in C++ kodunu Python kütüphanesine (`pjsua2` modülü) dönüştürmek için kullanılan kod üreticidir.
*   **`libssl-dev`**: SIP sinyalleşmesinde TLS/SRTP şifrelemesi (güvenli çağrı) için gereklidir.
*   **`libasound2-dev`**: PJSIP'in ses alt yapısı (ALSA) ile haberleşebilmesi için gereken geliştirici başlık dosyalarıdır.
*   **`libpq-dev`**: İlerleyen adımlarda PostgreSQL bağlantısı eklenmek istendiğinde gereken veritabanı kütüphanesidir.

---

## 3. PJSIP ve Python Bindings Derleme Adımları

Dockerfile içerisinde kaynak kod derleme işlemi şu 3 aşamada gerçekleştirilir:

### A. PJSIP Kaynak Kodunun Derlenmesi
```bash
wget https://github.com/pjsip/pjproject/archive/refs/tags/2.14.tar.gz
tar -xzf 2.14.tar.gz && cd pjproject-2.14
./configure --enable-shared --disable-sound --disable-video --disable-opencore-amr
make dep && make && make install
ldconfig
```
*   `--enable-shared`: PJSIP kütüphanelerinin paylaşımlı (`.so`) olarak derlenmesini sağlar. Python bindings bu kütüphanelere dinamik olarak bağlanır.
*   `--disable-sound` & `--disable-video`: Sunucu ortamında fiziksel hoparlör/kamera olmayacağı için bu donanımların sürücü entegrasyonu kapatılarak derleme süresi kısaltılır.
*   `ldconfig`: Derlenen `.so` dosyalarının işletim sistemi tarafından tanınmasını sağlar.

### B. SWIG ile Python PJSUA2 Modülünün Üretilmesi
```bash
cd pjsip-apps/src/swig/python
make
```
Bu dizindeki `make` komutu, SWIG aracını çalıştırarak C++ sınıflarını analiz eder ve Python'ın import edebileceği `pjsua2.py` ile C++ arayüz dosyası olan `pjsua2_wrap.cpp` dosyalarını otomatik olarak üretir.

### C. Python Modülünün Kurulması
```bash
python setup.py install
```
Üretilen wrapper dosyaları derlenerek Python'ın `site-packages` dizinine `pjsua2` modülü olarak yüklenir.

---

## 4. Karşılaşılan Sorunlar ve Çözümleri

### 1. Ses Kartı Yok Hatası (`PJMEDIA_EAUD_NODEFDEV`)
*   **Sorun**: Docker konteynerleri varsayılan olarak bir ses kartına sahip değildir. PJSIP çağrı başlatırken hoparlör ve mikrofon aradığı için `Unable to find default audio device` hatası verip çökmekteydi.
*   **Çözüm**: API başlatıldığında endpoint yapılandırmasının hemen ardına aşağıdaki komut eklenerek PJSIP'in sanal bir "null" (boş) ses cihazı simülasyonu kullanması sağlandı:
    ```python
    ep.audDevManager().setNullDev()
    ```

### 2. Logların Ekrana Düşmemesi (Buffering)
*   **Sorun**: Docker konteynerlerinde Python'ın standart çıktıları (`print` ve PJSIP logları) varsayılan olarak arabelleğe (buffer) alınır ve konteyner durdurulana kadar `docker logs` üzerinde görünmez.
*   **Çözüm**: Dockerfile içerisine `ENV PYTHONUNBUFFERED=1` çevre değişkeni eklenerek logların terminale anlık akması sağlandı.

### 3. Çoklu Thread ve Segmentation Fault Hatası
*   **Sorun**: Python'ın Global Interpreter Lock (GIL) mekanizması ile PJSIP'in kendi C++ arka plan thread'leri çakıştığında Python çalışma zamanı çökebilmektedir.
*   **Çözüm**: 
    1.  Konteyner ortamı için thread limitini 1 olarak sabitledik:
        ```python
        ep_cfg.uaConfig.threadCnt = 1
        ```
    2.  Arka planda tetiklenen her Python thread'ini çalışmaya başlamadan önce SIP motoruna kaydettik:
        ```python
        ep.libRegisterThread("call_thread")
        ```
    3.  Arama sonlandığında, zaten yok edilmiş olan SIP oturumuna tekrar sorgu atmamak (`call.getInfo()`) için arama durumunu callback içerisindeki bir boolean flag (`self.is_disconnected`) üzerinden takip ederek thread'i güvenli şekilde sonlandırdık.
