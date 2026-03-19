# Pepper Root AI Agency — Proje Dokümantasyonu

> **Son Güncelleme:** 19 Mart 2026
> **Repo:** [github.com/aemregul/PepperRootAiAgency](https://github.com/aemregul/PepperRootAiAgency)

Bu dosya projenin tüm özelliklerini, mimarisini ve nasıl çalıştığını açıklar. Yeni bir AI oturumu veya ekip üyesi bu dosyayı okuyarak projeyi tamamen anlayabilir.

cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev

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

## 🚀 Aktif Özellikler (19 Mart 2026)

### Entity İsim Değiştirme (update_entity) _(19 Mart 2026)_

- Kullanıcı chat'ten entity ismini değiştirebilir
- Deterministic yanıt — markdown bold (**) kaldırıldı
- Dosya: `backend/app/services/agent/orchestrator.py`

### Model Seçimi Fix & LLM Override _(18 Mart 2026)_

- Kullanıcı mesajından model tespiti, LLM override koruması
- Model seçimi normalizasyonu, referans pipeline sırası düzeltildi
- Self-Reflection yanlış tetiklenme sorunu çözüldü
- Nano Banana 2 API parametreleri düzeltildi + fallback zinciri
- Dosya: `backend/app/services/agent/orchestrator.py`, `backend/app/services/plugins/fal_plugin_v2.py`

### Sosyal Medya Görseli Üretim Zekası _(18 Mart 2026)_

- Agent, marka entity'si + format bilgisi kullanarak sosyal medya görselleri üretir
- Instagram hikaye (1080x1920), post (1080x1080), Facebook kapak vb. formatlar
- Dosya: `backend/app/services/agent/orchestrator.py`, `backend/app/services/agent/tools.py`

### Markdown Mesaj Render (react-markdown) _(16 Mart 2026)_

- Asistan mesajları `react-markdown` ile render ediliyor — **bold**, *italic*, başlıklar, listeler, kod blokları düzgün görünüyor
- `MarkdownContent` component'ı: özel styled heading, paragraph, list, code, blockquote, link, image, video, audio component'ları
- @mention desteği: `@tag` → `[@tag](#mention)` pre-processing + yeşil `.mention` CSS class ile render
- Kullanıcı mesajları hâlâ basit `renderContent` fonksiyonu ile render ediliyor
- Dosya: `frontend/src/components/ChatPanel.tsx`

### Entity Oluşturma Deterministic Yanıtları _(14-16 Mart 2026)_

- Karakter/lokasyon/marka oluşturulduğunda generic LLM yanıtı yerine deterministic onay mesajı
- Her bilgi ayrı satırda (markdown `\n\n`), emoji ile formatlanmış
- Tag'de çift `@` sorunu çözüldü (`tag_display` kontrol mekanizması)
- Preset oluşturma mesajı da aynı formatta düzeltildi
- Dosya: `backend/app/services/agent/orchestrator.py`

### AI Yanıt Formatlama & Emoji Kullanımı _(16 Mart 2026)_

- System prompt'a `YANIT FORMATLAMA` bölümü eklendi
- Bölüm başlıklarında emoji, madde işaretlerinde konuya uygun emoji
- ChatGPT tarzı profesyonel, temiz, okunaklı format
- Saf metin duvarları yasaklandı

### Ünlü Kişi Fotoğraf Kaydetme Bypass'ı _(16 Mart 2026)_

- Kullanıcı fotoğraf + isim verdiğinde AI kişiyi tanımaya çalışmıyor
- Verilen isimle `create_character` çağrılıp fotoğraf referans görseli olarak kaydediliyor
- "tanıyamıyorum" yanıtları yasaklandı (system prompt kural 9)
- Dosya: `backend/app/services/agent/orchestrator.py`

### Çöp Kutusu Cache Fix _(14 Mart 2026)_

- Silinen öğelerin ilk sayfa yenilemede geri gelme sorunu düzeltildi
- Cache invalidation stratejisi iyileştirildi
- Kalıcı silme ID uyumsuzluğu düzeltildi
- Dosya: `backend/app/api/routes/sessions.py`, `frontend/src/components/TrashModal.tsx`

### Production Progress Card

- Video/görsel/ses üretimi sırasında chat'te gerçek zamanlı ilerleme kartı
- İki sütunlu tasarım: sol tarafta mini chat log, sağ tarafta dairesel progress
- Uzun videolarda sahne göstergeleri (✓ S1, ⏳ S2, ○ S3...)
- Card **sadece backend üretimi başlattığında** açılır (keyword değil, event bazlı)
- Bilinçli asistan mesajları card mini-log'unda görünür

### Task Cancellation (İptal Mekanizması)

- Production card'ın sağ üstünde kırmızı ✕ iptal butonu
- Frontend: `AbortController.abort()` ile SSE stream kesilir
- Backend: `POST /chat/cancel-task` → `cancel_session_task()` → `asyncio.Task.cancel()`
- Session bazlı `_active_bg_tasks` registry — video, edit_video, long_video takibi
- İptal sonrası chat'e "🛑 İşlem iptal edildi" mesajı eklenir

### Duplicate Video Guard

- GPT-4o recursive retry'larda tekrar `generate_long_video` çağırsa bile sadece ilk video çalışır
- `_video_already_called` flag'i `result` dict'inde saklanır, recursive çağrılarda korunur

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

- **Chat Paneli**: SSE streaming, çoklu görsel yükleme (10'a kadar), ChatGPT tarzı medya düzeni, `react-markdown` ile zengin mesaj formatı
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
| 35    | 14 Mart    | Trash Cache Fix, Entity Response Fix                    |
| 36    | 16 Mart    | Markdown Render, Emoji Format, Celebrity Photo Bypass   |
| 37    | 18 Mart    | Sosyal Medya Görseli, Model Seçimi Fix, Entity Rename   |
| 38    | 19 Mart    | Workflow, GitHub Actions CI/CD, Proje Config            |

---

## 📊 Proje İstatistikleri

| Metrik         | Değer   |
| -------------- | ------- |
| Agent Araç     | 36      |
| AI Model       | 33      |
| Toplam Faz     | 38      |
| Canlı Backend  | Railway |
| Canlı Frontend | Vercel  |

---

## �️ ROADMAP — Öncelik Sıralı Geliştirme Planı

> **Oluşturulma:** 10 Mart 2026
> **Kural:** Her madde branch'ta geliştirilecek, test edilecek, sonra main'e merge edilecek.

---

### 🔴 Faz 1 — Kritik Bug Fix'ler (Öncelik: EN YÜKSEK)

Bu maddeler çözülmeden yeni özelliğe geçilmez.

- [x] **1.1 — Chat Yavaşlık & Yanıtsızlık Sorunu** _(Düzeltildi)_
  - SSE stream timeout, long video NameError, fal upload greenlet, trash cleanup import — tümü düzeltildi

- [x] **1.2 — "Beni Hatırla" Çalışmıyor** _(Test edildi, sorun bulunamadı)_

- [x] **1.3 — Görsel Silindiğinde Çöp Kutusuna Gitmiyor** _(Düzeltildi)_
  - `user_id` TrashItem'a set + frontend etiket düzeltmeleri

- [ ] **1.4 — Videodan Entity Kaydederken Referans Görsel Sorunu**
  - Sorun: Video URL (.mp4) `reference_image_url` olarak kaydediliyor → görsel modelleri çalışmıyor
  - Çözüm: Video URL tespit → FFmpeg ile thumbnail çıkart → `reference_image_url` olarak kullan
  - Etki alanı: `backend/app/services/entity_service.py`, `backend/app/services/agent/orchestrator.py`

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

- [x] **3.3 — Marka Bazlı Reklam Afişi & Sosyal Medya Görseli Üretimi** _(18 Mart 2026 — Tamamlandı)_
  - Agent marka entity'si + format bilgisini kullanarak sosyal medya görselleri üretir
  - Desteklenen formatlar: Instagram hikaye/post, Facebook kapak, banner
  - Etki alanı: `backend/app/services/agent/orchestrator.py`, `backend/app/services/agent/tools.py`

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
