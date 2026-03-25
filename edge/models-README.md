# IntelliOptics 2.0 - Model Setup Guide

## Model Directory Structure

```
/opt/intellioptics/models/
├── det_test_001/           # Detector ID
│   ├── primary/            # Main detection model (YOLO)
│   │   └── 1/              # Version number
│   │       └── model.buf   # ONNX model file
│   └── oodd/               # Out-of-Domain Detection model
│       └── 1/
│           └── model.buf   # ONNX model file
└── det_another/...         # Additional detectors
```

## Current Status

**⚠️ PLACEHOLDER MODELS INSTALLED**

Currently, placeholder text files are in place for testing the API layer. **Inference will fail** until real ONNX models are added.

## Option 1: Download YOLOv8 Models (Recommended)

### Using the provided script:

```bash
cd "/c/Dev/IntelliOptics 2.0/edge/scripts"

# Install dependencies
pip install ultralytics torch onnx

# Download YOLOv8n (nano - smallest, fastest)
python download-models.py --detector-id det_test_001 --model-size n

# Or download larger models:
# python download-models.py --detector-id det_test_001 --model-size s  # Small
# python download-models.py --detector-id det_test_001 --model-size m  # Medium
```

### Model Sizes:
- **YOLOv8n** (nano): ~6MB, fastest, good for real-time edge inference
- **YOLOv8s** (small): ~22MB, balanced speed/accuracy
- **YOLOv8m** (medium): ~52MB, better accuracy
- **YOLOv8l** (large): ~87MB, high accuracy
- **YOLOv8x** (xlarge): ~131MB, best accuracy

## Option 2: Use Your Own ONNX Models

If you have trained custom YOLO or other ONNX models:

```bash
# Copy your models
cp /path/to/your-primary-model.onnx /opt/intellioptics/models/det_test_001/primary/1/model.buf
cp /path/to/your-oodd-model.onnx /opt/intellioptics/models/det_test_001/oodd/1/model.buf
```

**Model Requirements:**
- Format: ONNX (.onnx)
- Input: `[batch, 3, 640, 640]` - RGB image, 640x640 pixels
- Output: YOLO format detection boxes

## Option 3: Export from PyTorch

If you have PyTorch YOLO models:

```python
from ultralytics import YOLO

# Load your trained model
model = YOLO('path/to/your-model.pt')

# Export to ONNX
model.export(format='onnx', imgsz=640)

# This creates a .onnx file - copy it to model.buf
```

## About OODD Models

**OODD (Out-of-Domain Detection)** acts as a "gatekeeper" to detect when input images are significantly different from training data.

### For Testing:
- You can use the **same model** for both Primary and OODD (the script does this)
- This allows the system to run, but won't provide true OOD detection

### For Production:
- Train a separate OODD model using an autoencoder or anomaly detection approach
- The OODD model should output an "in-domain score" (0.0 to 1.0)
- Images with low in-domain scores are automatically escalated for human review

## Verifying Model Installation

After adding models, verify they load correctly:

```bash
# Check files exist
ls -lh /opt/intellioptics/models/det_test_001/*/1/model.buf

# Start inference service
cd "/c/Dev/IntelliOptics 2.0/edge"
docker-compose up inference

# Check logs for "Loaded model" messages
docker-compose logs inference | grep "Loaded model"
```

## Testing Inference

Once real models are installed:

```bash
# Start all edge services
docker-compose up -d

# Submit a test image
curl -X POST "http://localhost:30101/v1/image-queries?detector_id=det_test_001" \
  -F "image=@/path/to/test-image.jpg"
```

**Expected response:**
```json
{
  "query_id": "qry_abc123",
  "label": 0,
  "confidence": 0.92,
  "raw_primary_confidence": 0.95,
  "oodd_in_domain_score": 0.97,
  "is_out_of_domain": false,
  "result": "pass"
}
```

## Troubleshooting

### "Failed to load model" error
- Ensure model.buf files are valid ONNX format
- Check file permissions: `chmod 644 /opt/intellioptics/models/*/1/model.buf`
- Verify ONNX Runtime is installed in inference container

### "Cannot parse container/blob from URL" error
- This error is from the cloud worker, not edge inference
- Edge inference loads models from local filesystem, not URLs

### Inference returns errors on every image
- Likely using placeholder text files instead of real ONNX models
- Follow Option 1 or 2 above to install real models

## Next Steps

After installing models:

1. Configure detector in `edge/config/edge-config.yaml`
2. Deploy edge services: `docker-compose up -d`
3. Test with real images
4. For production, train a proper OODD model
5. Set confidence thresholds based on accuracy requirements

## Resources

- [YOLOv8 Documentation](https://docs.ultralytics.com/)
- [ONNX Runtime](https://onnxruntime.ai/)
- [Model Export Guide](https://docs.ultralytics.com/modes/export/)
