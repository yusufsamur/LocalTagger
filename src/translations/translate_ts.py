#!/usr/bin/env python3
"""
Complete XML-aware Turkish translation script for tr.ts file.
Uses ElementTree to safely parse and modify XML without corrupting structure.
"""
import xml.etree.ElementTree as ET

# Complete translation dictionary - English to Turkish
translations = {
    # AnnotationListWidget
    '📊 Annotation Summary': '📊 Etiket Özeti',
    'Delete all annotations': 'Tüm etiketleri sil',
    'No image selected': 'Görsel seçilmedi',
    'No annotations - Start drawing': 'Etiket yok - Çizim yapın',
    'Total: {} ({})': 'Toplam: {} ({})',
    
    # ClassManagementDialog - Headers
    'Class Management': 'Sınıf Yönetimi',
    '🏷️ Label Classes': '🏷️ Etiket Sınıfları',
    'Class Name': 'Sınıf Adı',
    'Color': 'Renk',
    'Labels': 'Etiketler',
    'Images': 'Görseller',
    'Count in Project': 'Projede Sayısı',
    
    # ClassManagementDialog - Buttons with emojis
    'Add Class': 'Sınıf Ekle',
    '➕ Add New Class': '➕ Yeni Sınıf Ekle',
    'Add New Class': 'Yeni Sınıf Ekle',
    '✏️ Rename': '✏️ Yeniden Adlandır',
    'Rename': 'Yeniden Adlandır',
    '🎨 Change Color': '🎨 Renk Değiştir',
    'Change Color': 'Renk Değiştir',
    '🗑️ Delete': '🗑️ Sil',
    'Delete': 'Sil',
    'Close': 'Kapat',
    
    # ClassManagementDialog - Dialogs
    'Enter Class Name': 'Sınıf Adı Girin',
    'Class Name:': 'Sınıf Adı:',
    'Class name:': 'Sınıf adı:',
    'Pick a Color': 'Renk Seçin',
    'Warning': 'Uyarı',
    'Please select a class.': 'Lütfen bir sınıf seçin.',
    'Rename Class': 'Sınıfı Yeniden Adlandır',
    'New name:': 'Yeni ad:',
    'Merge Classes': 'Sınıfları Birleştir',
    'Merge Complete': 'Birleştirme Tamamlandı',
    'Select Class Color': 'Sınıf Rengi Seç',
    'Warning!': 'Uyarı!',
    'Delete Class': 'Sınıfı Sil',
    'Class Deleted': 'Sınıf Silindi',
    
    # ExportWizard - Steps
    'Export Wizard': 'Dışa Aktarma Sihirbazı',
    'Step 1/3: Dataset Split': 'Adım 1/3: Veri Seti Bölme',
    'Step 2/3: Augmentation': 'Adım 2/3: Augmentation',
    'Step 3/3: Format & Export': 'Adım 3/3: Format ve Dışa Aktarma',
    '← Back': '← Geri',
    'Cancel': 'İptal',
    'Cancel Export': 'Export İptal',
    'Next →': 'İleri →',
    'Total images: {}': 'Toplam görsel: {}',
    '📊 Total {} images': '📊 Toplam {} görsel',
    
    # ExportWizard - Dataset Split
    'Enable Dataset Split': 'Veri Seti Bölmeyi Etkinleştir',
    'Adjust split ratios by dragging': 'Bölme Oranlarını sürükleyerek ayarlayın',
    'Split Ratios (drag to adjust)': 'Bölme Oranları (sürükleyerek ayarlayın)',
    'Shuffle Settings': 'Karıştırma Ayarları',
    'Shuffle Data': 'Verileri Karıştır',
    'Unlabeled Files': 'Etiketsiz Dosyalar',
    'Include unlabeled images': 'Etiketsiz görselleri dahil et',
    'Include Unlabeled': 'Etiketsiz Görselleri Dahil Et',
    'If disabled, only labeled files will be exported': 'Devre dışı bırakılırsa, yalnızca etiketli dosyalar export edilir',
    '📊 {} labeled, {} unlabeled files': '📊 {} etiketli, {} etiketsiz dosya',
    'Seed': 'Seed',
    'Split Preview': 'Bölme Önizlemesi',
    'train': 'eğitim',
    'Train': 'Eğitim',
    'val': 'doğrulama',
    'Val': 'Doğrulama',
    'test': 'test',
    'Test': 'Test',
    
    # ExportWizard - Augmentation
    'Enable Augmentation': 'Augmentation Etkinleştir',
    'Enable augmentation': 'Augmentation etkinleştir',
    'Multiplier': 'Çarpan',
    'Multiplier:': 'Çarpan:',
    'Resize': 'Yeniden Boyutlandır',
    'Enable Resize': 'Yeniden Boyutlandırmayı Etkinleştir',
    'Size': 'Boyut',
    'Size:': 'Boyut:',
    'Mode:': 'Mod:',
    'Augmentation': 'Augmentation',
    'Augmentation Parameters': 'Augmentation Parametreleri',
    'Brightness': 'Parlaklık',
    '{}%': '{}%',
    'Value': 'Değer',
    'Value:': 'Değer:',
    'Brighten': 'Aydınlat',
    'Darken': 'Karart',
    'Random': 'Rastgele',
    'Flip': 'Çevir',
    'Horizontal Flip': 'Yatay Çevirme',
    'Vertical Flip': 'Dikey Çevirme',
    'Horizontal': 'Yatay',
    'Horizontal:': 'Yatay:',
    'Vertical': 'Dikey',
    'Vertical:': 'Dikey:',
    'Blur': 'Bulanıklık',
    'Noise': 'Gürültü',
    'Variance': 'Varyans',
    'Grayscale': 'Gri Tonlama',
    'Ratio': 'Oran',
    'Rate:': 'Oran:',
    'Exposure': 'Pozlama',
    'Rotation': 'Döndürme',
    'Range (±)': 'Aralık (±)',
    'Cutout': 'Cutout',
    'Count': 'Adet',
    'Count:': 'Adet:',
    'Motion Blur': 'Hareket Bulanıklığı',
    'Shear': 'Kesme',
    'X': 'X',
    'Y': 'Y',
    'Contrast': 'Kontrast',
    'Hue': 'Renk Tonu',
    'Live Preview': 'Canlı Önizleme',
    'Show Preview on Hover': 'Hover Önizlemesi',
    'No preview available': 'Önizleme mevcut değil',
    'Loading preview...': 'Önizleme yükleniyor...',
    'No image selected for preview': 'Önizleme için görsel seçilmedi',
    
    # ExportWizard - Format & Export
    'Export Format': 'Export Formatı',
    'Type': 'Tip',
    'Type:': 'Tip:',
    'Output Path': 'Çıkış Yolu',
    'Output Folder': 'Çıkış Klasörü',
    'Browse': 'Gözat',
    '📁 Browse...': '📁 Gözat...',
    'Select output folder...': 'Çıkış klasörü seçin...',
    'Select Output Folder': 'Çıkış Klasörünü Seçin',
    'Format & Export': 'Format ve Dışa Aktarma',
    'Format & Export': 'Format ve Dışa Aktarma',
    'Dataset Split': 'Veri Seti Bölme',
    'Step {}/3: {}': 'Adım {}/3: {}',
    '📦 Export': '📦 Dışa Aktar',
    'Export': 'Dışa Aktar',
    'Starting export...': 'Export başlatılıyor...',
    'Exporting: {}/{}': 'Export ediliyor: {}/{}',
    'Success': 'Başarılı',
    'Error': 'Hata',
    'No output path selected': 'Çıkış yolu seçilmedi',
    'Creating directories...': 'Dizinler oluşturuluyor...',
    'Loading annotations...': 'Etiketler yükleniyor...',
    'Applying augmentations...': 'Augmentasyonlar uygulanıyor...',
    'Exporting images...': 'Görseller export ediliyor...',
    'Export completed!': 'Export tamamlandı!',
    'Export Complete': 'Export Tamamlandı',
    'export cancelled by user': 'export kullanıcı tarafından iptal edildi',
    'Export cancelled': 'Export iptal edildi',
    'Export failed': 'Export başarısız',
    
    # LocalTaggerApp - Window Title
    'LocalTagger - Data Annotation Tool': 'LocalTagger - Veri Etiketleme Aracı',
    
    # LocalTaggerApp - File Menu
    '&File': '&Dosya',
    'Open Folder...': 'Klasör Aç...',
    'Open File...': 'Dosya Aç...',
    'Save': 'Kaydet',
    'Save All': 'Tümünü Kaydet',
    'Export...': 'Dışa Aktar...',
    'Exit': 'Çıkış',
    
    # LocalTaggerApp - Edit Menu
    '&Edit': '&Düzenle',
    '🏷️ Class Management...': '🏷️ Sınıf Yönetimi...',
    'Delete Selected Annotation': 'Seçili Etiketi Sil',
    'Clear All Annotations': 'Tüm Etiketleri Temizle',
    'Undo': 'Geri Al',
    'Redo': 'Yinele',
    
    # LocalTaggerApp - View Menu
    '&View': '&Görünüm',
    'Zoom In': 'Yakınlaştır',
    'Zoom Out': 'Uzaklaştır',
    'Fit to Window': 'Sığdır',
    'Actual Size': 'Gerçek Boyut',
    
    # LocalTaggerApp - Language Menu
    '&Language': '&Dil',
    'English': 'English',
    'Türkçe': 'Türkçe',
    
    # LocalTaggerApp - Help Menu
    '&Help': '&Yardım',
    'About LocalTagger': 'LocalTagger Hakkında',
    'About': 'Hakkında',
    
    # LocalTaggerApp - Status Messages
    'Ready - Press Ctrl+O to open a folder': 'Hazır - Klasör açmak için Ctrl+O tuşlarına basın',
    'The language will be fully applied after restarting the application.': 'Dil, uygulama yeniden başlatıldıktan sonra tam olarak uygulanacaktır.',
    '✓ BBox added: {}': '✓ BBox eklendi: {}',
    'BBox cancelled': 'BBox iptal edildi',
    '✓ Polygon added: {}': '✓ Polygon eklendi: {}',
    'Polygon cancelled': 'Polygon iptal edildi',
    '✓ AI Polygon class: {}': '✓ AI Polygon sınıfı: {}',
    'AI Polygon cancelled': 'AI Polygon iptal edildi',
    'Class: {}': 'Sınıf: {}',
    '✓ BBox updated and saved': '✓ BBox güncellendi ve kaydedildi',
    '✓ BBox deleted': '✓ BBox silindi',
    '✓ BBox class updated: {}': '✓ BBox sınıfı güncellendi: {}',
    '✓ Polygon updated and saved': '✓ Polygon güncellendi ve kaydedildi',
    '✓ Polygon deleted': '✓ Polygon silindi',
    '✓ Polygon class updated: {}': '✓ Polygon sınıfı güncellendi: {}',
    'Select': 'Seç',
    'Tool: {}': 'Araç: {}',
    'Classes updated': 'Sınıflar güncellendi',
    'Nothing to undo': 'Geri alınacak bir şey yok',
    '↩️ Undone': '↩️ Geri alındı',
    'Undo failed': 'Geri alma başarısız',
    'Nothing to redo': 'Yinelenecek bir şey yok',
    '↪️ Redone': '↪️ Yinelendi',
    'Redo failed': 'Yineleme başarısız',
    'No image to copy from!': 'Kopyalanacak görsel yok!',
    '📋 {} selected annotation(s) copied': '📋 {} seçili etiket kopyalandı',
    'Selected annotation not found': 'Seçili etiket bulunamadı',
    'Select an annotation first to copy': 'Kopyalamak için önce bir etiket seçin',
    'No image to paste to!': 'Yapıştırılacak görsel yok!',
    'Nothing to paste (copy with Ctrl+C first)': 'Yapıştırılacak bir şey yok (önce Ctrl+C ile kopyalayın)',
    '📋 {} annotation(s) pasted': '📋 {} etiket yapıştırıldı',
    'No image to delete from!': 'Silinecek görsel yok!',
    'No annotations to delete': 'Silinecek etiket yok',
    'Delete Annotations': 'Etiketleri Sil',
    'Delete {} annotation(s)?': '{} etiket silinsin mi?',
    '🗑️ {} annotation(s) deleted': '🗑️ {} etiket silindi',
    'Confirm': 'Onayla',
    'Are you sure you want to delete all annotations?': 'Tüm etiketleri silmek istediğinizden emin misiniz?',
    'Image Files (*.jpg *.jpeg *.png *.bmp *.gif)': 'Görsel Dosyaları (*.jpg *.jpeg *.png *.bmp *.gif)',
    'Open Images': 'Görselleri Aç',
    'Select Folder': 'Klasör Seç',
    'Language Changed': 'Dil Değiştirildi',
    'Language changed to {}. Please restart the application.': 'Dil {} olarak değiştirildi. Lütfen uygulamayı yeniden başlatın.',
    
    # About dialog content
    'LocalTagger - Data Annotation Tool': 'LocalTagger - Veri Etiketleme Aracı',
    'Version 2.0': 'Versiyon 2.0',
    'A powerful data annotation tool for machine learning datasets.': 'Makine öğrenmesi veri setleri için güçlü bir veri etiketleme aracı.',
    
    # Format types
    'YOLO': 'YOLO',
    'COCO': 'COCO',
    'Pascal VOC': 'Pascal VOC',
    'YOLO Detection': 'YOLO Detection',
    'YOLO Segmentation': 'YOLO Segmentation',
    'COCO Detection': 'COCO Detection',
    'COCO Segmentation': 'COCO Segmentation',
    
    # Additional strings
    'Select a class': 'Bir sınıf seçin',
    'No classes defined': 'Tanımlı sınıf yok',
    'images': 'görsel',
    'image': 'görsel',
    'annotations': 'etiket',
    'annotation': 'etiket',
    'label': 'etiket',
    'labels': 'etiketler',
    
    # New strings added for proper i18n
    # Export dialog - split summary
    'Split disabled - {} images to single folder': 'Split devre dışı - {} görsel tek klasöre yazılacak',
    '📂 Train: {} images | Val: {} images | Test: {} images': '📂 Train: {} görsel | Val: {} görsel | Test: {} görsel',
    # Export dialog - multiplier options
    '{}x → {} images (1 original + {} augmented)': '{}x → {} görsel (1 orijinal + {} augmented)',
    # Export dialog - export summary
    '📊 Total {} images to export': '📊 Toplam {} görsel dışa aktarılacak',
    
    # Class selector popup
    'Select Class (1-9 or Enter)': 'Sınıf Seç (1-9 veya Enter)',
    'ESC: Cancel': 'ESC: İptal',
    
    # Main window - tool buttons
    '⬜ BBox (W)': '⬜ BBox (W)',
    '◇ Polygon (E)': '◇ Polygon (E)',
    'BBox drawing mode': 'BBox çizim modu',
    'Polygon drawing mode': 'Polygon çizim modu',
    '✨ Magic Pixel': '✨ Magic Pixel',
    '📦 Magic Box': '📦 Magic Box',
    'Click to label - Point-based (T)': 'Tıklayarak etiketle - Nokta tabanlı (T)',
    'Draw bbox, AI refines - Box-based (Y)': 'BBox çiz, AI iyileştir - Kutu tabanlı (Y)',
    
    # Main window - Files panel
    '📁 Files (0)': '📁 Dosyalar (0)',
    '📁 Files ({})': '📁 Dosyalar ({})',
    'No folder opened': 'Klasör açılmadı',
    '✅ 0 labeled  ⭕ 0 unlabeled': '✅ 0 etiketli  ⭕ 0 etiketsiz',
    '✅ {} labeled  ⭕ {} unlabeled': '✅ {} etiketli  ⭕ {} etiketsiz',

    # File Dialogs
    'Select Image Folder': 'Görsel Klasörü Seç',
    'Select Images': 'Görsel Dosyaları Seç',
    'Image Files ({})': 'Görsel Dosyaları ({})',
    'Select Export Folder': 'Çıktı Klasörü Seç',

    # Missing Miscellaneous strings
    'Delete All': 'Tümünü Sil',
    'Are you sure you want to delete {} annotations from this image?': 'Bu görselden {} etiketi silmek istediğinize emin misiniz?',
    'This action cannot be undone!': 'Bu işlem geri alınamaz!',
    'No image to save!': 'Kaydedilecek görsel yok!',
    '✓ Saved: {}.txt': '✓ Kaydedildi: {}.txt',
    'No source folder!': 'Kaynak klasör yok!',
    '✓ {} file(s) saved': '✓ {} dosya kaydedildi',
    'Open a folder first!': 'Önce bir klasör açın!',
    'No images to export!': 'Dışa aktarılacak görsel yok!',
    'All annotations cleared': 'Tüm etiketler temizlendi',
    '📁 {} images, {} classes loaded': '📁 {} görsel, {} sınıf yüklendi',
    'No images found in folder!': 'Klasörde görsel bulunamadı!',
    '✓ {} classes loaded from data.yaml': '✓ data.yaml\'dan {} sınıf yüklendi',
    '🔍 Scanning label files...': '🔍 Etiket dosyaları taranıyor...',
    '🔍 Scanning... {}/{}': '🔍 Taranıyor... {}/{}',
    '📊 Loading annotations...': '📊 Etiketler yükleniyor...',
    '📊 Loading annotations... {}/{}': '📊 Etiketler yükleniyor... {}/{}',
    '🖼️ {} images loaded': '🖼️ {} görsel yüklendi',
    'Zoom: {}%': 'Yakınlaştırma: {}%',
    'Unsaved Changes': 'Kaydedilmemiş Değişiklikler',
    'There are unsaved changes. Do you want to exit without saving?': 'Kaydedilmemiş değişiklikler var. Kaydetmeden çıkmak istiyor musunuz?',
    '⏳ SAM model is loading, please wait...': '⏳ SAM modeli yükleniyor, lütfen bekleyin...',
    '🤖 AI mode enabled - Click on an object': '🤖 AI modu aktif - Bir nesneye tıklayın',
    '🤖 AI mode disabled': '🤖 AI modu devre dışı',
    '✓ SAM model loaded - Press T to enable AI': '✓ SAM modeli yüklendi - AI\'yı açmak için T\'ye basın',
    '❌ SAM model error: {}': '❌ SAM model hatası: {}',
    '⏳ Analyzing...': '⏳ Analiz ediliyor...',
    '✓ Ready': '✓ Hazır',
    '🤖 AI ready - Click on an object': '🤖 AI hazır - Bir nesneye tıklayın',
    '❌ SAM error: {}': '❌ SAM hatası: {}',
    '⏳ Please wait, analyzing image...': '⏳ Lütfen bekleyin, görsel analiz ediliyor...',
    '🔍 AI segmentation in progress... ({}, {})': '🔍 AI segmentasyonu devam ediyor... ({}, {})',
    '✓ AI Polygon created - Select class': '✓ AI Polygon oluşturuldu - Sınıf seçin',
    '❌ Could not read image: {}': '❌ Görsel okunamadı: {}',
    '🔲 Select (Q)': '🔲 Seç (Q)',
    'BBox selection and editing mode': 'BBox seçim ve düzenleme modu',
    '  Tool: BBox': '  Araç: BBox',
    '  Tool: {}': '  Araç: {}',
    '{} images': '{} görsel',
    'Model loading...': 'Model yükleniyor...',
}

# Multiline string translations (normalized without carriage returns)
multiline_translations = {
    "A class named '{}' already exists.\n\nWould you like to move all labels from '{}' class to '{}' class and merge them?\n\nThis action cannot be undone!": 
        "'{}' adında bir sınıf zaten mevcut.\n\n'{}' sınıfındaki tüm etiketleri '{}' sınıfına taşıyıp birleştirmek ister misiniz?\n\nBu işlem geri alınamaz!",
    
    "Class '{}' was merged with '{}'.\n\n{} labels were updated and saved.":
        "'{}' sınıfı '{}' ile birleştirildi.\n\n{} etiket güncellendi ve kaydedildi.",
    
    "There are {} labels belonging to '{}' class.\n\nDeleting this class will also DELETE ALL these labels.\n\nDo you want to continue?":
        "'{}' sınıfına ait {} etiket bulunmaktadır.\n\nBu sınıfı silmek tüm bu etiketleri de SİLECEKTİR.\n\nDevam etmek istiyor musunuz?",
    
    "Are you sure you want to delete '{}' class?":
        "'{}' sınıfını silmek istediğinizden emin misiniz?",
    
    "Class '{}' and {} labels were deleted.":
        "'{}' sınıfı ve {} etiket silindi.",
    
    "✓ {} images exported.\n\nLocation: {}":
        "✓ {} görsel export edildi.\n\nKonum: {}",
    
    "Export error:\n{}":
        "Export hatası:\n{}",
    
    # Tooltip translations
    "Brightness: Adjusts the light/dark level of the image.\n\n• Brighten: Lightens the image\n• Darken: Darkens the image\n• Value %: Effect intensity\n\nUsed for generalization under different lighting conditions.":
        "Parlaklık: Görüntünün açık/koyu seviyesini ayarlar.\n\n• Aydınlat: Görüntüyü açar\n• Karart: Görüntüyü koyulaştırır\n• Değer %: Efekt yoğunluğu\n\nFarklı aydınlatma koşullarında genelleme için kullanılır.",
        
    "Contrast: Adjusts the difference between light and dark tones.\n\n• 100%: Original contrast\n• <100%: Low contrast (more faded)\n• >100%: High contrast (sharper)\n\nUsed for generalization under different lighting conditions.":
        "Kontrast: Açık ve koyu tonlar arasındaki farkı ayarlar.\n\n• %100: Orijinal kontrast\n• <%100: Düşük kontrast (daha soluk)\n• >%100: Yüksek kontrast (daha keskin)\n\nFarklı aydınlatma koşullarında genelleme için kullanılır.",
        
    "Rotation: Rotates the image at random angles.\n\n• 0°: No rotation\n• 15°: Rotation in ±15° range\n• 45°: Rotation in ±45° range\n\nTeaches recognition of objects from different angles.":
        "Döndürme: Görüntüyü rastgele açılarda döndürür.\n\n• 0°: Döndürme yok\n• 15°: ±15° aralığında döndürme\n• 45°: ±45° aralığında döndürme\n\nFarklı açılardan nesne tanımayı öğretir.",
        
    "Flip: Mirrors the image.\n\n• Horizontal: Left-right mirroring\n• Vertical: Top-bottom mirroring\n• Percentage: Application probability\n\nProvides generalization for symmetric objects and different viewing angles.":
        "Çevirme: Görüntüyü aynalar.\n\n• Yatay: Sol-sağ aynalama\n• Dikey: Üst-alt aynalama\n• Yüzde: Uygulama olasılığı\n\nSimetrik nesneler ve farklı görüş açıları için genelleme sağlar.",

    # About Dialog HTML Content (Unescaped because ElementTree unescapes source.text)
    '''<h2>LocalTagger</h2>
<p><b>Professional Data Annotation Tool</b></p>
<p>LocalTagger is a high-performance, privacy-centric application designed for efficient local data annotation. It integrates advanced AI capabilities with a robust manual labeling interface.</p>

<h3>Key Features</h3>
<ul>
<li><b>Secure & Local:</b> Operates entirely offline to ensure maximum data privacy.</li>
<li><b>AI Assistance:</b> Integrated MobileSAM model for automated object segmentation.</li>
<li><b>Multi-Format Export:</b> Supports YOLO, COCO, and Pascal VOC standards with built-in data augmentation.</li>
</ul>

<h3>Usage Guide</h3>
<p>To start annotating, load a folder of images using the File menu. Select a class from the list or create a new one.</p>
<ul>
<li><b>Drawing:</b> Use the Toolbar or shortcuts to switch between Bounding Box and Polygon modes.</li>
<li><b>Editing:</b> Switch to Select Mode to adjust existing annotations. Double-click a label to modify its class.</li>
<li><b>AI Mode:</b> Enable AI to automatically segment and annotate objects with a single click.</li>
</ul>

<h3>Keyboard Shortcuts</h3>
<table width="100%" cellspacing="4">
<tr><td><b>W</b></td><td>Bounding Box Tool</td><td><b>E</b></td><td>Polygon Tool</td></tr>
<tr><td><b>Q</b></td><td>Select/Edit Tool</td><td><b>T</b></td><td>Toggle AI Mode</td></tr>
<tr><td><b>A / D</b></td><td>Previous / Next Image</td><td><b>Del</b></td><td>Delete Selected</td></tr>
<tr><td><b>Ctrl+S</b></td><td>Save Changes</td><td><b>Ctrl+E</b></td><td>Export Data</td></tr>
</table>

<p style="color: grey; font-size: 10px; margin-top: 15px;">© 2026 LocalTagger</p>
''': 
    '''<h2>LocalTagger</h2>
<p><b>Profesyonel Veri Etiketleme Aracı</b></p>
<p>LocalTagger, verimli yerel veri etiketleme için tasarlanmış, yüksek performanslı ve gizlilik odaklı bir uygulamadır. Gelişmiş yapay zeka yeteneklerini güçlü bir manuel etiketleme arayüzü ile birleştirir.</p>

<h3>Temel Özellikler</h3>
<ul>
<li><b>Güvenli ve Yerel:</b> Maksimum veri gizliliği sağlamak için tamamen çevrimdışı çalışır.</li>
<li><b>Yapay Zeka Desteği:</b> Otomatik nesne segmentasyonu için entegre MobileSAM modeli.</li>
<li><b>Çoklu Format Desteği:</b> Dahili veri artırma özellikleri ile YOLO, COCO ve Pascal VOC standartlarını destekler.</li>
</ul>

<h3>Kullanım Kılavuzu</h3>
<p>Etiketlemeye başlamak için Dosya menüsünden bir görsel klasörü yükleyin. Listeden bir sınıf seçin veya yeni bir sınıf oluşturun.</p>
<ul>
<li><b>Çizim:</b> Sınırlayıcı Kutu (BBox) ve Çokgen (Polygon) modları arasında geçiş yapmak için araç çubuğunu veya kısayolları kullanın.</li>
<li><b>Düzenleme:</b> Mevcut etiketleri ayarlamak için Seçim Moduna geçin. Sınıfını değiştirmek için etikete çift tıklayın.</li>
<li><b>AI Modu:</b> Nesneleri tek tıkla otomatik olarak segmentlere ayırmak ve etiketlemek için AI modunu etkinleştirin.</li>
</ul>

<h3>Klavye Kısayolları</h3>
<table width="100%" cellspacing="4">
<tr><td><b>W</b></td><td>Kutu (BBox) Aracı</td><td><b>E</b></td><td>Çokgen Aracı</td></tr>
<tr><td><b>Q</b></td><td>Seçim/Düzenleme Aracı</td><td><b>T</b></td><td>AI Modu Aç/Kapa</td></tr>
<tr><td><b>A / D</b></td><td>Önceki / Sonraki Görsel</td><td><b>Del</b></td><td>Seçiliyi Sil</td></tr>
<tr><td><b>Ctrl+S</b></td><td>Değişiklikleri Kaydet</td><td><b>Ctrl+E</b></td><td>Veri Dışa Aktar</td></tr>
</table>

<p style="color: grey; font-size: 10px; margin-top: 15px;">© 2026 LocalTagger</p>
''',

    # Delete confirmation multiline
    "Are you sure you want to delete {} annotations from this image?\n\nThis action cannot be undone!":
        "Bu görselden {} etiketi silmek istediğinize emin misiniz?\n\nBu işlem geri alınamaz!",

        
    "Blur: Adds Gaussian blur to the image.\n\nUnit: Kernel size (pixels)\n\nTeaches handling of out-of-focus or moving objects.":
        "Bulanıklık: Görüntüye Gaussian bulanıklık ekler.\n\nBirim: Kernel boyutu (piksel)\n\nOdak dışı veya hareketli nesnelerin işlenmesini öğretir.",
        
    "Noise: Adds random pixel noise to the image.\n\nUnit: Standard deviation (sigma)\nRandom values of ±sigma are added to pixel values.\n\nFor generalization with low quality or noisy camera sensors.":
        "Gürültü: Görüntüye rastgele piksel gürültüsü ekler.\n\nBirim: Standart sapma (sigma)\nPiksel değerlerine ±sigma rastgele değerler eklenir.\n\nDüşük kaliteli veya gürültülü kamera sensörleri için genelleme sağlar.",
        
    "Hue: Shifts colors in the color spectrum.\n\nAdapts to different lighting color temperatures.":
        "Renk Tonu: Renk spektrumunda renkleri kaydırır.\n\nFarklı aydınlatma renk sıcaklıklarına uyum sağlar.",
        
    "Grayscale: Converts the image to black and white.\n\n• Rate %: Percentage of images to convert to grayscale\n\nTeaches object recognition without color information.":
        "Gri Tonlama: Görüntüyü siyah-beyaza dönüştürür.\n\n• Oran %: Gri tonlamaya dönüştürülecek görüntü yüzdesi\n\nRenk bilgisi olmadan nesne tanımayı öğretir.",
        
    "Exposure (Gamma): Adjusts light exposure.\n\n• 100%: Original\n• <100%: Underexposed (darker)\n• >100%: Overexposed (brighter)\n\nUnlike brightness, preserves color tones.":
        "Pozlama (Gama): Işık pozlamasını ayarlar.\n\n• %100: Orijinal\n• <%100: Düşük pozlama (daha koyu)\n• >%100: Aşırı pozlama (daha parlak)\n\nParlaklığın aksine renk tonlarını korur.",
        
    "Cutout: Adds random black squares to the image.\n\nUnit: Percentage of image size\n• Size 10% = 64px square on 640px image\n\n• Count: Number of squares to add\n• Rate %: Application probability\n\nTeaches the model to work with missing information (occlusion robustness).\n\n⚠ WARNING: Some modern models like YOLOv8 may automatically apply\nsimilar techniques (e.g., erasing) during training.\nApplying this both here and during training (double application)\nmay negatively affect model performance.":
        "Cutout: Görüntüye rastgele siyah kareler ekler.\n\nBirim: Görüntü boyutunun yüzdesi\n• Boyut %10 = 640px görüntüde 64px kare\n\n• Adet: Eklenecek kare sayısı\n• Oran %: Uygulama olasılığı\n\nModele eksik bilgiyle çalışmayı öğretir (oklüzyon dayanıklılığı).\n\n⚠ UYARI: YOLOv8 gibi bazı modern modeller eğitim sırasında\nbenzer teknikleri (örn. silme) otomatik uygulayabilir.\nBunu hem burada hem de eğitim sırasında uygulamak (çift uygulama)\nmodel performansını olumsuz etkileyebilir.",
        
    "Motion Blur: Adds horizontal motion effect.\n\nUnit: Kernel size (pixels)\n\nTeaches detection of moving objects.":
        "Hareket Bulanıklığı: Yatay hareket efekti ekler.\n\nBirim: Kernel boyutu (piksel)\n\nHareketli nesnelerin algılanmasını öğretir.",
        
    "Shear: Tilts the image horizontally/vertically.\n\n• Horizontal: Horizontal tilt angle\n• Vertical: Vertical tilt angle\n\nProvides perspective variation,\nteaches generalization from different viewing angles.":
        "Kesme: Görüntüyü yatay/dikey olarak eğer.\n\n• Yatay: Yatay eğim açısı\n• Dikey: Dikey eğim açısı\n\nPerspektif çeşitliliği sağlar,\nfarklı görüş açılarından genelleme öğretir.",
}

def translate_ts_file(ts_path):
    """Parse and translate the .ts file preserving XML structure."""
    tree = ET.parse(ts_path)
    root = tree.getroot()
    root.set('language', 'tr_TR')
    
    translated_count = 0
    unfinished_count = 0
    
    for context in root.findall('context'):
        for message in context.findall('message'):
            source = message.find('source')
            translation = message.find('translation')
            
            if source is not None and translation is not None:
                source_text = source.text if source.text else ''
                source_normalized = source_text.replace('\r\n', '\n').replace('\r', '\n')
                
                # Check single-line dictionary
                if source_text in translations:
                    translation.text = translations[source_text]
                    if 'type' in translation.attrib:
                        del translation.attrib['type']
                    translated_count += 1
                # Check multiline translations
                elif source_normalized in multiline_translations:
                    translation.text = multiline_translations[source_normalized]
                    if 'type' in translation.attrib:
                        del translation.attrib['type']
                    translated_count += 1
                elif translation.attrib.get('type') == 'unfinished':
                    unfinished_count += 1
    
    tree.write(ts_path, encoding='utf-8', xml_declaration=True)
    
    with open(ts_path, 'r', encoding='utf-8') as f:
        content = f.read()
    content = content.replace("<?xml version='1.0' encoding='utf-8'?>", 
                              '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>')
    with open(ts_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Translation complete!")
    print(f"  Translated: {translated_count}")
    print(f"  Still unfinished: {unfinished_count}")

if __name__ == '__main__':
    translate_ts_file('tr.ts')
