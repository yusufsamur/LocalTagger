# LocalFlow 🏷️

**AI Destekli Yerel Veri Etiketleme Aracı** - MobileSAM entegrasyonu ile otomatik segmentasyon, gizlilik odaklı, tamamen offline çalışan veri etiketleme ve veri seti yönetim uygulaması.

## ✨ Özellikler

### 🤖 AI Destekli Etiketleme (MobileSAM)
- **Tıkla → Otomatik etiket**: Nesneye tıkla, AI otomatik BBox veya Polygon çıkarsın
- Arka planda çalışır, UI donmaz
- `T` tuşu ile AI'ı aç/kapat

### 📝 Manuel Etiketleme
- ⬜ Bounding Box çizimi
- ◇ Polygon çizimi
- Düzenlenebilir köşeler ve taşıma

### � Export Formatları
- **YOLO**: v5-v11 (txt)
- **COCO**: JSON formatı
- **Pascal VOC**: XML formatı
- **Custom**: Özel TXT/JSON şablonları

### 🔧 Veri Yönetimi
- Veri artırma (Augmentation): Brightness, contrast, rotation, flip, shear, cutout, motion blur
- Train/Val/Test bölümleme
- Resize seçenekleri

## 🚀 Kurulum

```bash
# Sanal ortam oluştur
python -m venv venv

# Sanal ortamı aktifleştir (Windows)
venv\Scripts\activate

# Bağımlılıkları yükle
pip install -r requirements.txt

# Uygulamayı çalıştır
python src/main.py
```

## ⌨️ Kısayollar

| Tuş | İşlev |
|-----|-------|
| `T` | AI Toggle (MobileSAM) |
| `W` | BBox çizim modu |
| `E` | Polygon çizim modu |
| `Q` | Seç/Düzenle modu |
| `A` / `D` | Önceki/Sonraki görsel |
| `Ctrl+S` | Kaydet |
| `Ctrl+E` | Dışa Aktar |
| `Del` | Seçili etiketi sil |
| `ESC` | Çizimi iptal |

## 📋 Gereksinimler

- Python 3.10+
- Windows / Linux / macOS
- MobileSAM ONNX modelleri (`src/resources/models/`)

## 🗺️ Yol Haritası

- [x] v0.5: Prototip - Temel tuval ve navigasyon
- [x] v1.0: MVP - Manuel etiketleme ve kayıt
- [x] v1.5: Veri Seti Yöneticisi - Augmentation ve bölümleme
- [x] v2.0: AI Assistant - MobileSAM entegrasyonu ✨
- [ ] v3.0: Active Learning - Model eğitimi

## 📄 Lisans

MIT License
