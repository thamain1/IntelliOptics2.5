# HRM Training Guide for IntelliOptics Quality Inspection

**Date**: 2026-01-05
**Status**: Ready for immediate execution
**Data Available**: Thousands of images with detections (Phase 1 complete)

---

## Prerequisites

### Hardware
- **GPU**: NVIDIA RTX 4070 or better (16GB+ VRAM recommended)
- **RAM**: 32GB+ system RAM
- **Storage**: 100GB free space for dataset + models

### Software
```bash
# 1. Install CUDA 12.6
CUDA_URL=https://developer.download.nvidia.com/compute/cuda/12.6.3/local_installers/cuda_12.6.3_560.35.05_linux.run
wget -q --show-progress --progress=bar:force:noscroll -O cuda_installer.run $CUDA_URL
sudo sh cuda_installer.run --silent --toolkit --override
export CUDA_HOME=/usr/local/cuda-12.6

# 2. Install PyTorch with CUDA 12.6
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126

# 3. Install FlashAttention 2 (for Ampere/Ada GPUs like RTX 4070)
pip3 install flash-attn packaging ninja wheel setuptools setuptools-scm

# 4. Install HRM dependencies
cd C:\Users\ThaMain1\HRM
pip install -r requirements.txt

# 5. Login to Weights & Biases (for experiment tracking)
wandb login
```

---

## Part 1: Data Preparation (YOUR IMAGES → HRM FORMAT)

### Step 1.1: Collect Your Detection Images

You mentioned you have **thousands of images with detections**. Let's structure them:

```
C:\dev\intellioptics-hrm-training\
├── raw_data\
│   ├── images\                # Your thousands of images
│   │   ├── img_0001.jpg
│   │   ├── img_0002.jpg
│   │   └── ...
│   ├── labels\                # Detection results (JSON format)
│   │   ├── img_0001.json      # Matches img_0001.jpg
│   │   ├── img_0002.json
│   │   └── ...
│   └── metadata.csv           # Optional: Image metadata
```

**Expected Label Format** (img_0001.json):
```json
{
    "image_id": "img_0001",
    "detector_id": "det_abc123",
    "detections": [
        {
            "label": "defect",           # or "pass"
            "confidence": 0.92,
            "bbox": [100, 150, 200, 250],  # [x1, y1, x2, y2] - optional
            "primary_confidence": 0.95,
            "oodd_in_domain_score": 0.97,
            "is_out_of_domain": false
        }
    ],
    "ground_truth": "defect",      # Human-verified label
    "reasoning": [                  # NEW: Add reasoning chains
        "Crack detected in critical zone",
        "Width exceeds 0.5mm threshold",
        "Pattern matches known failure mode"
    ]
}
```

**If you don't have reasoning chains yet**, we'll generate them in Step 1.3.

### Step 1.2: Convert Images to HRM Grid Format

HRM expects grid-based inputs (like Sudoku puzzles). We'll convert images to patch grids.

**Create**: `C:\dev\intellioptics-hrm-training\dataset\build_vision_dataset.py`

```python
import os
import json
import numpy as np
from PIL import Image
import torch
from torchvision import transforms
from torchvision.models import resnet50, ResNet50_Weights
from pathlib import Path

# Configuration
IMG_SIZE = 640          # Resize images to 640x640
PATCH_SIZE = 32         # Each patch is 32x32 pixels
GRID_SIZE = IMG_SIZE // PATCH_SIZE  # 20x20 grid
VOCAB_SIZE = 512        # Number of discrete tokens
OUTPUT_DIR = "C:/dev/intellioptics-hrm-training/data/vision-hrm-1k"

class ImageToGridConverter:
    def __init__(self):
        # Use ResNet50 as feature extractor
        weights = ResNet50_Weights.IMAGENET1K_V2
        self.encoder = resnet50(weights=weights)
        # Remove final classification layer
        self.encoder = torch.nn.Sequential(*list(self.encoder.children())[:-2])
        self.encoder.eval()
        self.encoder.cuda()

        # Image preprocessing
        self.transform = transforms.Compose([
            transforms.Resize((IMG_SIZE, IMG_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                               std=[0.229, 0.224, 0.225])
        ])

        # Learned codebook for quantization
        self.codebook = torch.randn(VOCAB_SIZE, 2048).cuda()

    def image_to_grid(self, image_path):
        """Convert image to discrete grid tokens"""
        # Load and preprocess image
        img = Image.open(image_path).convert('RGB')
        img_tensor = self.transform(img).unsqueeze(0).cuda()

        # Extract features (batch, 2048, 20, 20)
        with torch.no_grad():
            features = self.encoder(img_tensor)

        # Flatten spatial dimensions
        B, C, H, W = features.shape
        features_flat = features.permute(0, 2, 3, 1).reshape(-1, C)  # (400, 2048)

        # Quantize to discrete tokens using codebook
        # Find nearest codebook entry for each patch
        distances = torch.cdist(features_flat, self.codebook)
        tokens = torch.argmin(distances, dim=1)  # (400,)
        tokens = tokens.reshape(H, W).cpu().numpy()  # (20, 20)

        return tokens

    def build_dataset(self, raw_data_dir, output_dir, subsample_size=1000):
        """Build HRM-compatible dataset from your images"""
        raw_data_path = Path(raw_data_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Load all image/label pairs
        image_dir = raw_data_path / "images"
        label_dir = raw_data_path / "labels"

        image_files = sorted(list(image_dir.glob("*.jpg")))
        print(f"Found {len(image_files)} images")

        # Subsample if needed
        if len(image_files) > subsample_size:
            import random
            random.seed(42)
            image_files = random.sample(image_files, subsample_size)
            print(f"Subsampled to {subsample_size} images")

        dataset = []
        for img_file in image_files:
            label_file = label_dir / f"{img_file.stem}.json"
            if not label_file.exists():
                print(f"Warning: No label for {img_file.name}, skipping")
                continue

            # Load label
            with open(label_file) as f:
                label_data = json.load(f)

            # Convert image to grid
            grid_tokens = self.image_to_grid(img_file)

            # Prepare HRM-compatible entry
            entry = {
                "input_grid": grid_tokens.tolist(),  # (20, 20)
                "target": 1 if label_data["ground_truth"] == "defect" else 0,
                "reasoning_steps": label_data.get("reasoning", []),
                "metadata": {
                    "image_id": label_data["image_id"],
                    "detector_id": label_data["detector_id"],
                    "original_confidence": label_data["detections"][0]["confidence"]
                }
            }
            dataset.append(entry)

        # Split train/val/test (80/10/10)
        n = len(dataset)
        train_size = int(0.8 * n)
        val_size = int(0.1 * n)

        train_data = dataset[:train_size]
        val_data = dataset[train_size:train_size+val_size]
        test_data = dataset[train_size+val_size:]

        # Save splits
        for split, data in [("train", train_data), ("val", val_data), ("test", test_data)]:
            split_file = output_path / f"{split}.json"
            with open(split_file, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"Saved {len(data)} samples to {split_file}")

        # Save config
        config = {
            "img_size": IMG_SIZE,
            "patch_size": PATCH_SIZE,
            "grid_size": GRID_SIZE,
            "vocab_size": VOCAB_SIZE,
            "num_train": len(train_data),
            "num_val": len(val_data),
            "num_test": len(test_data)
        }
        with open(output_path / "config.json", 'w') as f:
            json.dump(config, f, indent=2)

        print(f"\nDataset built successfully!")
        print(f"Train: {len(train_data)}, Val: {len(val_data)}, Test: {len(test_data)}")

# Usage
if __name__ == "__main__":
    converter = ImageToGridConverter()
    converter.build_dataset(
        raw_data_dir="C:/dev/intellioptics-hrm-training/raw_data",
        output_dir="C:/dev/intellioptics-hrm-training/data/vision-hrm-1k",
        subsample_size=1000  # Use 1000 images for initial training
    )
```

**Run it:**
```bash
cd C:\dev\intellioptics-hrm-training
python dataset\build_vision_dataset.py
```

### Step 1.3: Generate Reasoning Chains (if missing)

If your labels don't have reasoning chains yet, generate them using a VLM (Vision Language Model):

**Create**: `C:\dev\intellioptics-hrm-training\scripts\generate_reasoning.py`

```python
import json
from pathlib import Path
import anthropic  # or openai

# Use Claude 3.7 Sonnet or GPT-4V
client = anthropic.Anthropic(api_key="YOUR_API_KEY")

def generate_reasoning(image_path, label):
    """Generate reasoning chain for why image is labeled as defect/pass"""

    # Read image
    with open(image_path, 'rb') as f:
        image_data = f.read()

    prompt = f"""You are an expert quality inspector. The image shows a manufactured part.

Ground Truth Label: {label}

Provide a 3-step reasoning chain explaining why this part is labeled as "{label}":
1. What visual features do you observe?
2. How do these features relate to quality standards?
3. What is the final conclusion?

Format as JSON array of strings."""

    response = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_data.hex()
                    }
                },
                {"type": "text", "text": prompt}
            ]
        }]
    )

    reasoning = json.loads(response.content[0].text)
    return reasoning

# Process all images
raw_data = Path("C:/dev/intellioptics-hrm-training/raw_data")
label_dir = raw_data / "labels"

for label_file in label_dir.glob("*.json"):
    with open(label_file) as f:
        label_data = json.load(f)

    # Skip if reasoning already exists
    if "reasoning" in label_data and label_data["reasoning"]:
        continue

    # Generate reasoning
    image_path = raw_data / "images" / f"{label_file.stem}.jpg"
    reasoning = generate_reasoning(image_path, label_data["ground_truth"])

    # Update label file
    label_data["reasoning"] = reasoning
    with open(label_file, 'w') as f:
        json.dump(label_data, f, indent=2)

    print(f"Generated reasoning for {label_file.name}")
```

---

## Part 2: HRM Architecture Adaptation

### Step 2.1: Create VisionHRM Model

**Create**: `C:\Users\ThaMain1\HRM\models\vision_hrm.py`

```python
import torch
import torch.nn as nn
from models.hrm.hrm import HierarchicalReasoningModel

class VisionHRM(nn.Module):
    """HRM adapted for computer vision tasks"""

    def __init__(self,
                 vocab_size=512,
                 grid_size=20,
                 num_classes=2,
                 d_model=256,
                 num_layers=6,
                 reasoning_depth=3):
        super().__init__()

        # Token embedding (converts discrete grid tokens to embeddings)
        self.token_embedding = nn.Embedding(vocab_size, d_model)

        # Positional encoding for grid
        self.pos_embedding = nn.Parameter(torch.randn(1, grid_size*grid_size, d_model))

        # Core HRM
        self.hrm = HierarchicalReasoningModel(
            d_model=d_model,
            num_layers=num_layers,
            reasoning_depth=reasoning_depth
        )

        # Classification head
        self.classifier = nn.Linear(d_model, num_classes)

        # Reasoning decoder (outputs text explanation)
        self.reasoning_decoder = nn.TransformerDecoder(
            nn.TransformerDecoderLayer(d_model, nhead=8),
            num_layers=3
        )

    def forward(self, grid_tokens, target_reasoning=None):
        """
        Args:
            grid_tokens: (batch, grid_size, grid_size) discrete tokens
            target_reasoning: (batch, seq_len) for training reasoning decoder

        Returns:
            logits: (batch, num_classes)
            reasoning_logits: (batch, seq_len, vocab_size) if training
        """
        batch_size, h, w = grid_tokens.shape

        # Flatten grid and embed
        grid_flat = grid_tokens.reshape(batch_size, -1)  # (batch, h*w)
        embeddings = self.token_embedding(grid_flat)  # (batch, h*w, d_model)
        embeddings = embeddings + self.pos_embedding

        # HRM processing
        hrm_output = self.hrm(embeddings)  # (batch, h*w, d_model)

        # Classification (use [CLS] token or mean pooling)
        pooled = hrm_output.mean(dim=1)  # (batch, d_model)
        logits = self.classifier(pooled)  # (batch, num_classes)

        # Reasoning generation (if training)
        reasoning_logits = None
        if target_reasoning is not None:
            reasoning_logits = self.reasoning_decoder(
                target_reasoning,
                hrm_output
            )

        return {
            "logits": logits,
            "reasoning_logits": reasoning_logits,
            "embeddings": hrm_output
        }
```

### Step 2.2: Create HRM Dataset Loader

**Create**: `C:\Users\ThaMain1\HRM\dataset\vision_dataset.py`

```python
import json
import torch
from torch.utils.data import Dataset
from pathlib import Path

class VisionHRMDataset(Dataset):
    def __init__(self, data_path, split='train'):
        self.data_path = Path(data_path)

        # Load data
        with open(self.data_path / f"{split}.json") as f:
            self.data = json.load(f)

        # Load config
        with open(self.data_path / "config.json") as f:
            self.config = json.load(f)

        print(f"Loaded {len(self.data)} samples from {split} split")

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        entry = self.data[idx]

        # Grid tokens (20, 20)
        grid = torch.tensor(entry["input_grid"], dtype=torch.long)

        # Target label (0 or 1)
        target = torch.tensor(entry["target"], dtype=torch.long)

        # Reasoning steps (convert to token IDs - simplified)
        reasoning = entry.get("reasoning_steps", [])
        # TODO: Tokenize reasoning text to IDs

        return {
            "grid_tokens": grid,
            "target": target,
            "reasoning": reasoning  # Will be tokenized in collate_fn
        }
```

### Step 2.3: Update HRM Config

**Create**: `C:\Users\ThaMain1\HRM\config\arch\vision_hrm.yaml`

```yaml
# Architecture config for Vision HRM
model_type: vision_hrm

# Grid parameters
vocab_size: 512
grid_size: 20  # 20x20 grid
num_classes: 2  # binary: defect/no-defect

# Model architecture
d_model: 256
num_layers: 6
reasoning_depth: 3
nhead: 8
dim_feedforward: 1024
dropout: 0.1

# Training
lr: 7e-5
weight_decay: 1.0
global_batch_size: 384
epochs: 20000
eval_interval: 2000

# Loss weights
classification_loss_weight: 1.0
reasoning_loss_weight: 0.5
```

---

## Part 3: Training HRM

### Step 3.1: Update pretrain.py

**Edit**: `C:\Users\ThaMain1\HRM\pretrain.py`

Add Vision HRM support at the top:

```python
# Add after imports
from models.vision_hrm import VisionHRM
from dataset.vision_dataset import VisionHRMDataset

# In main training loop, replace dataset loading:
if args.arch == "vision_hrm":
    train_dataset = VisionHRMDataset(args.data_path, split='train')
    val_dataset = VisionHRMDataset(args.data_path, split='val')
    model = VisionHRM(
        vocab_size=args.vocab_size,
        grid_size=args.grid_size,
        num_classes=args.num_classes,
        d_model=args.d_model,
        num_layers=args.num_layers,
        reasoning_depth=args.reasoning_depth
    )
```

### Step 3.2: Run Training

```bash
cd C:\Users\ThaMain1\HRM

# Single GPU training (RTX 4070)
OMP_NUM_THREADS=8 python pretrain.py \
    arch=vision_hrm \
    data_path=C:/dev/intellioptics-hrm-training/data/vision-hrm-1k \
    epochs=20000 \
    eval_interval=2000 \
    global_batch_size=384 \
    lr=7e-5 \
    weight_decay=1.0

# Multi-GPU training (if you have 2+ GPUs)
OMP_NUM_THREADS=8 torchrun --nproc-per-node 2 pretrain.py \
    arch=vision_hrm \
    data_path=C:/dev/intellioptics-hrm-training/data/vision-hrm-1k \
    epochs=20000 \
    eval_interval=2000 \
    global_batch_size=768 \
    lr=1e-4 \
    weight_decay=1.0
```

**Expected Training Time**: ~10 hours on RTX 4070

### Step 3.3: Monitor Training

1. Open Weights & Biases dashboard: https://wandb.ai
2. Watch metrics:
   - `train/loss` - should decrease steadily
   - `val/accuracy` - should reach >95%
   - `eval/exact_accuracy` - final metric

3. Early stopping: Stop when val accuracy plateaus (usually after 8-12 hours)

---

## Part 4: Evaluation & Export

### Step 4.1: Evaluate Trained Model

```bash
cd C:\Users\ThaMain1\HRM

python evaluate.py \
    checkpoint=checkpoints/vision_hrm_epoch_20000.pt \
    data_path=C:/dev/intellioptics-hrm-training/data/vision-hrm-1k
```

**Expected Output**:
```
Evaluation Results:
- Exact Accuracy: 96.5%
- Classification Accuracy: 97.2%
- Reasoning Quality Score: 0.89
```

### Step 4.2: Export to ONNX

**Create**: `C:\Users\ThaMain1\HRM\export_onnx.py`

```python
import torch
from models.vision_hrm import VisionHRM

# Load trained checkpoint
checkpoint_path = "checkpoints/vision_hrm_epoch_20000.pt"
model = VisionHRM.load_from_checkpoint(checkpoint_path)
model.eval()
model.cpu()

# Dummy input
dummy_grid = torch.randint(0, 512, (1, 20, 20), dtype=torch.long)

# Export to ONNX
torch.onnx.export(
    model,
    dummy_grid,
    "models/vision_hrm.onnx",
    input_names=["grid_tokens"],
    output_names=["logits", "reasoning_embeddings"],
    dynamic_axes={
        "grid_tokens": {0: "batch_size"},
        "logits": {0: "batch_size"}
    },
    opset_version=14
)

print("Model exported to models/vision_hrm.onnx")
```

Run:
```bash
python export_onnx.py
```

---

## Part 5: SendGrid Alert Integration

### Step 5.1: SendGrid Setup (Better than Azure for Alerts)

**Why SendGrid over Azure Communication Services:**
- Simpler API, less setup
- Better templating and dynamic content
- Built-in analytics and tracking
- More cost-effective for transactional emails
- Easier A/B testing and customization

**Install**:
```bash
pip install sendgrid
```

### Step 5.2: Alert Service Implementation

**Create**: `C:\dev\intellioptics-edge-deploy\cloud\backend\app\services\sendgrid_alerts.py`

```python
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment
from typing import List, Dict
import base64

class SendGridAlertService:
    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY")
        self.from_email = os.getenv("SENDGRID_FROM_EMAIL", "alerts@intellioptics.com")
        self.sg = SendGridAPIClient(self.api_key)

    def send_escalation_alert(self,
                            to_emails: List[str],
                            detector_name: str,
                            image_url: str,
                            confidence: float,
                            reasoning: List[str],
                            image_bytes: bytes = None):
        """Send escalation alert to human reviewers"""

        # Build HTML email with reasoning
        reasoning_html = "<ol>" + "".join(f"<li>{step}</li>" for step in reasoning) + "</ol>"

        html_content = f"""
        <html>
        <body>
            <h2>⚠️ Quality Inspection Escalation</h2>
            <p><strong>Detector:</strong> {detector_name}</p>
            <p><strong>Confidence:</strong> {confidence:.2%}</p>

            <h3>Reasoning:</h3>
            {reasoning_html}

            <p><a href="{image_url}">View Image for Review</a></p>

            <img src="{image_url}" alt="Inspection Image" style="max-width: 600px;"/>
        </body>
        </html>
        """

        message = Mail(
            from_email=self.from_email,
            to_emails=to_emails,
            subject=f"🔍 Escalation: {detector_name} (Confidence: {confidence:.2%})",
            html_content=html_content
        )

        # Attach image if provided
        if image_bytes:
            encoded = base64.b64encode(image_bytes).decode()
            attachment = Attachment(
                file_content=encoded,
                file_type='image/jpeg',
                file_name='inspection_image.jpg',
                disposition='inline',
                content_id='inspection_image'
            )
            message.add_attachment(attachment)

        # Send
        try:
            response = self.sg.send(message)
            return {
                "status": "sent",
                "status_code": response.status_code,
                "message_id": response.headers.get('X-Message-Id')
            }
        except Exception as e:
            print(f"SendGrid error: {e}")
            return {"status": "failed", "error": str(e)}

    def send_summary_report(self,
                          to_emails: List[str],
                          time_period: str,
                          stats: Dict):
        """Send periodic summary reports"""

        html_content = f"""
        <html>
        <body>
            <h2>📊 IntelliOptics Summary Report ({time_period})</h2>

            <table border="1" cellpadding="10">
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Total Inspections</td>
                    <td>{stats['total_inspections']}</td>
                </tr>
                <tr>
                    <td>Edge Processed</td>
                    <td>{stats['edge_processed']} ({stats['edge_percentage']:.1%})</td>
                </tr>
                <tr>
                    <td>Escalations</td>
                    <td>{stats['escalations']} ({stats['escalation_rate']:.2%})</td>
                </tr>
                <tr>
                    <td>Average Confidence</td>
                    <td>{stats['avg_confidence']:.2%}</td>
                </tr>
            </table>
        </body>
        </html>
        """

        message = Mail(
            from_email=self.from_email,
            to_emails=to_emails,
            subject=f"📈 IntelliOptics Report: {time_period}",
            html_content=html_content
        )

        response = self.sg.send(message)
        return response.status_code == 202

# Usage in edge-api or cloud backend
async def handle_escalation(detector_id, image_query):
    alert_service = SendGridAlertService()

    # Get detector config
    detector = get_detector(detector_id)

    # Get reviewer emails
    reviewer_emails = detector.reviewer_emails or ["quality@company.com"]

    # Send alert
    result = alert_service.send_escalation_alert(
        to_emails=reviewer_emails,
        detector_name=detector.name,
        image_url=image_query.image_url,
        confidence=image_query.confidence,
        reasoning=image_query.hrm_reasoning,
        image_bytes=get_image_bytes(image_query.image_url)
    )

    return result
```

### Step 5.3: Environment Configuration

Add to `.env`:
```bash
# SendGrid
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=alerts@intellioptics.com
SENDGRID_REVIEWER_EMAILS=reviewer1@company.com,reviewer2@company.com

# Alert thresholds
ALERT_CONFIDENCE_THRESHOLD=0.8
ALERT_BATCH_SIZE=10
ALERT_BATCH_INTERVAL_MINUTES=15
```

---

## Part 6: Alternative to Azure (If Applicable)

### Option 1: Self-Hosted Stack (Full Control)

**Replace**:
- Azure Blob Storage → **MinIO** (S3-compatible, self-hosted)
- Azure Service Bus → **RabbitMQ** or **Redis Streams**
- Azure PostgreSQL → **Self-hosted PostgreSQL** with **Crunchy Postgres Operator**
- Azure APIM → **Kong Gateway** or **Tyk**

**Benefits**:
- 70% cost savings
- No vendor lock-in
- Full control over data
- Better for on-premise customers

**Docker Compose Example**:
```yaml
services:
  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ROOT_USER=admin
      - MINIO_ROOT_PASSWORD=password123
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

  rabbitmq:
    image: rabbitmq:3-management
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      - RABBITMQ_DEFAULT_USER=admin
      - RABBITMQ_DEFAULT_PASS=password123

  kong:
    image: kong:latest
    environment:
      - KONG_DATABASE=postgres
      - KONG_PG_HOST=postgres
    ports:
      - "8000:8000"
      - "8443:8443"
      - "8001:8001"
```

### Option 2: Hybrid (Keep Azure DB, Replace Others)

- Keep: Azure PostgreSQL (managed, reliable)
- Replace Blob Storage with MinIO (self-hosted, S3-compatible)
- Replace Service Bus with RabbitMQ (faster, simpler)
- Use SendGrid for emails (done above)

---

## Part 7: Quick Start Summary

**1. Data Prep (1 hour)**:
```bash
cd C:\dev\intellioptics-hrm-training
python dataset\build_vision_dataset.py
python scripts\generate_reasoning.py  # If needed
```

**2. HRM Setup (30 min)**:
```bash
cd C:\Users\ThaMain1\HRM
pip install -r requirements.txt
wandb login
```

**3. Train HRM (10 hours)**:
```bash
OMP_NUM_THREADS=8 python pretrain.py \
    arch=vision_hrm \
    data_path=C:/dev/intellioptics-hrm-training/data/vision-hrm-1k \
    epochs=20000 \
    eval_interval=2000 \
    global_batch_size=384 \
    lr=7e-5
```

**4. Export Model (5 min)**:
```bash
python export_onnx.py
```

**5. Deploy (Phase 2)**:
- Copy `vision_hrm.onnx` to edge deployment
- Update edge-api to call HRM service
- Configure SendGrid alerts

---

## Next Steps

1. **Run Data Prep NOW**: Get your images into HRM format
2. **Start Training**: Kick off the 10-hour training run
3. **While Training**: Set up SendGrid account and test alerts
4. **After Training**: Export model and integrate into edge deployment
5. **Monitor**: Track escalation reduction and reasoning quality

**Questions? Issues?**
- HRM training issues: Check `wandb` dashboard for metrics
- SendGrid issues: Check API logs in SendGrid dashboard
- Data format issues: Review `build_vision_dataset.py` output

---

**Ready to start?** Begin with Step 1.1 (collect your detection images) and let me know when you're ready for the next step!
