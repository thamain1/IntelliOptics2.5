import React, { useRef, useState, useEffect, useCallback } from 'react';

export interface BoundingBox {
  id?: string;
  x: number;      // normalized 0-1
  y: number;      // normalized 0-1
  width: number;  // normalized 0-1
  height: number; // normalized 0-1
  label: string;
  confidence?: number | null;
  source: 'model' | 'human';
  review_status?: string;
}

interface BoundingBoxAnnotatorProps {
  imageUrl: string;
  boxes: BoundingBox[];
  availableLabels: string[];
  onBoxesChange: (boxes: BoundingBox[]) => void;
  onBoxSelect?: (box: BoundingBox | null) => void;
  readOnly?: boolean;
}

const COLORS = [
  '#22c55e', // green
  '#3b82f6', // blue
  '#f59e0b', // amber
  '#ef4444', // red
  '#8b5cf6', // violet
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#f97316', // orange
];

const BoundingBoxAnnotator: React.FC<BoundingBoxAnnotatorProps> = ({
  imageUrl,
  boxes,
  availableLabels,
  onBoxesChange,
  onBoxSelect,
  readOnly = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const [imageDimensions, setImageDimensions] = useState({ width: 0, height: 0 });
  const [isDrawing, setIsDrawing] = useState(false);
  const [drawStart, setDrawStart] = useState<{ x: number; y: number } | null>(null);
  const [currentBox, setCurrentBox] = useState<BoundingBox | null>(null);
  const [selectedBoxIndex, setSelectedBoxIndex] = useState<number | null>(null);
  const [selectedLabel, setSelectedLabel] = useState(availableLabels[0] || 'object');
  const [isResizing, setIsResizing] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  // Color mapping for labels
  const labelColors = useCallback((label: string) => {
    const index = availableLabels.indexOf(label);
    return COLORS[index % COLORS.length];
  }, [availableLabels]);

  // Handle image load
  const handleImageLoad = () => {
    if (imageRef.current) {
      setImageDimensions({
        width: imageRef.current.naturalWidth,
        height: imageRef.current.naturalHeight,
      });
    }
  };

  // Convert pixel coordinates to normalized (0-1)
  const pixelToNormalized = useCallback((px: number, py: number) => {
    if (!containerRef.current) return { x: 0, y: 0 };
    const rect = containerRef.current.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, px / rect.width)),
      y: Math.max(0, Math.min(1, py / rect.height)),
    };
  }, []);

  // Convert normalized to pixel coordinates
  const normalizedToPixel = useCallback((nx: number, ny: number) => {
    if (!containerRef.current) return { x: 0, y: 0 };
    const rect = containerRef.current.getBoundingClientRect();
    return {
      x: nx * rect.width,
      y: ny * rect.height,
    };
  }, []);

  // Get mouse position relative to container
  const getMousePos = useCallback((e: React.MouseEvent) => {
    if (!containerRef.current) return { x: 0, y: 0 };
    const rect = containerRef.current.getBoundingClientRect();
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    };
  }, []);

  // Handle mouse down
  const handleMouseDown = (e: React.MouseEvent) => {
    if (readOnly) return;
    e.preventDefault();

    const pos = getMousePos(e);
    const normalized = pixelToNormalized(pos.x, pos.y);

    // Check if clicking on a resize handle
    if (selectedBoxIndex !== null) {
      const box = boxes[selectedBoxIndex];
      const handleSize = 8;
      const boxPx = {
        x: box.x * (containerRef.current?.clientWidth || 0),
        y: box.y * (containerRef.current?.clientHeight || 0),
        width: box.width * (containerRef.current?.clientWidth || 0),
        height: box.height * (containerRef.current?.clientHeight || 0),
      };

      // Check corners for resize
      const corners = [
        { name: 'nw', x: boxPx.x, y: boxPx.y },
        { name: 'ne', x: boxPx.x + boxPx.width, y: boxPx.y },
        { name: 'sw', x: boxPx.x, y: boxPx.y + boxPx.height },
        { name: 'se', x: boxPx.x + boxPx.width, y: boxPx.y + boxPx.height },
      ];

      for (const corner of corners) {
        if (Math.abs(pos.x - corner.x) < handleSize && Math.abs(pos.y - corner.y) < handleSize) {
          setIsResizing(corner.name);
          return;
        }
      }

      // Check if dragging the box
      if (
        pos.x >= boxPx.x &&
        pos.x <= boxPx.x + boxPx.width &&
        pos.y >= boxPx.y &&
        pos.y <= boxPx.y + boxPx.height
      ) {
        setIsDragging(true);
        setDragOffset({
          x: normalized.x - box.x,
          y: normalized.y - box.y,
        });
        return;
      }
    }

    // Check if clicking on an existing box
    for (let i = boxes.length - 1; i >= 0; i--) {
      const box = boxes[i];
      if (
        normalized.x >= box.x &&
        normalized.x <= box.x + box.width &&
        normalized.y >= box.y &&
        normalized.y <= box.y + box.height
      ) {
        setSelectedBoxIndex(i);
        onBoxSelect?.(box);
        return;
      }
    }

    // Start drawing new box
    setSelectedBoxIndex(null);
    onBoxSelect?.(null);
    setIsDrawing(true);
    setDrawStart(normalized);
    setCurrentBox({
      x: normalized.x,
      y: normalized.y,
      width: 0,
      height: 0,
      label: selectedLabel,
      source: 'human',
    });
  };

  // Handle mouse move
  const handleMouseMove = (e: React.MouseEvent) => {
    if (readOnly) return;

    const pos = getMousePos(e);
    const normalized = pixelToNormalized(pos.x, pos.y);

    if (isDrawing && drawStart) {
      setCurrentBox({
        x: Math.min(drawStart.x, normalized.x),
        y: Math.min(drawStart.y, normalized.y),
        width: Math.abs(normalized.x - drawStart.x),
        height: Math.abs(normalized.y - drawStart.y),
        label: selectedLabel,
        source: 'human',
      });
    } else if (isResizing && selectedBoxIndex !== null) {
      const box = { ...boxes[selectedBoxIndex] };
      const newBoxes = [...boxes];

      switch (isResizing) {
        case 'se':
          box.width = Math.max(0.02, normalized.x - box.x);
          box.height = Math.max(0.02, normalized.y - box.y);
          break;
        case 'sw':
          box.width = Math.max(0.02, box.x + box.width - normalized.x);
          box.height = Math.max(0.02, normalized.y - box.y);
          box.x = Math.min(normalized.x, box.x + box.width - 0.02);
          break;
        case 'ne':
          box.width = Math.max(0.02, normalized.x - box.x);
          box.height = Math.max(0.02, box.y + box.height - normalized.y);
          box.y = Math.min(normalized.y, box.y + box.height - 0.02);
          break;
        case 'nw':
          box.width = Math.max(0.02, box.x + box.width - normalized.x);
          box.height = Math.max(0.02, box.y + box.height - normalized.y);
          box.x = Math.min(normalized.x, box.x + box.width - 0.02);
          box.y = Math.min(normalized.y, box.y + box.height - 0.02);
          break;
      }

      newBoxes[selectedBoxIndex] = box;
      onBoxesChange(newBoxes);
    } else if (isDragging && selectedBoxIndex !== null) {
      const box = { ...boxes[selectedBoxIndex] };
      const newBoxes = [...boxes];

      box.x = Math.max(0, Math.min(1 - box.width, normalized.x - dragOffset.x));
      box.y = Math.max(0, Math.min(1 - box.height, normalized.y - dragOffset.y));

      newBoxes[selectedBoxIndex] = box;
      onBoxesChange(newBoxes);
    }
  };

  // Handle mouse up
  const handleMouseUp = () => {
    if (isDrawing && currentBox && currentBox.width > 0.01 && currentBox.height > 0.01) {
      const newBoxes = [...boxes, currentBox];
      onBoxesChange(newBoxes);
      setSelectedBoxIndex(newBoxes.length - 1);
      onBoxSelect?.(currentBox);
    }

    setIsDrawing(false);
    setDrawStart(null);
    setCurrentBox(null);
    setIsResizing(null);
    setIsDragging(false);
  };

  // Handle key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (readOnly) return;

      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedBoxIndex !== null) {
          const newBoxes = boxes.filter((_, i) => i !== selectedBoxIndex);
          onBoxesChange(newBoxes);
          setSelectedBoxIndex(null);
          onBoxSelect?.(null);
        }
      } else if (e.key === 'Escape') {
        setSelectedBoxIndex(null);
        onBoxSelect?.(null);
        setIsDrawing(false);
        setCurrentBox(null);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [readOnly, selectedBoxIndex, boxes, onBoxesChange, onBoxSelect]);

  // Update selected box label
  const updateSelectedBoxLabel = (newLabel: string) => {
    if (selectedBoxIndex !== null) {
      const newBoxes = [...boxes];
      newBoxes[selectedBoxIndex] = { ...newBoxes[selectedBoxIndex], label: newLabel };
      onBoxesChange(newBoxes);
    }
  };

  // Delete selected box
  const deleteSelectedBox = () => {
    if (selectedBoxIndex !== null) {
      const newBoxes = boxes.filter((_, i) => i !== selectedBoxIndex);
      onBoxesChange(newBoxes);
      setSelectedBoxIndex(null);
      onBoxSelect?.(null);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Toolbar */}
      {!readOnly && (
        <div className="flex items-center gap-4 p-2 bg-gray-900 rounded-lg">
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-400">Label:</label>
            <select
              value={selectedLabel}
              onChange={(e) => setSelectedLabel(e.target.value)}
              className="bg-gray-700 text-white text-sm rounded px-2 py-1 border border-gray-600"
            >
              {availableLabels.map((label) => (
                <option key={label} value={label}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          {selectedBoxIndex !== null && (
            <>
              <div className="h-6 w-px bg-gray-600" />
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-400">Selected:</span>
                <select
                  value={boxes[selectedBoxIndex]?.label || ''}
                  onChange={(e) => updateSelectedBoxLabel(e.target.value)}
                  className="bg-gray-700 text-white text-sm rounded px-2 py-1 border border-gray-600"
                >
                  {availableLabels.map((label) => (
                    <option key={label} value={label}>
                      {label}
                    </option>
                  ))}
                </select>
                <button
                  onClick={deleteSelectedBox}
                  className="bg-red-600 hover:bg-red-500 text-white text-sm px-2 py-1 rounded"
                >
                  Delete
                </button>
              </div>
            </>
          )}

          <div className="flex-1" />
          <span className="text-xs text-gray-500">
            {boxes.length} annotation{boxes.length !== 1 ? 's' : ''} | Click & drag to draw
          </span>
        </div>
      )}

      {/* Canvas */}
      <div
        ref={containerRef}
        className="relative bg-gray-900 rounded-lg overflow-hidden cursor-crosshair"
        style={{ maxHeight: '60vh' }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <img
          ref={imageRef}
          src={imageUrl}
          alt="Annotation canvas"
          className="w-full h-auto"
          onLoad={handleImageLoad}
          draggable={false}
        />

        {/* Existing boxes */}
        {boxes.map((box, index) => {
          const isSelected = selectedBoxIndex === index;
          const color = labelColors(box.label);

          return (
            <div
              key={index}
              className={`absolute border-2 ${isSelected ? 'border-white' : ''}`}
              style={{
                left: `${box.x * 100}%`,
                top: `${box.y * 100}%`,
                width: `${box.width * 100}%`,
                height: `${box.height * 100}%`,
                borderColor: isSelected ? '#fff' : color,
                backgroundColor: `${color}20`,
              }}
            >
              {/* Label tag */}
              <div
                className="absolute -top-6 left-0 px-2 py-0.5 text-xs font-medium text-white rounded-t"
                style={{ backgroundColor: color }}
              >
                {box.label}
                {box.confidence !== null && box.confidence !== undefined && (
                  <span className="ml-1 opacity-75">{(box.confidence * 100).toFixed(0)}%</span>
                )}
                {box.source === 'model' && (
                  <span className="ml-1 opacity-50">[AI]</span>
                )}
              </div>

              {/* Resize handles (only when selected and not readOnly) */}
              {isSelected && !readOnly && (
                <>
                  <div className="absolute -left-1 -top-1 w-3 h-3 bg-white border border-gray-800 cursor-nw-resize" />
                  <div className="absolute -right-1 -top-1 w-3 h-3 bg-white border border-gray-800 cursor-ne-resize" />
                  <div className="absolute -left-1 -bottom-1 w-3 h-3 bg-white border border-gray-800 cursor-sw-resize" />
                  <div className="absolute -right-1 -bottom-1 w-3 h-3 bg-white border border-gray-800 cursor-se-resize" />
                </>
              )}
            </div>
          );
        })}

        {/* Current drawing box */}
        {currentBox && currentBox.width > 0 && currentBox.height > 0 && (
          <div
            className="absolute border-2 border-dashed border-white"
            style={{
              left: `${currentBox.x * 100}%`,
              top: `${currentBox.y * 100}%`,
              width: `${currentBox.width * 100}%`,
              height: `${currentBox.height * 100}%`,
              backgroundColor: `${labelColors(selectedLabel)}40`,
            }}
          />
        )}
      </div>

      {/* Box list */}
      {boxes.length > 0 && (
        <div className="bg-gray-900 rounded-lg p-3 max-h-48 overflow-y-auto">
          <h4 className="text-sm font-medium text-gray-400 mb-2">Annotations</h4>
          <div className="space-y-1">
            {boxes.map((box, index) => (
              <div
                key={index}
                className={`flex items-center justify-between p-2 rounded cursor-pointer transition ${
                  selectedBoxIndex === index
                    ? 'bg-gray-700 border border-gray-500'
                    : 'bg-gray-800 hover:bg-gray-700'
                }`}
                onClick={() => {
                  setSelectedBoxIndex(index);
                  onBoxSelect?.(box);
                }}
              >
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: labelColors(box.label) }}
                  />
                  <span className="text-sm text-white">{box.label}</span>
                  {box.confidence !== null && box.confidence !== undefined && (
                    <span className="text-xs text-gray-400">
                      ({(box.confidence * 100).toFixed(0)}%)
                    </span>
                  )}
                  <span
                    className={`text-xs px-1 rounded ${
                      box.source === 'model' ? 'bg-blue-600' : 'bg-green-600'
                    }`}
                  >
                    {box.source}
                  </span>
                </div>
                {!readOnly && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      const newBoxes = boxes.filter((_, i) => i !== index);
                      onBoxesChange(newBoxes);
                      if (selectedBoxIndex === index) {
                        setSelectedBoxIndex(null);
                        onBoxSelect?.(null);
                      }
                    }}
                    className="text-red-400 hover:text-red-300 text-xs"
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Instructions */}
      {!readOnly && (
        <div className="text-xs text-gray-500 text-center">
          Click and drag to draw a box | Click a box to select | Press Delete to remove | Drag corners to resize
        </div>
      )}
    </div>
  );
};

export default BoundingBoxAnnotator;
