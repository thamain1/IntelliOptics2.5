import React, { useState, useRef, useCallback } from 'react';
import axios from 'axios';
import LiveBboxOverlay, { Detection } from '../components/LiveBboxOverlay';

interface QueryResult {
  id: string;
  question: string;
  answer: string;
  confidence: number;
  detections: Detection[];
  timestamp: string;
}

export default function OpenVocabPage() {
  const [mode, setMode] = useState<'detect' | 'query'>('detect');
  const [prompts, setPrompts] = useState('');
  const [question, setQuestion] = useState('');
  const [confidence, setConfidence] = useState(0.25);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [queryHistory, setQueryHistory] = useState<QueryResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setImageFile(file);
      setImagePreview(URL.createObjectURL(file));
      setDetections([]);
    }
  };

  const toBase64 = (file: File): Promise<string> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => {
        const result = reader.result as string;
        resolve(result.split(',')[1]); // Strip data:...;base64, prefix
      };
      reader.onerror = reject;
    });

  const handleDetect = useCallback(async () => {
    if (!imageFile || !prompts.trim()) return;
    setLoading(true);
    setError(null);

    try {
      const imageData = await toBase64(imageFile);
      const res = await axios.post('/open-vocab/detect', {
        prompts: prompts,
        confidence_threshold: confidence,
        image_data: imageData,
      });

      const dets: Detection[] = (res.data.detections || []).map((d: any) => ({
        label: d.label,
        confidence: d.confidence,
        bbox: d.bbox,
      }));

      setDetections(dets);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  }, [imageFile, prompts, confidence]);

  const handleQuery = useCallback(async () => {
    if (!imageFile || !question.trim()) return;
    setLoading(true);
    setError(null);

    try {
      const imageData = await toBase64(imageFile);
      const res = await axios.post('/open-vocab/query', {
        question: question,
        image_data: imageData,
      });

      const result: QueryResult = {
        id: Date.now().toString(),
        question: question,
        answer: res.data.answer,
        confidence: res.data.confidence,
        detections: res.data.bboxes || [],
        timestamp: new Date().toISOString(),
      };

      setQueryHistory(prev => [result, ...prev]);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  }, [imageFile, question]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display uppercase tracking-ioWide text-3xl font-bold text-white">
          Visual <span className="text-brand-primary">Insight</span>
        </h1>
        <div className="inline-flex border border-brand-line">
          <button
            onClick={() => setMode('detect')}
            className={`px-6 py-2.5 font-display uppercase tracking-ioWide text-xs font-bold border-r border-brand-line transition-colors ${
              mode === 'detect' ? 'bg-brand-primary text-black' : 'bg-transparent text-brand-textDim hover:text-brand-primary'
            }`}
          >
            Detect
          </button>
          <button
            onClick={() => setMode('query')}
            className={`px-6 py-2.5 font-display uppercase tracking-ioWide text-xs font-bold transition-colors ${
              mode === 'query' ? 'bg-brand-primary text-black' : 'bg-transparent text-brand-textDim hover:text-brand-primary'
            }`}
          >
            Analyze Scene
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Image + Controls */}
        <div className="space-y-4">
          {/* Image upload */}
          <div className="bg-gray-800 rounded-lg p-4">
            <label className="block text-sm font-medium text-gray-400 mb-2">Upload Image</label>
            <input
              type="file"
              accept="image/*"
              onChange={handleImageSelect}
              className="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded file:bg-brand-bg2 file:text-white file:border-0 hover:file:bg-gray-600"
            />
          </div>

          {/* Image preview with bbox overlay */}
          {imagePreview && (
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="relative inline-block w-full">
                <img
                  ref={imageRef}
                  src={imagePreview}
                  alt="Upload preview"
                  className="w-full h-auto rounded"
                />
                <LiveBboxOverlay
                  videoRef={imageRef}
                  detections={detections}
                  fps={5}
                  showLabels={true}
                  showConfidence={true}
                />
              </div>
            </div>
          )}

          {/* Controls */}
          <div className="bg-gray-800 rounded-lg p-4 space-y-3">
            {mode === 'detect' ? (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">
                    Detection Prompts (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={prompts}
                    onChange={e => setPrompts(e.target.value)}
                    placeholder="person, car, fire, red truck..."
                    className="w-full bg-brand-bg2 text-white rounded px-3 py-2 text-sm border border-brand-line focus:border-brand-primary focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">
                    Confidence: {confidence}
                  </label>
                  <input
                    type="range"
                    min={0.05}
                    max={0.95}
                    step={0.05}
                    value={confidence}
                    onChange={e => setConfidence(parseFloat(e.target.value))}
                    className="w-full"
                  />
                </div>
                <button
                  onClick={handleDetect}
                  disabled={loading || !imageFile || !prompts.trim()}
                  className="w-full bg-brand-primary hover:bg-brand-primaryH disabled:bg-gray-600 disabled:text-gray-400 text-black font-display uppercase tracking-ioWide text-sm font-bold py-3 transition-colors"
                >
                  {loading ? 'Detecting...' : 'Run Detection'}
                </button>
              </>
            ) : (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">
                    Ask a Question
                  </label>
                  <input
                    type="text"
                    value={question}
                    onChange={e => setQuestion(e.target.value)}
                    placeholder="Is there a person wearing a red hat?"
                    className="w-full bg-brand-bg2 text-white rounded px-3 py-2 text-sm border border-brand-line focus:border-purple-500 focus:outline-none"
                  />
                </div>
                <button
                  onClick={handleQuery}
                  disabled={loading || !imageFile || !question.trim()}
                  className="w-full bg-brand-primary hover:bg-brand-primaryH disabled:bg-gray-600 disabled:text-gray-400 text-black font-display uppercase tracking-ioWide text-sm font-bold py-3 transition-colors"
                >
                  {loading ? 'Thinking...' : 'Analyze Scene'}
                </button>
              </>
            )}
          </div>

          {error && (
            <div className="bg-red-900/50 border border-red-700 rounded p-3 text-red-300 text-sm">
              {error}
            </div>
          )}
        </div>

        {/* Right: Results */}
        <div className="space-y-4">
          {/* Detection Results */}
          {mode === 'detect' && detections.length > 0 && (
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-400 mb-3">
                Detections ({detections.length})
              </h3>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {detections.map((det, i) => (
                  <div key={i} className="flex items-center justify-between bg-brand-bg2 rounded p-2">
                    <span className="text-white text-sm font-medium">{det.label}</span>
                    <span className="text-gray-400 text-sm">
                      {(det.confidence * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* VLM Query History */}
          {mode === 'query' && queryHistory.length > 0 && (
            <div className="bg-gray-800 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-400 mb-3">Query History</h3>
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {queryHistory.map(result => (
                  <div key={result.id} className="bg-brand-bg2 rounded p-3">
                    <p className="text-purple-400 text-sm font-medium">Q: {result.question}</p>
                    <p className="text-white text-sm mt-1">A: {result.answer}</p>
                    <p className="text-gray-500 text-xs mt-1">
                      {new Date(result.timestamp).toLocaleTimeString()}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Instructions */}
          <div className="bg-gray-800 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-400 mb-2">How it works</h3>
            {mode === 'detect' ? (
              <ul className="text-gray-500 text-xs space-y-1">
                <li>1. Upload an image</li>
                <li>2. Type what to detect (e.g., "person, car, fire")</li>
                <li>3. The system finds objects matching your prompts — no training needed</li>
                <li>4. Bounding boxes are drawn on the image in real-time</li>
              </ul>
            ) : (
              <ul className="text-gray-500 text-xs space-y-1">
                <li>1. Upload an image</li>
                <li>2. Ask a natural language question about it</li>
                <li>3. The system analyzes the scene and answers</li>
                <li>4. Supports complex queries like "Is the gate open?"</li>
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
