# LocalTagger 🏷️

**AI-Powered Local Data Annotation Tool** - Efficient, privacy-focused, offline data annotation tool featuring MobileSAM integration for automated segmentation.

![LocalTagger](src/resources/icon/LocalTagger.ico)

## ✨ Features

### 🤖 AI-Assisted Labeling (MobileSAM)
- **Click → Auto Label**: Click on an object, AI automatically generates BBox or Polygon.
- Runs locally in background, no UI freezing.
- Toggle AI with `T` key.

### 📝 Manual Annotation
- ⬜ Bounding Box drawing
- ◇ Polygon drawing
- Editable vertices and drag-to-move support.

### 📦 Export Formats
- **YOLO**: v5-v11 (txt)
- **COCO**: JSON format
- **Pascal VOC**: XML format
- **Custom**: Custom TXT/JSON templates

### 🔧 Data Management
- **Augmentation**: Brightness, contrast, rotation, flip, shear, cutout, motion blur.
- **Dataset Split**: Train/Val/Test splitting.
- **Resize**: Integrated resizing options.

## 🚀 Installation

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python src/main.py
```

## ⌨️ Shortcuts

| Key | Function |
|-----|----------|
| `T` | Toggle AI (MobileSAM) |
| `W` | BBox visual tool |
| `E` | Polygon visual tool |
| `Q` | Select/Edit mode |
| `A` / `D` | Previous/Next image |
| `Ctrl+S` | Save annotations |
| `Ctrl+E` | Export data |
| `Del` | Delete selected annotation |
| `ESC` | Cancel drawing |

## 📋 Requirements

- Python 3.10+
- Windows / Linux / macOS
- MobileSAM ONNX models (placed in `src/resources/models/`)

## 📄 License

MIT License
