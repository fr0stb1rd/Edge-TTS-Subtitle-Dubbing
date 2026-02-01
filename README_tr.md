# Edge TTS Altyazı Seslendirme (Numpy/Librosa)

[ 🇬🇧 English ](README.md)

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fr0stb1rd/Edge-TTS-Subtitle-Dubbing/blob/main/Edge_TTS_Subtitle_Dubbing.ipynb)

Bu araç, **SRT altyazılarını**, örnekleme hassasiyetinde ses işleme ile Microsoft Edge TTS kullanarak tek bir senkronize **ses dosyasına** dönüştürür. Oluşturulan sesin orijinal videonun süresiyle mükemmel bir şekilde eşleşmesini sağlamak ve zamanla oluşabilecek senkronizasyon kaymalarını önlemek için **Numpy** ve **Librosa** ile güçlendirilmiş katı bir **Zaman Dilimi Doldurma (Time-Slot Filling)** algoritması kullanır.

🔗 [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/fr0stb1rd/Edge-TTS-Subtitle-Dubbing/blob/main/Edge_TTS_Subtitle_Dubbing.ipynb) \| [Repo](https://github.com/fr0stb1rd/Edge-TTS-Subtitle-Dubbing) \| [Ses İşleme Hattı Diyagramını Görüntüle (Mermaid)](https://fr0stb1rd.gitlab.io/posts/edge-tts-altyazi-dublaj-araci/#ses-i%CC%87%C5%9Fleme-hatt%C4%B1-pipeline)

## Öne Çıkan Özellikler
*   **Örnekleme Hassasiyetinde Senkronizasyon**: Mükemmel zamanlama sağlayan hassas, örnekleme düzeyinde ses birleştirme için Numpy/Librosa kullanır.
*   **Bellek Optimizasyonu**: Liste tabanlı biriktirme tamponu, O(N²) bellek kopyalamasını önleyerek çok uzun videolarda bile verimli çalışır.
*   **Yüksek Kaliteli Zaman Uzatma**: Konuşma hızını ayarlarken üstün ses kalitesi için `audiostretchy` kütüphanesini kullanır.
*   **Asenkron Toplu İşleme**: 2-3 kat daha hızlı işlem için TTS seslerini paralel olarak oluşturur.
*   **Akıllı Metin Önelliği (Caching)**: Aynı metin parçaları için sesi otomatik olarak yeniden kullanarak tekrarlanan içerikte %50'ye varan tasarruf sağlar.
*   **Zaman Dilimi Doldurma Senkronizasyonu**: Her altyazı bloğunun SRT'de tanımlanan süreyi tam olarak kaplamasını sağlar, konuşulan ses çok kısaysa araya sessizlik ekler.
*   **Mükemmel Video Eşleşmesi**: `--ref_video` kullanılarak, nihai sesi videonuzun tam uzunluğuna uyacak şekilde doldurabilir (pad).
*   **Akıllı Sessizlik**: Satırlar arasına örnekleme düzeyi hassasiyetinde hesaplanmış sessizlikler ekler.
*   **Çoklu Dil**: Microsoft Edge TTS tarafından sağlanan tüm dilleri ve sesleri destekler.
*   **Nöral Sesler**: `en-US-JennyNeural`, `tr-TR-AhmetNeural` gibi yüksek kaliteli Nöral sesleri kullanır.
*   **Kaldığı Yerden Devam Etme**: Kesintiye uğrarsa işleme kaldığı yerden devam edebilir.
*   **Otomatik Geç Başlangıç Yönetimi**: Örtüşen (overlapping) altyazıları akıllıca yöneterek maksimum hız sıkıştırmasını zorlar.
*   **İlerleme İstatistikleri**: Üretim, önbellekleme ve hata sayılarını gösteren detaylı gerçek zamanlı istatistikler.

## Gereksinimler

*   Python 3.8+
*   **FFmpeg** yüklü ve PATH'e eklenmiş olmalı (`ffprobe` medya süresi tespiti için gereklidir)

## Repoyu klonlayın ve dizine girin

```bash
git clone https://github.com/fr0stb1rd/Edge-TTS-Subtitle-Dubbing.git

cd Edge-TTS-Subtitle-Dubbing
```

## Sanal Ortam (Önerilen)
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

## Bağımlılıklar

```bash
pip install -r requirements.txt
```

## Kullanım

Temel komut:
```bash
python src/main.py <input.srt> <output.wav> --voice <voice_name>
```

**Örnek:**
```bash
python src/main.py tr.srt output.wav --voice tr-TR-AhmetNeural
```

### Gelişmiş Seçenekler

| Bayrak | Açıklama | Varsayılan |
| :--- | :--- | :--- |
| `--voice <ad>` | Edge TTS Ses adı (`edge-tts --list-voices` çalıştırın). | `en-US-JennyNeural` |
| `--ref_video <yol>` | Orijinal video yolu. Süreyi tam eşleştirmek için sona sessizlik ekler. | `None` |
| `--expected_duration <değer>` | Video mevcut değilse manuel toplam süre (Saniye veya SS:DD:SN). | `None` |
| `--max_speed <değer>` | Maksimum hızlandırma faktörü (örn. 2.0). Çok fazla 'Overlap' uyarısı görürseniz artırın. | `1.5` |
| `--temp <yol>` | Özel bir geçici dizin belirtin. | mevcut dizinde `temp/` |
| `--keep-temp` | İşlem bittikten sonra geçici dosyaları silmez. | `False` (Otomatik silme) |
| `--resume` | Mevcut geçici dosyaları işleyerek devam eder. | `False` |
| `--no-concat` | Yalnızca segmentleri oluşturur, son birleştirmeyi atlar. | `False` |
| `--batch_size <sayı>` | Paralel işlem için eş zamanlı TTS isteği sayısı. | `10` |
| `--log_file <yol>` | Log dosyası yolu. Belirtilmezse çıktı dosyasının yanında `<output_name>.log` otomatik oluşturulur. | Otomatik oluşturulur |
| `--log_level <seviye>` | Loglama seviyesi: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` |
| `--retries <sayı>` | Ağ hatalarında TTS oluşturma için yeniden deneme sayısı. | `10` |
| `--format <uzantı>` | Çıktı formatını zorla (`wav`, `m4a`, `opus`). Gerekiyorsa dosya uzantısını ekler. | `None` (WAV) |

**Örnek: Tam Senkronizasyon İş Akışı**
Çıktı sesinin videonuzla tam olarak aynı uzunlukta olmasını garanti etmek için:

```bash
# Senaryo A: Video elinizde mevcut
python src/main.py subtitles.srt dub.wav --ref_video original_movie.mp4

# Senaryo B: Video süresini biliyorsunuz (Video dosyasına gerek yok)
# Süreyi "SS:DD:SN" formatında veya toplam saniye olarak verebilirsiniz.

# Seçenek 1: SS:DD:SN.ms (örn., 1 saat, 30 dakika, 5.123 saniye)
python src/main.py subtitles.srt dub.wav --expected_duration "01:30:05.123"

# Seçenek 2: Saniye (örn., 90 dakika)
python src/main.py subtitles.srt dub.wav --expected_duration 5400.5
```


**Örnek: Loglama Seçenekleri**
Loglama çıktısını ve ayrıntı düzeyini kontrol edin:

```bash
# Varsayılan: INFO seviyesiyle output.log oluşturur
python src/main.py subtitles.srt output.wav --voice en-US-JennyNeural

# Özel log dosyası konumu
python src/main.py subtitles.srt output.wav --log_file ~/logs/dubbing.log

# Sorun giderme için Debug (hata ayıklama) seviyesi
python src/main.py subtitles.srt output.wav --log_level DEBUG

# Minimum loglama (sadece hatalar)
python src/main.py subtitles.srt output.wav --log_level ERROR
```

## Faydalı İpuçları

### ffprobe ile Video Süresini Alma
`--expected_duration` parametresi için bir video dosyasının tam süresini bulmanız gerekirse:

```bash
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 video.mp4
```

Bu komut süreyi saniye cinsinden verecektir (örn., `5400.5`).

### Sesleri Bulma
Mevcut tüm sesleri listelemek için:
```bash
edge-tts --list-voices
```

## Performans Optimizasyonları

Araç, hızlı işlem için çeşitli optimizasyonlar içerir:

### Asenkron Toplu İşleme
Paralel TTS istekleri sayesinde **2-3 kat daha hızlı oluşturma**:

```bash
# Varsayılan: 10 eş zamanlı istek
python src/main.py subtitles.srt output.wav

# İyi ağ bağlantılarında daha hızlı (20 eş zamanlı)
python src/main.py subtitles.srt output.wav --batch_size 20

# Yavaş ağlarda daha güvenli (5 eş zamanlı)
python src/main.py subtitles.srt output.wav --batch_size 5
```

**Nasıl çalışır:**
- Segmentler sırayla değil, paralel partiler (batch) halinde oluşturulur
- Hız ve ağ yükünü dengelemek için yapılandırılabilir parti boyutu
- İlerleme durumu her parti için gösterilir

### Akıllı Metin Önelliği (Caching)
Tekrarlanan metin içeren dosyalarda **%20-75 daha hızlı**:

- Özdeş altyazı metinlerini otomatik olarak algılar
- TTS'i bir kez oluşturur, tüm kopyalar için yeniden kullanır
- Önbellek geçici dizinde saklanır (`--keep-temp` kullanılmadıkça otomatik temizlenir)

**Örnek:**
```
Yaygın ifadelere sahip 100 segment:
- "Evet" 15 kez geçiyor → Bir kez oluşturulur, 14 kez önbellekten kullanılır
- "Teşekkürler" 10 kez geçiyor → Bir kez oluşturulur, 9 kez önbellekten kullanılır
Sonuç: %25 daha az TTS isteği!
```

### Birleşik Performans
**Beklenen hız artışları:**
- Küçük dosyalar (< 50 segment): 2-3 kat daha hızlı
- Büyük dosyalar (500+ segment): 3-5 kat daha hızlı
- Tekrarlanan içerik: 5 kata kadar daha hızlı

## İlerleme İstatistikleri

Araç detaylı ilerleme bilgisi sağlar:

```
============================================================
Processing Summary:
  Total segments: 100
  Generated: 65        # Yeni TTS sesi oluşturuldu
  Cached (text reuse): 20   # Önbellekten yeniden kullanılan kopyalar
  Resumed: 15         # Önceki çalıştırmadan kalan mevcut dosyalar
  Empty subtitles: 2   # Boş altyazı girişleri
  Failed (using silence): 0
  Overlaps detected: 1
  Late starts (speed-up): 1
  Output audio duration: 3645.23s
  Target match accuracy: 99.97%
============================================================
```

**İstatistiklerin açıklaması:**
- **Generated**: Bu çalıştırmada oluşturulan benzersiz TTS ses dosyaları
- **Cached**: Akıllı önbellekleme (aynı metin) sayesinde yeniden kullanılan segmentler
- **Resumed**: Önceki kesintiye uğrayan çalıştırmadan kalan dosyalar (`--resume` ile)
- **Target match accuracy**: Çıktının beklenen süreyle ne kadar yakından eşleştiği

## Teknik Detaylar

### Ses İşleme Hattı (Pipeline)
Araç, maksimum kalite ve senkronizasyon için gelişmiş bir ses işleme hattı kullanır:

1. **TTS Üretimi**: Her altyazı segmenti için MP3 sesi oluşturmak üzere Microsoft Edge TTS kullanır
2. **Zaman Uzatma (Time-Stretching)**: Kaliteyi korurken ses süresini ayarlamak için `audiostretchy` kütüphanesini kullanır
3. **Örnekleme Hassasiyetinde Birleştirme**: Numpy dizileri, örnekleme düzeyinde (24kHz) hassas zamanlama sağlar
4. **Liste Tabanlı Biriktirme**: Segmentler bir listede saklanır ve O(N²) bellek karmaşıklığından kaçınmak için tek seferde birleştirilir
5. **Hassas Kırpma/Doldurma**: Kaymayı önlemek için nihai ses, tam örnek sayısına göre kırpılır veya doldurulur

### Bellek Optimizasyonu
Çok sayıda altyazı içeren uzun videolar için araç, tekrarlanan `numpy.concatenate()` çağrıları yerine liste tabanlı bir tampon kullanır. Bu, saf yaklaşımda oluşabilecek performans düşüşünü ve bellek sorunlarını önler.

**Bellek Kullanımı:**
- Minimum ayak izi: Liste tabanlı tampon bellek şişmesini önler
- Dosya uzunluğuyla doğrusal olarak ölçeklenir
- 1000+ segmentli dosyalarla sorunsuz test edilmiştir

### Geç Başlangıç Yönetimi
Bir altyazı geç başlarsa (önceki sesle çakışırsa), araç otomatik olarak:
- Çakışmayı algılar ve bir uyarı verir
- Maksimum hız sıkıştırmasını ( `--max_speed` faktörüne kadar) zorlar
- Genel senkronizasyonu korumak için işleme devam eder

## Desteklenen Sesler (Seçki)

| İsim | Cinsiyet | Kategori |
| :--- | :--- | :--- |
| **İngilizce (ABD)** | | |
| `en-US-JennyNeural` | Kadın | Genel |
| `en-US-ChristopherNeural` | Erkek | Haber |
| `en-US-GuyNeural` | Erkek | Haber |
| **Türkçe** | | |
| `tr-TR-AhmetNeural` | Erkek | Genel |
| `tr-TR-EmelNeural` | Kadın | Genel |
| **Çince** | | |
| `zh-CN-XiaoxiaoNeural` | Kadın | Sıcak |
| `zh-CN-YunyangNeural` | Erkek | Profesyonel |

*(Listenin tamamı için `edge-tts --list-voices` çalıştırın)*

## Lisans

Bu proje **MIT Lisansı** altında lisanslanmıştır. Detaylar için [LICENSE](LICENSE) dosyasına bakın veya [repoyu](https://github.com/fr0stb1rd/Edge-TTS-Subtitle-Dubbing) ziyaret edin.
