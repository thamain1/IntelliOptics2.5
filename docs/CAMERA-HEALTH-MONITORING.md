# Camera Health Monitoring

IntelliOptics 2.0 includes comprehensive camera health monitoring capabilities to ensure image quality and detect physical tampering with camera systems.

## Overview

The camera health monitoring system provides:

1. **Image Quality Assessment**
   - Blur detection
   - Brightness/exposure validation
   - Contrast analysis
   - Overexposure/underexposure detection

2. **Tampering Detection**
   - Physical obstruction detection
   - Camera movement detection
   - Focus change detection
   - Significant scene change detection

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    RTSP Stream Ingestion                    │
│                                                             │
│  1. Capture frame from camera                              │
│  2. Assess frame health (if enabled)                       │
│     ├─ Quality Metrics                                     │
│     │   ├─ Blur Score (Laplacian variance)                │
│     │   ├─ Brightness (mean pixel value)                  │
│     │   ├─ Contrast (std dev)                             │
│     │   └─ Exposure (over/under exposed pixels)           │
│     └─ Tampering Metrics (if check_tampering=true)        │
│         ├─ Obstruction (dark pixel ratio)                 │
│         ├─ Movement (feature matching)                    │
│         ├─ Focus Change (blur score delta)                │
│         └─ Frame Difference (vs. reference)               │
│  3. Log health status (if log_health_status=true)          │
│  4. Skip if CRITICAL (if skip_unhealthy_frames=true)       │
│  5. Submit frame for inference                             │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

Camera health monitoring is configured per RTSP stream in `edge-config.yaml`:

```yaml
streams:
  camera_line_1:
    name: "Production Line 1 - Quality Station"
    detector_id: det_quality_check_001
    url: "rtsp://192.168.1.100:554/stream1"

    # Camera health monitoring configuration
    camera_health:
      enabled: true  # Enable health monitoring
      check_tampering: true  # Enable tampering detection
      log_health_status: true  # Log health metrics
      skip_unhealthy_frames: true  # Skip CRITICAL frames
      health_check_interval_seconds: 0.0  # Check frequency (0.0 = every frame)

      # Quality thresholds
      blur_threshold: 100.0  # Laplacian variance < 100 = blurry
      brightness_low: 40.0  # Mean brightness < 40 = too dark
      brightness_high: 220.0  # Mean brightness > 220 = too bright
      contrast_low: 30.0  # Std dev < 30 = low contrast

      # Tampering thresholds
      obstruction_threshold: 0.3  # >30% dark pixels = obstructed
      movement_threshold: 50.0  # Feature distance > 50 = moved
```

### Health Check Frequency

The `health_check_interval_seconds` parameter controls how often health assessments are performed:

**Options**:
- **`0.0`** (default): Check **every frame** - No caching, maximum accuracy
- **`> 0.0`**: Check **periodically** - Caches result between checks, reduces CPU overhead

**How it works**:
1. Health check runs immediately on first frame
2. Subsequent frames use **cached result** until interval elapses
3. When interval expires, new health check runs and cache updates
4. Cached results are used for frame filtering decisions

**Example**: Sampling at 2s intervals with 10s health check interval
```
Time    Frame    Health Check?    Action
0s      Frame 1  ✅ CHECK         Assess health, cache result
2s      Frame 2  ❌ CACHED        Use cached result
4s      Frame 3  ❌ CACHED        Use cached result
6s      Frame 4  ❌ CACHED        Use cached result
8s      Frame 5  ❌ CACHED        Use cached result
10s     Frame 6  ✅ CHECK         Assess health, update cache
12s     Frame 7  ❌ CACHED        Use cached result
...
```

**CPU Savings**: With 10s interval and 2s sampling, you reduce health checks by ~80%

### When to Use Different Intervals

| Interval | Use Case | CPU Overhead | Detection Latency |
|----------|----------|--------------|-------------------|
| **0s** | Critical inspections, quality assurance, first-time setup | High (~35ms/frame) | Immediate |
| **5s** | Security cameras, tampering detection | Medium | 5s max |
| **10s** | Stable environments, periodic diagnostics | Low | 10s max |
| **30s** | Background monitoring, long-term health tracking | Very low | 30s max |
| **60s** | Minimal monitoring, camera uptime checks | Minimal | 60s max |

**Recommendations**:

**Critical Inspection (Quality Assurance)**:
```yaml
health_check_interval_seconds: 0.0  # Check every frame
skip_unhealthy_frames: true  # Skip bad frames
```
- Use when every frame must be perfect
- Manufacturing quality checks
- High-value inspections

**Security Camera (Tampering Detection)**:
```yaml
health_check_interval_seconds: 5.0  # Check every 5 seconds
skip_unhealthy_frames: false  # Don't skip, log tampering
check_tampering: true
```
- Detect tampering quickly (within 5s)
- Log security events without dropping frames
- Balance between detection speed and CPU usage

**Stable Environment (Diagnostics)**:
```yaml
health_check_interval_seconds: 10.0  # Check every 10 seconds
skip_unhealthy_frames: true
```
- Camera is in controlled environment
- Lighting is stable
- Mainly checking for gradual degradation
- 80% CPU savings vs. every-frame checking

**Background Monitoring**:
```yaml
health_check_interval_seconds: 30.0  # Check every 30 seconds
log_health_status: true
skip_unhealthy_frames: false
```
- Long-term health trending
- Alert on persistent issues
- Minimal performance impact

## Quality Metrics

### 1. Blur Detection

**Method**: Laplacian variance

**How it works**:
- Computes the variance of the Laplacian operator applied to the grayscale image
- Higher variance = sharper image
- Lower variance = blurrier image

**Threshold**: `blur_threshold` (default: 100.0)
- Below threshold → Image is blurry (quality issue)
- Above threshold → Image is sharp (OK)

**Typical values**:
- Sharp image: 200-1000+
- Slightly blurry: 50-200
- Very blurry: <50

**Tuning tip**: Capture reference images from your camera and measure their blur scores:
```python
import cv2
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
print(f"Blur score: {blur_score}")
```

### 2. Brightness Analysis

**Method**: Mean pixel value (0-255)

**Thresholds**:
- `brightness_low` (default: 40.0) - Too dark below this
- `brightness_high` (default: 220.0) - Too bright above this

**Typical values**:
- Well-lit scene: 100-180
- Underexposed: <60
- Overexposed: >200

**Tuning tip**: Measure brightness in your typical lighting conditions:
```python
brightness = gray.mean()
print(f"Brightness: {brightness}")
```

### 3. Contrast Analysis

**Method**: Standard deviation of pixel values

**Threshold**: `contrast_low` (default: 30.0)
- Below threshold → Low contrast (flat image)
- Above threshold → Good contrast

**Typical values**:
- High contrast: 50-100+
- Medium contrast: 30-50
- Low contrast: <30

### 4. Exposure Detection

**Overexposure**: >10% of pixels above `overexposure_threshold` (default: 250)
**Underexposure**: >30% of pixels below `underexposure_threshold` (default: 20)

## Tampering Detection

### 1. Obstruction Detection

**Method**: Dark pixel ratio

**How it works**:
- Counts pixels with brightness < 30 (very dark)
- Calculates ratio: dark_pixels / total_pixels
- If ratio > `obstruction_threshold`, frame is obstructed

**Use case**: Detects when camera lens is covered or blocked

**Threshold**: `obstruction_threshold` (default: 0.3 = 30%)

**Examples**:
- Clean lens: ~0.05-0.15 (depending on scene)
- Partial obstruction: 0.3-0.6
- Fully covered: >0.8

### 2. Camera Movement Detection

**Method**: ORB feature matching between current and reference frame

**How it works**:
1. Extract ORB keypoints from reference frame (first frame)
2. Extract ORB keypoints from current frame
3. Match features using Brute Force matcher
4. Calculate average matching distance
5. If distance > `movement_threshold`, camera has moved

**Use case**: Detects if camera is physically moved or knocked

**Threshold**: `movement_threshold` (default: 50.0)

**Examples**:
- Stable camera: 5-20
- Slight vibration: 20-40
- Camera moved: >50

### 3. Focus Change Detection

**Method**: Blur score delta from reference

**How it works**:
- Compare current blur score to reference blur score
- Calculate ratio: |current - reference| / reference
- If ratio > `focus_change_threshold` (hardcoded: 0.3), focus changed

**Use case**: Detects if camera is refocused or lens tampered with

**Examples**:
- Same focus: <0.1
- Slight change: 0.1-0.3
- Focus changed: >0.3

### 4. Significant Scene Change

**Method**: Absolute frame difference

**How it works**:
- Calculate pixel-wise absolute difference from reference
- Normalize to 0-1 range
- If difference > `frame_diff_threshold` (hardcoded: 0.4), significant change

**Use case**: Detects if camera view is obstructed or scene drastically changed

## Health Status and Scoring

Each frame receives a health assessment with:

### Health Status

- **HEALTHY** (score ≥ 80): Frame is good quality
- **WARNING** (score 50-79): Minor issues detected
- **CRITICAL** (score < 50): Severe issues, frame should be skipped
- **UNKNOWN**: OpenCV not available

### Scoring System

**Starting score**: 100

**Deductions for quality issues**:
- Blur: -20
- Low brightness: -15
- High brightness: -15
- Low contrast: -10
- Overexposure: -10
- Underexposure: -10

**Deductions for tampering issues** (more severe):
- Obstruction: -50
- Camera moved: -30
- Focus changed: -20
- Significant change: -15

**Special rule**: Obstruction always results in CRITICAL status

## Logging

When `log_health_status: true`, health assessments are logged:

**HEALTHY frames** (DEBUG level):
```
Camera health for stream 'camera_line_1': status=healthy, score=95.0, blur=345.2, brightness=128.3, contrast=52.1
```

**WARNING frames** (INFO level):
```
Camera health for stream 'camera_line_1': status=warning, score=65.0, blur=78.4, brightness=45.2, contrast=28.5, quality_issues=['blur', 'low_contrast']
```

**CRITICAL frames** (WARNING level):
```
Camera health for stream 'camera_line_1': status=critical, score=25.0, blur=35.1, brightness=8.2, contrast=15.3, quality_issues=['blur', 'low_brightness', 'low_contrast', 'underexposure'], tampering_issues=['obstruction']
```

## Skipping Unhealthy Frames

When `skip_unhealthy_frames: true`:
- Frames with **CRITICAL** status are not submitted for inference
- Reduces false detections from poor quality images
- Saves inference compute resources
- Logged as: `Skipping unhealthy frame from stream 'camera_line_1'`

**Recommendation**: Enable this for production to avoid wasting inference on bad frames.

## Reference Frame Management

The first frame from each stream is used as the **reference frame** for tampering detection.

**To reset reference frame** (e.g., after intentional camera movement):
- Restart the edge-api service
- Or implement a reset endpoint (future enhancement)

## Tuning Guidelines

### 1. Capture Baseline Metrics

Run camera with `log_health_status: true` and `skip_unhealthy_frames: false` for 1 hour:
```bash
docker-compose -f docker-compose.yml logs edge-api | grep "Camera health"
```

Analyze logs to find typical values for:
- Blur score
- Brightness
- Contrast

### 2. Set Thresholds

Set thresholds **below** the minimum acceptable values:
- `blur_threshold`: Set to 70% of typical blur score
- `brightness_low`: Set to minimum acceptable brightness - 10
- `brightness_high`: Set to maximum acceptable brightness + 10
- `contrast_low`: Set to 70% of typical contrast

### 3. Test Tampering Detection

**Obstruction test**: Cover lens partially → Should detect obstruction
**Movement test**: Nudge camera → Should detect movement
**Focus test**: Adjust lens focus → Should detect focus change

### 4. Enable Frame Skipping

Once thresholds are tuned, enable:
```yaml
skip_unhealthy_frames: true
```

## Performance Impact

### CPU Overhead (per health check)

**Quality assessment only**:
- Blur detection: ~3-5ms
- Brightness/contrast: ~1-2ms
- Exposure analysis: ~1-2ms
- **Total**: ~5-10ms

**Quality + Tampering detection**:
- Quality checks: ~5-10ms
- ORB feature extraction: ~10-15ms
- Feature matching: ~5-10ms
- **Total**: ~20-35ms

### Impact on Different Configurations

| Configuration | Sampling Rate | Check Interval | Checks/Min | CPU Time/Min |
|---------------|---------------|----------------|------------|--------------|
| **Every frame** | 1 FPS | 0s | 60 | 2.1s (3.5%) |
| **Every frame** | 0.5 FPS (2s) | 0s | 30 | 1.05s (1.75%) |
| **Periodic** | 0.5 FPS (2s) | 10s | 6 | 0.21s (0.35%) |
| **Periodic** | 1 FPS | 10s | 6 | 0.21s (0.35%) |
| **Background** | 0.5 FPS (2s) | 30s | 2 | 0.07s (0.12%) |

*Assumes 35ms per health check (quality + tampering)*

### Recommendations

**For Critical Quality Assurance**:
```yaml
health_check_interval_seconds: 0.0  # Every frame
```
- ~2-3% CPU overhead at typical sampling rates
- Ensures every submitted frame is validated
- Recommended when quality is paramount

**For Stable Environments** (RECOMMENDED):
```yaml
health_check_interval_seconds: 10.0  # Every 10 seconds
```
- ~0.35% CPU overhead
- **80-90% CPU savings** vs. every-frame checking
- Detects gradual degradation (focus, lighting changes)
- Best balance of monitoring and performance

**For Security/Tampering Detection**:
```yaml
health_check_interval_seconds: 5.0  # Every 5 seconds
check_tampering: true
```
- ~0.7% CPU overhead
- Detects tampering within 5 seconds
- Alerts on obstruction, movement, focus changes

**For Background Health Monitoring**:
```yaml
health_check_interval_seconds: 30.0  # Every 30 seconds
```
- ~0.12% CPU overhead (negligible)
- Periodic camera health checks
- Long-term diagnostics and trending

## API Integration (Future)

**Planned endpoints**:
```
GET /api/v1/streams/{stream_name}/health
```
Response:
```json
{
  "stream_name": "camera_line_1",
  "status": "healthy",
  "score": 95.0,
  "quality_metrics": {
    "blur_score": 345.2,
    "brightness": 128.3,
    "contrast": 52.1
  },
  "quality_issues": [],
  "tampering_issues": []
}
```

**Reset reference frame**:
```
POST /api/v1/streams/{stream_name}/reset-reference
```

## Example Use Cases

### 1. Quality Assurance Inspection

**Scenario**: Camera must capture sharp, well-lit images for defect detection

**Configuration**:
```yaml
camera_health:
  enabled: true
  check_tampering: false  # Not needed
  log_health_status: true
  skip_unhealthy_frames: true
  blur_threshold: 150.0  # Require sharp images
  brightness_low: 80.0  # Well-lit
  brightness_high: 200.0
  contrast_low: 40.0  # High contrast
```

### 2. Security-Critical Camera

**Scenario**: Camera monitors restricted area, must detect tampering

**Configuration**:
```yaml
camera_health:
  enabled: true
  check_tampering: true  # ENABLE tampering detection
  log_health_status: true
  skip_unhealthy_frames: true
  obstruction_threshold: 0.2  # Sensitive to obstruction
  movement_threshold: 30.0  # Sensitive to movement
```

### 3. Low-Light Environment

**Scenario**: Camera operates in dim lighting

**Configuration**:
```yaml
camera_health:
  enabled: true
  check_tampering: false
  log_health_status: true
  skip_unhealthy_frames: false  # Allow darker frames
  blur_threshold: 80.0  # Lower bar for sharpness
  brightness_low: 20.0  # Accept darker images
  brightness_high: 180.0
  contrast_low: 20.0  # Lower contrast acceptable
```

## Troubleshooting

### Issue: All frames marked as blurry

**Solution**: Lower `blur_threshold`
- Log current blur scores
- Set threshold to 70% of minimum acceptable score

### Issue: All frames too dark

**Solution**: Lower `brightness_low`
- Check camera lighting
- Adjust camera exposure settings
- Lower threshold to match environment

### Issue: Constant obstruction alerts

**Solution**:
- Check if camera scene is naturally dark (e.g., night vision)
- Increase `obstruction_threshold`
- Or disable tampering detection: `check_tampering: false`

### Issue: Frequent movement alerts

**Solution**:
- Camera might be on vibrating surface
- Increase `movement_threshold`
- Or reset reference frame after intentional movement

### Issue: High CPU usage

**Solution**:
- Disable tampering detection: `check_tampering: false`
- Increase `sampling_interval_seconds` (capture less frequently)
- Use quality assessment only: `enabled: true, check_tampering: false`

## Summary

Camera health monitoring provides:
- ✅ **Image quality validation** (blur, brightness, contrast)
- ✅ **Tampering detection** (obstruction, movement, focus changes)
- ✅ **Configurable thresholds** per stream
- ✅ **Automatic frame filtering** (skip bad frames)
- ✅ **Comprehensive logging** for troubleshooting

**When to use**:
- Quality-critical inspections (always enable quality checks)
- Security cameras (enable tampering detection)
- Production monitoring (log health status for diagnostics)

**Performance**: ~20-35ms overhead per frame (negligible for typical 1-5 FPS streams)
