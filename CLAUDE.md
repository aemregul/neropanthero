# Pepper Root AI Agency — Proje Dokümantasyonu

> **Son Güncelleme:** 10 Mart 2026
> **Repo:** [github.com/aemregul/PepperRootAiAgency](https://github.com/aemregul/PepperRootAiAgency)

Bu dosya projenin tüm özelliklerini, mimarisini ve nasıl çalıştığını açıklar. Yeni bir AI oturumu veya ekip üyesi bu dosyayı okuyarak projeyi tamamen anlayabilir.

---

## 🚨 KRİTİK ÇALIŞMA KURALLARI (EN ÖNCELİKLİ!)

Bu kurallar her şeyden önce gelir. Bu kurallara uyulmadığı takdirde proje bozulabilir.

### 1. Branch Tabanlı Geliştirme

- **`main` branch'a direkt push YASAK.** Her değişiklik için yeni branch oluştur.
- Branch'ı Vercel'de ayrı deploy olarak canlıya al ve test et.
- Test başarılıysa `main`'e merge et. Başarısızsa düzelt, tekrar test et.
- Branch isimlendirme: `fix/bug-adi`, `feat/ozellik-adi`, `hotfix/acil-duzeltme`

### 2. Bir Şeyi Düzeltirken Başka Şeyleri Bozma

- **Bir bug fix'e odaklanırken mevcut çalışan özellikleri ASLA bozma.**
- Değişiklik yapmadan önce etki analizi yap: "Bu değişiklik hangi dosyaları, hangi özellikleri etkiler?"
- Eğer bir fix başka bir özelliği bozabilecekse, **ÖNCE kullanıcıyı bilgilendir:**
  - "Bu bug'ı şöyle çözeceğim, ama X özelliği etkilenebilir. Onay veriyor musun?"
- Kullanıcıdan onay almadan riskli değişiklik YAPMA.

### 3. Test Etmeden Push Yok

- Her değişiklik **önce local'de test edilecek** (import kontrolü, syntax kontrolü, çalıştırma testi).
- Sonra branch'ta Vercel'e deploy edilip **canlıda da test edilecek.**
- Test edilmemiş kod kesinlikle `main`'e merge edilmez.

### 4. Bilgilendirme Zorunluluğu

- Ne yapacağını, hangi dosyaları değiştireceğini, potansiyel riskleri **önceden söyle.**
- Sessizce dosya değiştirme, "bonus" özellik ekleme, veya planlanmamış değişiklik yapma.
- Her değişiklik öncesi kısa bilgi ver: "X dosyasında Y değişikliği yapacağım, Z etkisi olabilir."

### 5. Sadece İstenen Şeye Odaklan

- Kullanıcının istediği değişikliği yap, ekstra "iyileştirme" ekleme.
- Çalışan sisteme müdahale etme — "daha iyi olur" diye değişiklik yapma.
- Bir sorun çözülmüyorsa zorlamadan kullanıcıyla konuş, birlikte karar verin.

### 6. Öncelik: Stabilite

- Yeni özellik eklemeden önce mevcut sistemin **chat yanıtı**, **kısa video üretimi**, **uzun video üretimi** ve **gerçek zamanlı hata bildirimi** uçtan uca çalışıyor olmalı.
- Demo / sunum öncesi özellikle şu akışlar yerelde doğrulanmalı:
  - Düz metin sohbeti
  - SSE streaming yanıtı
  - 5 saniyelik kısa video üretimi
  - Uzun video başlatma + WebSocket progress/error/complete bildirimi
- Kullanıcı tarafında "yanıt vermedi" veya "asılı kaldı" hissi oluşturan sessiz hatalar kritik bug olarak ele alınmalı.

---

## 🔧 Son Stabilizasyon Çalışması (7 Mart 2026)

### Amaç

- Yeni özellik değil, mevcut demoda bozulan akışları tekrar güvenilir hale getirmek
- Özellikle:
  - Chat bazen yanıt vermiyor gibi görünüyordu
  - Video üretimi başarısız olduğunda kullanıcıya net hata dönmüyordu
  - Kısa video üretiminde sistem gereksiz şekilde kırılgan servis yoluna düşebiliyordu

### Yapılan Düzeltmeler

- **Frontend SSE hata görünürlüğü düzeltildi**
  - Dosya: `frontend/src/components/ChatPanel.tsx`
  - Sorun: Backend `event: error` gönderse bile frontend bunu sadece console'a yazıyordu, kullanıcı chat içinde hata görmüyordu.
  - Düzeltme: SSE hata event'i artık UI'da görünür hata mesajına çevriliyor.

- **Arka plan video crash'lerinde WebSocket hata bildirimi eklendi**
  - Dosya: `backend/app/services/agent/orchestrator.py`
  - Sorun: `_run_video_bg` ve `_run_long_video_bg` exception aldığında DB'ye hata mesajı yazılsa da canlı progress kanalına hata gitmiyordu.
  - Düzeltme: Crash durumunda `progress_service.send_error(...)` çağrılıyor.

- **Kısa video varsayılan modeli daha güvenilir hatta alındı**
  - Dosya: `backend/app/services/agent/orchestrator.py`
  - Sorun: Kısa video tool çağrısında model gelmezse varsayılan olarak `veo` kullanılıyordu; bu da sistemi gereksiz şekilde Google/Gemini hattına bağımlı yapıyordu.
  - Düzeltme: Varsayılan model `kling` yapıldı.

- **Test branch'inde video maliyet optimizasyonu yapıldı**
  - Dosyalar:
    - `backend/app/services/agent/orchestrator.py`
    - `backend/app/services/plugins/fal_plugin_v2.py`
    - `backend/app/services/plugins/model_selector.py`
    - `backend/app/services/long_video_service.py`
  - Amaç: Testlerde kredi tüketimini düşürmek
  - Karar: Mevcut entegrasyon içindeki varsayılan video modeli `MiniMax Hailuo 02 Standard` olarak ayarlandı
  - Not:
    - Bu değişiklik **test branch'i** içindir
    - Yayına çıkarken kalite / ihtiyaç durumuna göre `Veo` veya başka ana modele geri dönülebilir
    - Explicit olarak `veo`, `kling` vb. model isteyen çağrılar bozulmadı; sadece varsayılanlar ve auto seçim maliyet odaklı kaydırıldı

- **Kısa video tamamlanınca chat'e düşmeyen kritik hata izole edildi**
  - Dosyalar:
    - `backend/app/services/stats_service.py`
    - `backend/app/services/agent/orchestrator.py`
    - `frontend/src/components/ChatPanel.tsx`
  - Kök neden: `usage_stats` tablosu hem günlük aggregate hem model-bazlı satırlar için kullanılıyor. Video asset kaydedildikten sonra `StatsService` yanlış şekilde birden fazla satırla eşleşip `Multiple rows were found when one or none was required` hatası üretiyordu.
  - Etki: Video aslında oluşuyor ve assets tarafına kaydoluyor, ama completion mesajı chat'e düşmeden akış hata mesajına dönüyordu; kullanıcı ekranda `%90` civarında takılmış gibi görüyordu.
  - Düzeltme:
    - `StatsService` artık sadece aggregate satırı (`model_name IS NULL`) hedefliyor
    - Legacy duplicate durumda ilk uygun satırı kullanıp user flow'u bozmuyor
    - Video istatistiği yazımı ayrıca non-critical hale getirildi; hata olsa bile completion akışı kesilmiyor
    - Frontend progress state `complete/error` event'lerinde doğru statüye çekildi

- **Media panelinden eklenen referans görsel yanlış asset'e düşebiliyordu**
  - Dosyalar:
    - `frontend/src/components/ChatPanel.tsx`
    - `backend/app/services/agent/orchestrator.py`
  - Kök neden 1: Media panelinden chat'e eklenen görsel gerçek binary olarak attach edilmiyordu; boş `File` placeholder gönderildiği için backend yeni referansı alamıyor, session cache'deki eski görsele düşebiliyordu.
  - Kök neden 2: `with-files` (non-stream) akışında arka plan video görevi başlatıldıktan sonra sistem tekrar LLM final response üretiyordu; bu da saçma/hallucinated kapanış metinlerine neden olabiliyordu.
  - Düzeltme:
    - Asset panelinden eklenen image URL artık önce fetch edilip gerçek dosya olarak attach ediliyor
    - Drag/drop ve asset-panel image attach davranışı aynı mantığa çekildi
    - Non-stream background task akışında final LLM cevabı atlanıyor; tool'un deterministik mesajı doğrudan kullanılıyor

- **Referanslı video akışında gereksiz çift upload kaldırıldı**
  - Dosyalar:
    - `backend/app/api/routes/chat.py`
    - `backend/app/services/agent/orchestrator.py`
  - Kök neden:
    - `with-files` endpoint'i yüklenen referans görseli önce fal storage'a upload ediyordu
    - ardından `agent.process_message` aynı görseli base64'ten tekrar fal storage'a upload ediyordu
    - bu da özellikle referanslı video başlatma akışında gereksiz gecikme yaratıyordu
  - Düzeltme:
    - `with-files` akışında oluşan fal URL'leri artık `agent.process_message` içine doğrudan taşınıyor
    - agent bu URL'leri yeniden kullanıyor, ikinci upload yapılmıyor
    - GPT-4o vision için base64 içerik korunuyor; sadece storage upload duplicaton kaldırıldı
    - Saf `videoya çevir / animate` isteklerinde GPT-4o'ya görsel piksellerini tekrar okutmak yerine doğrudan `image_url` odaklı hızlı yol kullanılıyor

- **Agent prompt hafızasında DB öğrenilmiş tercihler görünür hale getirildi**
  - Dosya: `backend/app/services/preferences_service.py`
  - Not: Bu değişiklik stabilite dışı ama kaybolmaması için kayıt altına alındı. `manage_core_memory` ile kaydedilen `learned_preferences` verileri artık prompt context'e açık şekilde ekleniyor.

- **Hafıza hijyeni daraltıldı; anlık görev parametreleri artık kalıcı tercih gibi davranmıyor**
  - Dosyalar:
    - `backend/app/services/memory_hygiene.py`
    - `backend/app/services/preferences_service.py`
    - `backend/app/services/conversation_memory_service.py`
    - `backend/app/services/episodic_memory_service.py`
    - `backend/app/services/agent/orchestrator.py`
    - `backend/app/services/agent/tools.py`
  - Kök neden:
    - Kullanıcıyı tanımak için eklenen hafıza katmanı; `5 saniye`, `1 görsel`, seçilen model, son referans gibi anlık görev parametrelerini de kalıcı bilgi gibi prompt'a geri taşıyabiliyordu.
    - Özellikle `successful_prompts` benzerlik araması ve learned preferences, yeni istekte açıkça verilen süre/adet bilgisini kirletebiliyordu.
  - Düzeltme:
    - Kalıcı hafıza yazımı whitelist ile sınırlandı; sadece stabil `style / identity / brand / workflow / preferred_colors` türü bilgiler saklanıyor
    - Süre, adet, model, URL, son asset, tek seferlik görev talimatları hafızaya yazılmıyor
    - Cross-project memory ve episodic memory prompt'a eklenirken transient içerikler filtreleniyor
    - `find_similar_prompts` artık mevcut istekle çelişen geçmiş prompt'ları eliyor ve prompt örneklerini sadece stil/ton ilhamı olarak veriyor
    - Agent system prompt'una "mevcut mesaj hafızadan üstündür" guardrail'i eklendi

- **Video üretiminde stale referans görsel sızıntısı kapatıldı**
  - Dosyalar:
    - `backend/app/services/agent/orchestrator.py`
    - `backend/tests/test_video_reference_resolution.py`
  - Kök neden:
    - Kullanıcı yeni referans seçmeden video istediğinde sistem bazen eski session cache / eski referans geçmişini `generate_video` aracına gizlice `image_url` olarak enjekte ediyordu.
    - Bu da text-to-video isteğinin yanlışlıkla eski bir görselle image-to-video'ya dönmesine neden oluyordu.
  - Düzeltme:
    - `generate_video` ve `generate_long_video` için stale session-cache auto injection kaldırıldı
    - Video aracı artık sadece:
      - bu mesajda gerçekten attach edilen referansı kullanıyor
      - veya kullanıcı açıkça "ilk görsel", "son görsel", "ilk oluşturduğumuz kedi görseli" gibi bir asset seçimi yaparsa oturum asset'lerinden doğru görseli çözüyor
    - Eski referans artık sırf cache'de kaldı diye yeni video isteğine sızmıyor

### Yapılan Doğrulamalar

- `backend/venv/bin/python -m py_compile backend/app/services/agent/orchestrator.py`
- `backend/venv/bin/python -m py_compile backend/app/services/preferences_service.py`
- `backend/venv/bin/pytest backend/tests/test_preferences_service.py`
- `backend/venv/bin/python -m py_compile backend/app/services/memory_hygiene.py backend/app/services/preferences_service.py backend/app/services/conversation_memory_service.py backend/app/services/episodic_memory_service.py backend/app/services/agent/orchestrator.py backend/app/services/agent/tools.py`
- `backend/venv/bin/pytest backend/tests/test_preferences_service.py backend/tests/test_memory_hygiene.py backend/tests/test_stats_service.py`
- `backend/venv/bin/python -m py_compile backend/app/services/agent/orchestrator.py backend/tests/test_video_reference_resolution.py`
- `backend/venv/bin/pytest backend/tests/test_video_reference_resolution.py backend/tests/test_memory_hygiene.py backend/tests/test_preferences_service.py backend/tests/test_stats_service.py`
- `frontend`: `ChatPanel.tsx` için lint çalıştırıldı, yeni error yok; dosyada mevcut eski warning'ler devam ediyor.

### Halen Doğrulanması Gerekenler

- Lokal canlı akışta düz metin chat isteği
- Lokal canlı akışta kısa video üretimi
- Lokal canlı akışta uzun video başlatma + progress / complete bildirimi
- Branch deploy sonrası Vercel/Railway üzerinde yeniden test

---

## 🧠 Proje Nedir?

Pepper Root AI Agency, **agent-first** (ajantik) bir AI yaratıcı stüdyodur. Kullanıcı doğal dilde istek yapar; AI asistan planlar, üretir, düzenler ve adapte olur.

**Temel Yetkinlikler:**

- 🖼️ Görsel üretim ve düzenleme (33 AI modeli, admin toggle ile yönetim)
- 🎬 Video üretim ve post-production (FFmpeg + AI)
- 🎵 Müzik/ses üretimi ve senkronizasyon
- 🚀 Tek cümleden tam kampanya oluşturma (otonom)
- 👤 Karakter/marka/mekan hafızası (@tag sistemi)
- 🔍 Web araştırma ve analiz

---

## 🏗️ Mimari

### Tech Stack

| Katman          | Teknoloji                                                            |
| --------------- | -------------------------------------------------------------------- |
| **Backend**     | Python 3.14, FastAPI, SQLAlchemy, Alembic                            |
| **Frontend**    | Next.js 16.1.6, TypeScript, React                                    |
| **Veritabanı**  | PostgreSQL (Lokal: Docker `pepperroot-db` / Canlı: Railway Postgres) |
| **Cache**       | Redis (opsiyonel — yoksa DB fallback)                                |
| **Primary LLM** | OpenAI GPT-4o                                                        |
| **Görsel AI**   | fal.ai (Nano Banana, Flux.2, GPT Image 1 vb.)                        |
| **Video AI**    | fal.ai (Kling 3.0 Pro — varsayılan), Google Veo 3.1                  |
| **Ses AI**      | OpenAI Whisper/TTS, ElevenLabs, Mirelo SFX                           |
| **Arama**       | Pinecone (vektör), SerpAPI (web)                                     |
| **Auth**        | Google OAuth 2.0, JWT                                                |

### Klasör Yapısı

```
PepperRootAiAgency/
├── backend/
│   ├── app/
│   │   ├── api/routes/          # REST API endpoints
│   │   ├── core/                # config, database, cache
│   │   ├── models/              # SQLAlchemy modelleri
│   │   ├── services/
│   │   │   ├── agent/           # orchestrator.py, tools.py (36 araç)
│   │   │   ├── plugins/         # fal_plugin_v2.py, fal_models.py
│   │   │   ├── long_video_service.py
│   │   │   ├── google_video_service.py
│   │   │   ├── entity_service.py
│   │   │   ├── asset_service.py
│   │   │   └── ...
│   │   └── main.py
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/                 # Next.js pages (/, /app, /login)
│       ├── components/          # ChatPanel, AssetsPanel, Sidebar vb.
│       ├── contexts/            # AuthContext
│       └── lib/                 # api.ts
└── CLAUDE.md                    # Bu dosya
```

---

## 🤖 Agent Sistemi (36 Araç)

Agent, GPT-4o tabanlıdır. Kullanıcının mesajını alır, hangi araçları kullanacağına karar verir ve çalıştırır. Araç tanımları `tools.py`, handler'lar `orchestrator.py` dosyasındadır.

### Tool Call Guard'ları

| Guard                     | Engellenen                         | Tetikleyici                    |
| ------------------------- | ---------------------------------- | ------------------------------ |
| **Entity Guard**          | `create_character/location/brand`  | `generate_image` aynı batch'te |
| **Plugin Guard**          | `generate_image`, `edit_image` vb. | `manage_plugin` aynı batch'te  |
| **Video Duplicate Guard** | İkinci video çağrısı               | Aynı batch'te 2x video         |

### Görsel Araçları

| Araç                | Ne Yapar                                      |
| ------------------- | --------------------------------------------- |
| `generate_image`    | Yeni görsel üretir (9 model destekler)        |
| `edit_image`        | Mevcut görseli düzenler (maskesiz inpainting) |
| `outpaint_image`    | Görsel boyutunu/formatını değiştirir          |
| `upscale_image`     | Kaliteyi artırır (Topaz 2x-4x)                |
| `remove_background` | Arka planı kaldırır (transparent PNG)         |
| `generate_grid`     | 3x3 grid oluşturur (9 varyasyon)              |

### Video Araçları

| Araç                  | Ne Yapar                                                       |
| --------------------- | -------------------------------------------------------------- |
| `generate_video`      | Kısa video üretir (≤10s) — 5 model                             |
| `generate_long_video` | Uzun video üretir (15-180s) — sahne planı + FFmpeg birleştirme |
| `edit_video`          | Videoyu görsel olarak düzenler                                 |
| `advanced_edit_video` | FFmpeg post-production (10 operasyon)                          |

### Ses & Müzik

| Araç                 | Ne Yapar                                  |
| -------------------- | ----------------------------------------- |
| `generate_music`     | AI müzik üretir (MiniMax)                 |
| `add_audio_to_video` | Videoya ses/müzik ekler (FFmpeg)          |
| `audio_visual_sync`  | Ses-görüntü senkronizasyonu (6 operasyon) |

### Diğer Araçlar

| Araç                                  | Ne Yapar                      |
| ------------------------------------- | ----------------------------- |
| `plan_and_execute`                    | Tek cümleden tam kampanya     |
| `create_character/location/brand`     | Entity oluştur (@tag sistemi) |
| `search_web/search_images/browse_url` | Web araştırma                 |
| `research_brand`                      | Marka araştırması             |
| `manage_plugin`                       | Plugin CRUD                   |
| `manage_core_memory`                  | Kullanıcı tercihleri hafıza   |

---

## 🎬 33 AI Modeli (5 Kategori)

| Kategori         | Sayı | Modeller                                                                                                                    |
| ---------------- | ---- | --------------------------------------------------------------------------------------------------------------------------- |
| Görsel Üretim    | 9    | Nano Banana Pro, Nano Banana 2, Flux.2, Flux 2 Max, GPT Image 1, Reve, Seedream 4.5, Recraft V3, Grok Imagine 1.0           |
| Görsel Düzenleme | 7    | Flux Kontext, Flux Kontext Pro, OmniGen V1, Flux Inpainting, Object Removal, Outpainting, Nano Banana 2 Edit                |
| Video            | 9    | Kling 3.0 Pro, Sora 2 Pro, Veo 3.1 Fast, Veo 3.1 Quality, Veo 3.1 (Google SDK), Seedance 1.5, Hailuo 02, Grok Imagine Video |
| Ses & Müzik      | 4    | ElevenLabs TTS/SFX, Whisper STT, Stable Audio                                                                               |
| Araç & Utility   | 4    | Face Swap, Topaz Upscale, Background Removal, Style Transfer                                                                |

---

## 🛡️ Admin Panel

| Sekme           | Ne Yapar                                                |
| --------------- | ------------------------------------------------------- |
| **Genel Bakış** | Toplam oturum, asset, mesaj, aktif model istatistikleri |
| **AI Modeller** | 33 modelin açma/kapama toggle'ları (5 kategori)         |
| **Analitik**    | Model kullanım dağılımı, günlük üretim trendleri        |

---

## 🏪 Plugin Marketplace

- 41 resmi plugin (8 kategori)
- Topluluk pluginleri (chat'ten oluşturulan otomatik yayınlanır)
- Sıralama: Popüler, En İyi, Yeni
- Proje seçici popup ile yükleme, duplicate kontrolü

---

## 🖥️ Frontend Özellikleri

- **Chat Paneli**: SSE streaming, çoklu görsel yükleme (10'a kadar), ChatGPT tarzı medya düzeni
- **Assets Panel**: 6 kategori filtresi, çoklu seçim & indirme, video hover preview, çöp kutusu
- **Sidebar**: Proje yönetimi, entity listesi, plugin listesi, daraltılabilir
- **Auth**: Google OAuth 2.0, "Hesabımı hatırla" toggle

---

## 🔧 Çalıştırma Komutları

```bash
# Backend (production)
cd /Users/emre/PepperRootAiAgency/backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Backend (development — auto-reload)
cd /Users/emre/PepperRootAiAgency/backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd /Users/emre/PepperRootAiAgency/frontend
npm run dev
```

### URL'ler

| Ortam | Frontend                                 | Backend                                              |
| ----- | ---------------------------------------- | ---------------------------------------------------- |
| Lokal | http://localhost:3000                    | http://localhost:8000                                |
| Canlı | https://pepper-root-ai-agency.vercel.app | https://pepperrootaiagency-production.up.railway.app |

### Railway Environment Variables

| Değişken               | Açıklama                                      |
| ---------------------- | --------------------------------------------- |
| `DATABASE_URL`         | `${Postgres.DATABASE_URL}` — Railway referans |
| `OPENAI_API_KEY`       | OpenAI API anahtarı                           |
| `FAL_KEY`              | fal.ai API anahtarı                           |
| `GOOGLE_CLIENT_ID`     | Google OAuth Client ID                        |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret                    |
| `GOOGLE_REDIRECT_URI`  | Google OAuth callback URL                     |
| `FRONTEND_URL`         | Vercel frontend URL                           |
| `BACKEND_URL`          | Railway backend URL                           |
| `ALLOWED_ORIGINS`      | CORS izin verilen origins                     |

---

## 🧠 Agent Context Sistemi

`orchestrator.py` → `_build_enriched_context()` metodu:

| #   | Bileşen               | Ne Enjekte Eder                         |
| --- | --------------------- | --------------------------------------- |
| 1   | Entity @tag çözümleme | Mesajdaki @tag'lerin detayları          |
| 2   | Proje bağlamı         | Aktif proje adı, kategori               |
| 3   | Working Memory        | Son 5 asset'in URL ve prompt'u          |
| 4   | Kullanıcı tercihleri  | Aspect ratio, model, stil               |
| 5   | Episodic memory       | Önemli olaylar                          |
| 6   | Core memory           | Projeler arası uzun vadeli hafıza       |
| 7   | Entity listesi        | Kullanıcının TÜM entity'leri            |
| 8   | Plugin listesi        | Projede yüklü eklentilerin stil bilgisi |

---

## 📋 Faz Geçmişi

| Faz   | Tarih      | Açıklama                                                |
| ----- | ---------- | ------------------------------------------------------- |
| 1-4   | Ocak 2026  | Altyapı, Agent çekirdek, Entity sistemi, Video üretimi  |
| 5-8   | Şubat 2026 | Plugin, Auth, Frontend, GPT-4o migration                |
| 9-13  | Şubat 2026 | Redis, Pinecone, Gemini edit, Core Memory               |
| 14-21 | Şubat 2026 | UI redesign, Multi-model video, 47 model                |
| 22-24 | 27 Şubat   | Kampanya planlama, Video editing, Audio sync            |
| 25-27 | 1 Mart     | Admin Panel, Plugin Marketplace, Guards & UX            |
| 28-30 | 3 Mart     | Agent Intelligence, Security & Deploy, Feedback sistemi |
| 31    | 4 Mart     | Long Video Production Fix & Stability                   |
| 32    | 4 Mart     | Grok Imagine Entegrasyonu (33 model)                    |
| 33    | 5 Mart     | Autonomous Agency Features                              |
| 34    | 5 Mart     | Production Deploy (Railway + Vercel)                    |

---

## 📊 Proje İstatistikleri

| Metrik         | Değer   |
| -------------- | ------- |
| Agent Araç     | 36      |
| AI Model       | 33      |
| Toplam Faz     | 34      |
| Canlı Backend  | Railway |
| Canlı Frontend | Vercel  |

---

## �️ ROADMAP — Öncelik Sıralı Geliştirme Planı

> **Oluşturulma:** 10 Mart 2026
> **Kural:** Her madde branch'ta geliştirilecek, test edilecek, sonra main'e merge edilecek.

---

### 🔴 Faz 1 — Kritik Bug Fix'ler (Öncelik: EN YÜKSEK)

Bu maddeler çözülmeden yeni özelliğe geçilmez.

- [x] **1.1 — Chat Yavaşlık & Yanıtsızlık Sorunu** _(10 Mart 2026 — Düzeltildi)_
  - ~~Sorun: Chat çok yavaş, bazen hiç geri dönüş yapmıyor~~
  - Düzeltilen: SSE stream `onDone` callback eksikliği, `charQueue` flush sonsuz bekleme (10sn timeout eklendi)
  - Düzeltilen: `_generate_long_video` fonksiyonunda `resolved_entities` NameError
  - Düzeltilen: `with-files` endpoint'inde `fal_client.upload` senkron çağrısı greenlet çakışması (`asyncio.to_thread` ile çözüldü)
  - Düzeltilen: `main.py` trash cleanup'ta `AsyncSessionLocal` import hatası (`async_session_maker` ile değiştirildi)
  - Etki alanı: `backend/app/services/agent/orchestrator.py`, `backend/app/api/routes/chat.py`, `frontend/src/components/ChatPanel.tsx`, `backend/app/main.py`

- [ ] **1.2 — "Beni Hatırla" Çalışmıyor**
  - Sorun: Login'de "Hesabımı hatırla" toggle'ı aktif olsa bile oturum kayboluyor
  - Araştırılacak: JWT token persist mantığı, localStorage/cookie süresi, token refresh akışı
  - Etki alanı: `frontend/src/contexts/AuthContext.tsx`, `backend/app/api/routes/auth.py`

- [ ] **1.3 — Görsel Silindiğinde Çöp Kutusuna Gitmiyor**
  - Sorun: Kaydedilen görseller silindiğinde soft-delete (trash) çalışmıyor, direkt kayboluyor
  - Araştırılacak: `trash_items` tablosuna kayıt yazılıp yazılmadığı, frontend delete handler'ı
  - Etki alanı: `backend/app/api/routes/admin.py`, `frontend/src/components/AssetsPanel.tsx`, `backend/app/models/models.py`

---

### 🟡 Faz 2 — Stabilite & Performans (Öncelik: YÜKSEK)

- [ ] **2.1 — Genel Performans İyileştirme**
  - Chat yanıt süresi optimize edilecek
  - Gereksiz API çağrıları azaltılacak
  - Redis cache stratejisi gözden geçirilecek
  - Frontend render optimizasyonu (gereksiz re-render'lar)
  - Etki alanı: Backend geneli + Frontend geneli

- [ ] **2.2 — Uzun Süreli Test (Stress Test)**
  - Tüm akışlar uçtan uca test edilecek: chat, görsel üretim, video üretim, entity yönetimi
  - Edge case'ler: eşzamanlı istekler, büyük dosyalar, uzun oturumlar
  - Regresyon kontrolü: mevcut çalışan her şey test sonrası da çalışmalı
  - Çıktı: Test raporu oluşturulacak

- [ ] **2.3 — Marketplace Kaldırılacak**
  - Plugin Marketplace UI ve backend endpoint'leri devre dışı bırakılacak
  - Sidebar'daki marketplace butonu kaldırılacak
  - Etki alanı: `frontend/src/components/Sidebar.tsx`, `backend/app/api/routes/admin.py`, ilgili marketplace componentleri

---

### 🟢 Faz 3 — Yeni Özellikler (Öncelik: ORTA)

- [ ] **3.1 — Marka Objeleştirme & Genişletme**
  - Marka entity'si tıklanabilir, genişletilebilir bir obje olacak
  - Marka kartına tıklayınca: logo, renkler, font, ton of voice, hedef kitle gibi alanlar düzenlenebilecek
  - Marka alt-elemanları eklenebilecek (alt-markalar, kampanyalar, ürün serileri)
  - Etki alanı: `backend/app/models/models.py`, `backend/app/services/entity_service.py`, frontend entity card componentleri

- [ ] **3.2 — Skill Sistemi (Marka Odaklı)**
  - Agent'a kalıcı "skill" dosyaları eklenebilecek (marka kılavuzu, stil rehberi, ton of voice dokümanı vb.)
  - Skill'ler bir kez yüklenip DB'de saklanacak — her seferinde API'ye gönderilmeyecek
  - Agent ihtiyaç duyduğunda ilgili skill'i çekip context'e ekleyecek
  - Avantaj: Token tasarrufu, tutarlı marka çıktısı, ölçeklenebilir bilgi tabanı
  - Etki alanı: Yeni servis (`backend/app/services/skill_service.py`), `orchestrator.py`, yeni frontend UI

- [ ] **3.3 — Marka Bazlı Reklam Afişi & Sosyal Medya Görseli Üretimi**
  - Agent, kayıtlı marka entity'sinin kimliğini (logo, renkler, font, ton of voice) kullanarak markaya özel kreatif üretecek
  - Desteklenecek formatlar: Instagram hikaye (1080x1920), Instagram post (1080x1080), Facebook kapak, banner vb.
  - Örnek akış: "Sahibinden markamız adına Kurban Bayramı kutlama görseli oluştur, Instagram hikaye formatında" → Agent marka bilgilerini çeker → uygun format ve marka renkleriyle görsel üretir
  - Mevsimsel/etkinlik bazlı şablonlar: Bayramlar, yılbaşı, kampanya dönemleri
  - Bağımlılık: 3.1 (Marka Objeleştirme) ve 3.2 (Skill Sistemi) tamamlanmış olmalı
  - Etki alanı: `backend/app/services/agent/orchestrator.py`, `backend/app/services/agent/tools.py`, entity context enjeksiyonu

- [ ] **3.4 — Paralel Çoklu Görsel Üretimi (Batch Generation)**
  - Kullanıcı "4 görsel oluştur" dediğinde agent tam olarak 4 görseli **eşzamanlı (parallel)** üretecek
  - Agent mesajdaki sayıyı algılayıp her biri için farklı sahne/açıklama oluşturacak
  - Örnek: "Bir adamın tüm gününü anlatan 4 görsel" → sabah/öğle/akşam/gece sahneleri paralel üretilir
  - `asyncio.gather()` ile eşzamanlı fal.ai çağrıları — sıralı üretimden 3-4x daha hızlı
  - Sayı limiti: kullanıcıya maliyet uyarısı (ör: 10+ görsel → "Bu X kredi harcayacak, onay veriyor musun?")
  - Karakter/marka tutarlılığı: entity bağlamı tüm paralel üretim çağrılarına aynı şekilde enjekte edilecek
  - **Fark yaratan özellik:** Diğer AI araçları tek tek üretir, PepperRoot paralel batch ile saniyeler içinde set üretir
  - Etki alanı: `backend/app/services/agent/orchestrator.py`, `backend/app/services/agent/tools.py`, `backend/app/services/plugins/fal_plugin_v2.py`

- [ ] **3.5 — Grid Generator'dan Chat'e Referans Görsel Gönderme**
  - Grid Generator UI içinde panel upscale edildikten sonra "Chat'e Ekle" butonu
  - Tıklanınca görsel chat'e referans görsel olarak düşecek (paperclip attach gibi)
  - Kullanıcı bu referansla: "bunu düzenle", "bunu videoya çevir" gibi devam komutları verebilecek
  - Etki alanı: `frontend/src/components/GridGenerator.tsx`, `frontend/src/components/ChatPanel.tsx`

- [ ] **3.6 — Asistan İçi Grid Üretimi & Panel İşlemleri (Grid Generator'dan Bağımsız)**
  - Grid Generator UI'sından bağımsız, **tamamen chat üzerinden** çalışan grid üretim yeteneği
  - Kullanıcı chat'ten: "Bu 2 karakter ve bu lokasyonu kullanarak 3x3 grid oluştur" diyecek
  - Dinamik boyut: 2x2, 3x3, 4x4 vb. — kullanıcı ne isterse o boyutta
  - **Entity entegrasyonu:** @karakter ve @lokasyon tag'leri grid prompt'larına otomatik enjekte edilecek
  - **Eşit kare zorunluluğu:** Varsayılan — her kare aynı boyutta. Kullanıcı açıkça "farklı boyutlarda" demediği sürece uniform grid
  - **Panel çıkarma:** "Soldan 2. görseli çıkar" → agent grid'den o kareyi kesip ayrı asset olarak kaydetecek
  - **Panel post-processing zinciri:** Çıkarılan kare üzerine doğrudan upscale, videoya çevirme, düzenleme
  - Örnek tam akış:
    1. "Bu iki karakteri kullanarak 3x3 grid oluştur" → 9 karelik eşit boyutlu grid üretilir
    2. "Sağ üst köşedeki görseli çok beğendim, upscale et" → panel çıkarılır + upscale uygulanır
    3. "Şimdi bunu videoya çevir" → upscale edilmiş görsel videoya dönüştürülür
    4. Kullanıcıya: çıkarılmış görsel + upscale sonucu + video çıktısı döndürülür
  - Mevcut `generate_grid` tool + `sharp` panel extraction altyapısı kullanılacak, chat akışına zincirleme entegrasyonu yapılacak
  - Etki alanı: `backend/app/services/agent/orchestrator.py`, `backend/app/services/agent/tools.py`, grid backend servisleri

- [ ] **3.7 — Agent Config'i DB'ye Kaydetme & Yükleme**
  - Agent'ın system prompt'u, tool konfigürasyonu, aktif model seçimleri DB'ye kaydedilecek
  - Farklı agent profilleri oluşturulabilecek (ör: "Marka Asistanı", "Video Uzmanı", "Genel Yaratıcı")
  - İstenen profil seçilip anında yüklenebilecek
  - Etki alanı: Yeni tablo + servis, `backend/app/services/agent/orchestrator.py`, admin UI

---

### 🔵 Faz 4 — Sunum Hazırlığı (Öncelik: FAZ 1-3 SONRASI)

- [ ] **4.1 — Sunum Aşamaları Dokümanı**
  - Demo senaryosu yazılacak: hangi özellikler hangi sırayla gösterilecek
  - Her adım için hazır prompt'lar ve beklenen çıktılar belirlenecek
  - Olası sorulara hazırlık notları

- [ ] **4.2 — Demo Ortamı Hazırlığı**
  - Canlıda temiz test verisi ile stabil bir demo ortamı
  - Tüm Faz 1-3 maddeleri tamamlanmış ve doğrulanmış olacak

---

## 🔁 Agentic Loop Implementasyonu

> **Amaç:** Agent'ı tek seferlik araç çalıştırıcıdan, kendi çıktısını değerlendirip iteratif olarak iyileştiren gerçek bir otonom ajana dönüştürmek.

### Mevcut Durum

- Agent araç seçimi yapıyor ✅
- Hardcoded fallback zincirleri var (model patlarsa → diğer model) ✅
- Face Swap pipeline var (üret → yüz kontrol → swap) ✅
- **Eksik:** AI kendi çıktısını değerlendirip "tekrar deneyeyim mi?" kararı vermiyor ❌

### Adımlar

- [ ] **Adım 1 — Reflection Loop Altyapısı**
  - `orchestrator.py`'da tool execution sonrası sonucu tekrar LLM'e gönderen döngü mekanizması
  - `max_iterations` limiti (önerilen: 3) — sonsuz döngü koruması
  - Her iterasyonda maliyet takibi (API call sayacı)
  - Etki alanı: `backend/app/services/agent/orchestrator.py`

- [ ] **Adım 2 — Self-Evaluation (Görsel Kalite Değerlendirme)**
  - Üretilen görseli GPT-4o Vision'a gösterip kalite skoru aldırma
  - Skor eşik altındaysa otomatik tekrar üretim veya düzeltme
  - Entity varsa yüz tutarlılığı kontrolü (referans vs çıktı karşılaştırma)
  - Etki alanı: `backend/app/services/agent/orchestrator.py`, `backend/app/services/agent/tools.py`

- [ ] **Adım 3 — Adaptive Retry (Akıllı Yeniden Deneme)**
  - Araç başarısız olduğunda AI'ın **kendi kararıyla** farklı model/parametre denemesi
  - Mevcut hardcoded fallback'lerin LLM kararına dönüştürülmesi
  - Örnek: Kling patladı → AI kendi seçiyor: "Veo ile farklı parametrede deneyeyim"
  - Etki alanı: `backend/app/services/agent/orchestrator.py`, `backend/app/services/plugins/model_selector.py`

- [ ] **Adım 4 — Multi-Step Reasoning (Çok Adımlı Görev Yönetimi)**
  - Karmaşık isteklerde AI'ın kendi alt görev planı çıkarıp sırayla yürütmesi
  - Her adımın çıktısını bir sonraki adımın girdisi olarak kullanma
  - Örnek: "marka kampanyası yap" → logo üret → kontrol et → poster üret → logoyla uyumlu mu kontrol et → video üret
  - Etki alanı: `backend/app/services/agent/orchestrator.py`, `backend/app/services/agent/tools.py`

- [ ] **Adım 5 — Güvenlik & Maliyet Kontrolleri**
  - Iterasyon başına token/API maliyet limiti
  - Kullanıcıya "3 deneme yaptım, en iyisi bu" şeffaflık mesajı
  - Loop'un gereksiz tetiklenmemesi için basit isteklerde bypass (düz metin chat, web arama vb.)
  - Etki alanı: `backend/app/services/agent/orchestrator.py`

---

## � Supabase Hibrit Geçiş Planı

> **Karar:** Supabase'e tam migration yapılmayacak. Mevcut FastAPI backend ve PostgreSQL/SQLAlchemy altyapısı korunacak. Sadece aşağıdaki 3 katman Supabase'e devredilecek.

### Geçilecek Katmanlar

- [ ] **Auth → Supabase Auth**
  - Mevcut: Kendi Google OAuth + JWT implementasyonumuz (`AuthContext`, backend JWT token yönetimi)
  - Hedef: Supabase Auth ile Google, GitHub, Apple, Email auth tek config'den yönetilecek
  - Avantaj: Otomatik token refresh, güvenlik güncellemeleri, yeni social login'ler (Apple, GitHub) sıfır kodla
  - Etki alanı: `backend/app/api/routes/auth.py`, `frontend/src/contexts/AuthContext.tsx`, `frontend/src/lib/api.ts`

- [ ] **Storage → Supabase Storage**
  - Mevcut: Üretilen görseller/videolar fal.ai URL'leri üzerinden saklanıyor (expire riski var)
  - Hedef: Oluşturulan tüm medya asset'leri Supabase Storage'a (S3-uyumlu + CDN) yüklenecek
  - Avantaj: Kalıcı URL'ler, CDN ile hızlı dağıtım, bucket bazlı erişim kontrolü
  - Etki alanı: `backend/app/services/asset_service.py`, `backend/app/services/agent/orchestrator.py`

- [ ] **Realtime → Supabase Realtime**
  - Mevcut: WebSocket ile sadece video progress bildirimi var; genel chat/asset güncellemesi polling-based
  - Hedef: DB değişiklikleri (yeni mesaj, yeni asset, entity güncelleme) anında frontend'e yansıyacak
  - Avantaj: Çoklu cihaz/sekme senkronizasyonu, canlı asset paneli, SSE'ye bağımlılık azalır
  - Etki alanı: `frontend/src/components/ChatPanel.tsx`, `frontend/src/components/AssetsPanel.tsx`

### Geçilmeyecek Katmanlar (Mevcut Yapıda Kalacak)

- ✅ **Database (PostgreSQL):** SQLAlchemy + Alembic altyapısı olgun ve kararlı, taşımak büyük risk az kazanç
- ✅ **Cache (Redis):** Supabase Redis alternatifi sunmuyor, mevcut yapı devam edecek
- ✅ **Backend Logic (FastAPI):** Agent orchestration, model selection, tool pipeline — tamamı FastAPI'de kalacak
- ✅ **Hosting:** Frontend Vercel, Backend Railway — mevcut deployment yapısı korunacak

---

## �🛠️ Son Lokal Düzeltmeler

- Video üretiminde stale referans görsel sızıntısı kapatıldı:
  - Session cache'deki eski görsel artık yeni video isteğine otomatik enjekte edilmiyor
  - `image_url` sadece kullanıcı bu turda görsel attach ettiyse veya mesajda açıkça mevcut asset'i hedeflediyse kullanılıyor
- Medya üretiminde saçma/hallucinated kapanış metinleri kapatıldı:
  - Başarılı `generate_image` / `edit_image` / medya araçlarında final LLM kapanış turu atlanıyor
  - Kullanıcıya tool'un deterministik `message` alanı gösteriliyor
  - Tool call ile birlikte gelen initial planning text artık non-stream akışta kullanıcıya direkt yazılmıyor
- SSE chat mesaj kalıcılığı güçlendirildi:
  - Stream assistant mesajı baştan placeholder olarak DB'ye yazılıyor
  - Token ve asset geldikçe aynı mesaj incremental update ediliyor
  - Backend restart/stream kopması olsa bile asset kaydı ile chat mesajı birbirinden kopmuyor
- Referans video akışı yapılandırıldı:
  - Frontend artık referans videoyu metin içine markdown link olarak gömmek yerine structured alanla backend'e iletiyor
  - Aktif referans video varsa working memory asset listesi bu istekte baskılanıyor
  - Eski asset anotasyonları history'den temizlenerek prompt sızıntısı azaltıldı
  - Agent attached video varken yanlışlıkla `generate_video` seçerse akış `edit_video`ya reroute ediliyor
  - Referans video yoksa ve kullanıcı `önceki/ilk/son video` diyorsa session asset'lerinden doğru video seçilmeye çalışılıyor
- Video düzenleme (`edit_video`) akışı arka plana alındı:
  - `önceki videoyu anime yap` gibi istekler artık SSE request'ine bağlı kalmıyor
  - Sayfa yenilense bile iş iptal olmak yerine arka planda devam ediyor
  - Video edit talepleri de `generation_start` + WebSocket progress ile progress card gösterecek
- Boş pending assistant mesajları temizlendi:
  - SSE bağlantısı client tarafından kapanırsa içerik üretmeden kalan placeholder mesaj siliniyor
  - Session history endpoint'i legacy boş/pending assistant kayıtlarını geri döndürmüyor
- Gizli `ltx-video` fallback'i sistemden çıkarıldı:
  - `edit_video` akışı artık admin panelini bypass eden legacy `fal-ai/ltx-video` yolunu kullanmıyor
  - Video edit sadece admin tarafından yönetilen ve açık olan modellerle çalışıyor
  - Stil/anime video düzenleme akışında kare çıkarma + stil uygulama + yönetilen video modeli zinciri kullanılıyor
- `edit_video` başarısız olunca yanlış tool fallback'i kapatıldı:
  - Video düzenleme preflight veya tool seviyesinde hata alırsa sistem artık kafasına göre `generate_video` / `sora2` gibi alakasız bir t2v akışına düşmüyor
  - Kullanıcı doğrudan video edit hatasını chat içinde görüyor
- Doğrudan `video_url` ile gelen video edit isteklerinde kayıtlı referans kare tekrar kullanılıyor:
  - Eğer video asset'in `thumbnail_url` veya `model_params.source_image` verisi varsa, yeniden frame extraction zorunlu olmadan edit akışına taşınıyor
  - Bu sayede önceki videoyu düzenleme akışında gereksiz preflight hataları azaltıldı
- Tüm kullanıcıya görünen hata mesajları Türkçe ve normalize hale getirildi:
  - Yeni servis: `backend/app/services/user_error_formatter.py`
  - SSE stream, WebSocket progress error ve arka plan video/video-edit/long-video hata mesajları artık tek merkezden formatlanıyor
  - Teknik metinler (`stderr de boş`, `subprocess`, `quota`, `timeout` vb.) kullanıcı dostu Türkçe açıklamaya çevriliyor
- Yerel video edit retest'inde başarılı çıktı alındı:
  - Referanslı video üzerinden yeniden üretim akışında kullanıcı tarafından iyi kalite sonucu doğrulandı
  - Kapsamlı uçtan uca regresyon testi bir sonraki gün yeni proje üzerinde tekrar yapılacak
- Bilinçli asistan bilgilendirme sistemi (Smart Reassurance v2):
  - Video üretimi sırasında asistan artık robotik sabit zamanlayıcı yerine **olay bazlı bilinçli mesajlar** gönderiyor
  - Uzun video: sahne tamamlandığında ("Sahne 2/4 bitti! Sıradaki başlıyor"), FFmpeg başladığında ("Sahneler birleştiriliyor!")
  - Tüm video tipleri: 3+ dk sessizlik olursa geçen süre ve durum bilgisiyle bağlamsal mesaj ("14. dakikadayız, 3/4 sahne hazır")
  - `progress_service.send_reassurance()` → DB'ye gerçek assistant mesajı + WebSocket `reassurance` tipi
  - Frontend `ChatPanel.tsx` → `reassurance` mesajını gerçek chat baloncuğu olarak gösteriyor (duplicate korumalı)

### ✅ ÇÖZÜLDÜ: "Tekrar dene" komutunda yanlış referans görseli kullanımı
- **Sorun:** Kullanıcı "tekrar dene" / "beğenmedim" dediğinde orchestrator eski session asset'lerinden yanlış referans görseli çekiyordu
- **Çözüm (3 vektör):**
  1. `_is_explicit_session_asset_request`: Retry mesajları artık diskalifiye — "tekrar dene" AÇIK asset referansı DEĞİL
  2. Working Memory talimatı: LLM'ye "retry mesajlarında bu URL'leri image_url olarak VERME" uyarısı eklendi
  3. `_session_reference_images` cache: Her request başında stale referanslar temizleniyor
- **Durum:** ✅ Düzeltildi — `fix/reference-image-bug` branch

### 🔮 Gelecek Plan: Task İptal Mekanizması
- 30+ dk süren üretimlerde asistan "Çok uzun sürdü, iptal edip yeniden başlayalım mı?" önerisi yapabilmeli
- Backend'de `asyncio.Task` referansları session bazlı saklanmalı, `task.cancel()` ile durdurulabilmeli
- Frontend'de iptal butonu + kullanıcı "iptal et" yazarsa chat handler'dan tetikleme
- fal.ai request_id ile üretim iptali de desteklenmeli
- Bu özellik henüz uygulanmadı — planlama ve tasarım gerektirir
