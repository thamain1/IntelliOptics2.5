import React, { useRef, useEffect, useCallback } from 'react';

export interface Detection {
  label: string;
  confidence: number;
  bbox: number[]; // [x1, y1, x2, y2] normalized 0-1
  mask_polygon?: number[][]; // [[x, y], ...] normalized 0-1 — SAM output
}

interface LiveBboxOverlayProps {
  videoRef: React.RefObject<HTMLVideoElement | HTMLImageElement | null>;
  detections: Detection[];
  fps?: number;
  showLabels?: boolean;
  showConfidence?: boolean;
  mirrored?: boolean;
  colorMap?: Record<string, string>;
  showSegment?: boolean; // when true, draw SAM polygon instead of bbox
}

const DEFAULT_COLORS = [
  '#22c55e', '#3b82f6', '#f59e0b', '#ef4444',
  '#8b5cf6', '#ec4899', '#06b6d4', '#f97316',
];

function getColor(label: string, colorMap?: Record<string, string>): string {
  if (colorMap && colorMap[label]) return colorMap[label];
  let hash = 0;
  for (let i = 0; i < label.length; i++) {
    hash = label.charCodeAt(i) + ((hash << 5) - hash);
  }
  return DEFAULT_COLORS[Math.abs(hash) % DEFAULT_COLORS.length];
}

const LiveBboxOverlay: React.FC<LiveBboxOverlayProps> = ({
  videoRef,
  detections,
  fps = 30,
  showLabels = true,
  showConfidence = true,
  mirrored = false,
  colorMap,
  showSegment = false,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrameRef = useRef<number>(0);
  const detectionsRef = useRef<Detection[]>(detections);

  // Keep detections ref in sync
  useEffect(() => {
    detectionsRef.current = detections;
  }, [detections]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;

    const rect = video.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;

    // Size canvas to match the video element
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, rect.width, rect.height);

    const dets = detectionsRef.current;
    if (!dets || dets.length === 0) return;

    const w = rect.width;
    const h = rect.height;

    for (const det of dets) {
      if (!det.bbox || det.bbox.length < 4) continue;

      const [x1, y1, x2, y2] = det.bbox;
      const bx = mirrored ? (1 - x2) * w : x1 * w;
      const by = y1 * h;
      const bw = (x2 - x1) * w;
      const bh = (y2 - y1) * h;

      const color = getColor(det.label, colorMap);
      const hasPoly = showSegment && det.mask_polygon && det.mask_polygon.length >= 3;

      if (hasPoly) {
        // Draw SAM polygon
        const pts = det.mask_polygon!;
        ctx.beginPath();
        const px0 = mirrored ? (1 - pts[0][0]) * w : pts[0][0] * w;
        ctx.moveTo(px0, pts[0][1] * h);
        for (let i = 1; i < pts.length; i++) {
          const px = mirrored ? (1 - pts[i][0]) * w : pts[i][0] * w;
          ctx.lineTo(px, pts[i][1] * h);
        }
        ctx.closePath();
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.fillStyle = color + '30';
        ctx.fill();
      } else {
        // Draw bounding box
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.strokeRect(bx, by, bw, bh);
        ctx.fillStyle = color + '20';
        ctx.fillRect(bx, by, bw, bh);
      }

      // Label — anchor to top-left of bbox regardless of mode
      if (showLabels) {
        const labelText = showConfidence
          ? `${det.label} ${(det.confidence * 100).toFixed(0)}%`
          : det.label;

        ctx.font = '12px monospace';
        const metrics = ctx.measureText(labelText);
        const labelH = 18;
        const labelW = metrics.width + 8;

        ctx.fillStyle = color;
        ctx.fillRect(bx, by - labelH, labelW, labelH);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(labelText, bx + 4, by - 5);
      }
    }
  }, [videoRef, showLabels, showConfidence, mirrored, colorMap, showSegment]);

  useEffect(() => {
    const interval = 1000 / fps;
    let lastTime = 0;

    const animate = (time: number) => {
      if (time - lastTime >= interval) {
        draw();
        lastTime = time;
      }
      animFrameRef.current = requestAnimationFrame(animate);
    };

    animFrameRef.current = requestAnimationFrame(animate);

    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, [draw, fps]);

  // ResizeObserver to handle container resize
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const observer = new ResizeObserver(() => draw());
    observer.observe(video);
    return () => observer.disconnect();
  }, [videoRef, draw]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
      }}
    />
  );
};

export default LiveBboxOverlay;
