=============================================================================
PROJE BAŞLIĞI: LocalFlow (Geçici İsim) - Yerel Veri Etiketleme Aracı
TÜR: Masaüstü Uygulaması (Desktop Application)
DURUM: Tasarım Aşamasında
=============================================================================

1. PROJE ÖZETİ VE KAPSAM
-----------------------------------------------------------------------------
Bu proje, bilgisayarlı görü (Computer Vision) projeleri için kullanıcıların
yerel bilgisayarlarında (offline) çalıştırabilecekleri, bulut tabanlı sistemlere
(örn. Roboflow) alternatif, gizlilik odaklı ve ücretsiz bir veri etiketleme
ve veri seti yönetim aracı geliştirmeyi hedefler.

2. FONKSİYONEL GEREKSİNİMLER (FUNCTIONAL REQUIREMENTS)
-----------------------------------------------------------------------------

2.1. TEMEL ETİKETLEME MODÜLLERİ (CORE ANNOTATION)
   [FR-01] Çoklu Görev Desteği:
           Sistem aşağıdaki üç temel görev tipini desteklemelidir:
           - Object Detection (Nesne Tespiti): Bounding Box (Kutu) çizimi.
           - Instance Segmentation (Bölütleme): Polygon (Çokgen) çizimi.
           - Classification (Sınıflandırma): Görsele tekil etiket atama.

   [FR-02] Sınıf (Class) Yönetimi:
           - Kullanıcı sınıfları ekleyebilmeli, silebilir ve düzenleyebilmelidir.
           - Her sınıf için özelleştirilebilir renk ataması yapılmalıdır.
           - Sınıflar bir konfigürasyon dosyası (örn. classes.txt) üzerinden
             içe/dışa aktarılabilmelidir.

2.2. AI DESTEKLİ OTOMATİK ETİKETLEME (SMART LABELING)
   [FR-03] Tıkla-Etiketle (Click-to-Label / SAM Entegrasyonu):
           - Kullanıcı bir nesneye tıkladığında, entegre "Segment Anything Model"
             (SAM veya MobileSAM) nesnenin sınırlarını otomatik olarak algılayıp
             Polygon veya Bounding Box oluşturmalıdır.

   [FR-04] Model Destekli Etiketleme (Model-Assisted Labeling):
           - "Active Learning" akışı desteklenmelidir:
           1. Kullanıcı veri setinin küçük bir kısmını (örn. %10-20) manuel etiketler.
           2. Sistem bu küçük veri ile arka planda hafif bir model (örn. YOLO-Nano) eğitir.
           3. Eğitilen model, kalan veriyi (%80) otomatik olarak etiketler.
           4. Kullanıcı sadece hatalı tahminleri düzeltir.

2.3. VERİ YÖNETİMİ VE İŞLEME (DATA PIPELINE)
   [FR-05] İçe Aktarım (Import) ve Format Desteği:
           - Resim klasörleri ve video dosyaları (karelere ayrılarak) yüklenebilmelidir.
           - Mevcut etiket formatları (YOLO txt, Pascal VOC xml, COCO json)
             okunabilmelidir.

   [FR-06] Dışa Aktarım ve Dönüşüm (Export & Convert):
           - Etiketlenen veriler, kullanıcı tarafından seçilen hedef formata
             otomatik dönüştürülerek kaydedilmelidir.
           - Desteklenen Çıktılar: YOLOv5/v8, COCO, Pascal VOC, TFRecord.

   [FR-07] Veri Seti Bölme (Dataset Splitting):
           - Kullanıcı, veri setini görsel bir arayüz (slider) ile
             Train (Eğitim), Validation (Doğrulama) ve Test setlerine ayırabilmelidir.
           - Bölme işlemi rastgele (random) veya sıralı yapılabilmelidir.

   [FR-08] Veri Artırma (Data Augmentation):
           - Entegre bir "Augmentation Pipeline" bulunmalıdır.
           - Seçenekler: Rotate, Flip, Noise, Blur, Brightness/Contrast, Crop.
           - Kullanıcı parametreleri seçtiğinde anlık önizleme (preview) sunulmalıdır.
           - Dışa aktarım sırasında veriler seçilen katsayı kadar çoğaltılmalıdır.

3. TEKNİK VE SİSTEM GEREKSİNİMLERİ (NON-FUNCTIONAL)
-----------------------------------------------------------------------------
   [NFR-01] Yerellik ve Gizlilik (Local-First):
            - Uygulama çalışmak için internet bağlantısına ihtiyaç duymamalıdır.
            - Hiçbir veri (görsel veya etiket) harici bir sunucuya gönderilmemelidir.

   [NFR-02] Performans:
            - Büyük veri setleri (10.000+ görsel) ile çalışırken arayüz donmamalıdır.
            - "Lazy Loading" teknikleri kullanılmalıdır.

   [NFR-03] Uyumluluk:
            - Windows, Linux ve macOS işletim sistemlerinde çalışabilir olmalıdır
              (Cross-Platform).

4. KULLANICI ARAYÜZÜ (UI/UX)
-----------------------------------------------------------------------------
   - Klavye kısayolları (Shortcuts) ile hızlı etiketleme (Örn: 'W' tuşu ile kutu çizme).
   - Karanlık Mod (Dark Mode) desteği.
   - Yakınlaştırma (Zoom) ve Kaydırma (Pan) gibi tuval kontrolleri akıcı olmalıdır.

=============================================================================

5. PROJE YOL HARİTASI (ROADMAP)
-----------------------------------------------------------------------------
Proje, teknik riskleri yönetmek ve kullanıcıya en hızlı şekilde değer
sağlamak amacıyla "Yinelemeli Geliştirme" (Iterative Development) modeli
ile ilerleyecektir.

v0.5: Prototip (Internal Alpha)
Amaç: Arayüz iskeletini kurmak ve temel tuval (canvas) mimarisini doğrulamak.
* Özellikler:
    * Klasörden resim yükleme ve dosya listesi görüntüleme.
    * Tuval kontrolleri: Yakınlaştırma (Zoom) ve Kaydırma (Pan).
    * Temel çizim testi: Bounding Box (Kutu) çizimi (kayıt özelliği olmadan).
* Teknoloji: Python, PySide6, QGraphicsScene.

### v1.0: MVP (Temel Sürüm) - "Modern LabelImg"
Amaç: "LabelImg" gibi eski araçların yerini alabilecek, stabil ve üretimde kullanılabilir ilk sürüm.
* Kapsam: Sadece Manuel Etiketleme ve Kayıt.
* İsterler:
    * `[FR-01]` Temel Çizim: Bounding Box ve Polygon (Manuel).
    * `[FR-02]` Sınıf Yönetimi: Sınıf ekleme/silme, renk atama (`classes.txt`).
    * `[FR-05]` İçe Aktarım: Klasör bazlı resim yükleme.
    * `[FR-06]` Dışa Aktarım (Temel): YOLO (.txt) formatında kaydetme.
    * `[NFR-01]` Çevrimdışı: İnternet bağlantısı olmadan tam fonksiyonellik.

### v1.5: Fark Yaratan Sürüm - "Veri Seti Yöneticisi"
Amaç: Rakiplerde bulunmayan veri işleme özelliklerini sunarak kullanıcı kitlesini genişletmek.
* Kapsam: Veri Artırma (Augmentation) ve Veri Seti Bölümleme.
* İsterler:
    * `[FR-08]` Augmentation Pipeline: Albumentations entegrasyonu (Döndürme, Gürültü, Parlaklık vb.) ve anlık önizleme.
    * `[FR-07]` Veri Bölme: Train/Validation/Test ayrımı için görsel arayüz.
    * `[FR-06]` Dışa Aktarım (Genişletilmiş): COCO (.json) ve Pascal VOC (.xml) desteği.
* Strateji: AI entegrasyonundan önce bu özellikleri eklemek, teknik karmaşıklığa girmeden ürüne "Benzersiz Değer" (USP) katar.

### v2.0: Akıllı Sürüm - "AI Assistant"
Amaç: Manuel iş yükünü azaltarak etiketleme hızını maksimize etmek.
* Kapsam: SAM (Segment Anything Model) Entegrasyonu.
* İsterler:
    * `[FR-03]` Tıkla-Etiketle: ONNX Runtime üzerinden `MobileSAM` entegrasyonu ile tek tıkla maske oluşturma.
    * `[NFR-02]` Performans: AI işlemleri sırasında arayüzün donmaması için Threading/Worker yapısının kurulması.

### v3.0: Profesyonel Sürüm - "Active Learning"
Amaç: Veri döngüsünü uygulama içinde tamamlamak (En riskli ve son aşama).
* Kapsam: Uygulama içi model eğitimi ve otomatik etiketleme döngüsü.
* İsterler:
    * `[FR-04]` Model Destekli Etiketleme: Arka planda hafif modellerin (örn. YOLO-Nano) eğitilmesi ve etiketlenmemiş verinin otomatik tahminlenmesi.
* Not: Bu sürüm yüksek donanım gereksinimi yaratabileceğinden opsiyonel modül olarak tasarlanacaktır.