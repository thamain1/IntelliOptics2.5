import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import BoundingBoxAnnotator, { BoundingBox } from '../components/BoundingBoxAnnotator';

interface Escalation {
  id: string;
  query_id: string;
  created_at: string;
  reason?: string;
  resolved: boolean;
}

interface Query {
  id: string;
  image_url: string;
  image_blob_path: string;
  result_label: string;
  result: string;
  confidence: number;
  detector_id: string;
  created_at: string;
}

interface Annotation {
  id: string;
  query_id: string;
  image_blob_path: string;
  x: number;
  y: number;
  width: number;
  height: number;
  label: string;
  confidence: number | null;
  source: 'model' | 'human';
  model_name: string | null;
  review_status: string;
}

interface DetectorConfig {
  detector_id: string;
  class_names: string[] | null;
}

const EscalationQueuePage: React.FC = () => {
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [selected, setSelected] = useState<Escalation | null>(null);
  const [selectedQuery, setSelectedQuery] = useState<Query | null>(null);
  const [label, setLabel] = useState('YES');
  const [confidence, setConfidence] = useState<number | ''>('');
  const [notes, setNotes] = useState('');
  const [count, setCount] = useState<number | ''>('');
  const [loadingQuery, setLoadingQuery] = useState(false);

  // Annotation state
  const [annotationMode, setAnnotationMode] = useState(false);
  const [boundingBoxes, setBoundingBoxes] = useState<BoundingBox[]>([]);
  const [availableLabels, setAvailableLabels] = useState<string[]>(['YES', 'NO', 'object', 'defect']);
  const [savingAnnotations, setSavingAnnotations] = useState(false);

  const fetchEscalations = async () => {
    try {
      const res = await axios.get<Escalation[]>('/escalations');
      setEscalations(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchEscalations();
  }, []);

  const handleResolve = async (esc: Escalation) => {
    // Fetch query details before showing resolve confirmation
    setLoadingQuery(true);
    try {
      const queryRes = await axios.get<Query>(`/queries/${esc.query_id}`);
      setSelectedQuery(queryRes.data);
      setSelected(esc);
      setLabel('YES');
      setConfidence('');
      setNotes('');
      setCount('');
    } catch (err) {
      console.error('Failed to fetch query details:', err);
      alert('Failed to load query details');
    } finally {
      setLoadingQuery(false);
    }
  };

  const handleAnnotate = async (esc: Escalation) => {
    setLoadingQuery(true);
    try {
      const queryRes = await axios.get<Query>(`/queries/${esc.query_id}`);
      setSelectedQuery(queryRes.data);
      setSelected(esc);
      setLabel('YES');
      setConfidence('');
      setNotes('');
      setCount('');
      setAnnotationMode(true);

      // Load existing annotations for this query
      try {
        const annotationsRes = await axios.get<Annotation[]>(`/annotations/by-query/${esc.query_id}`);
        const loadedBoxes: BoundingBox[] = annotationsRes.data.map(ann => ({
          id: ann.id,
          x: ann.x,
          y: ann.y,
          width: ann.width,
          height: ann.height,
          label: ann.label,
          confidence: ann.confidence,
          source: ann.source,
          review_status: ann.review_status,
        }));
        setBoundingBoxes(loadedBoxes);
      } catch {
        setBoundingBoxes([]);
      }

      // Load detector config for class names
      if (queryRes.data.detector_id) {
        try {
          const configRes = await axios.get<DetectorConfig>(`/detectors/${queryRes.data.detector_id}/config`);
          if (configRes.data?.class_names && configRes.data.class_names.length > 0) {
            setAvailableLabels(configRes.data.class_names);
          }
        } catch {
          // Keep default labels if config fetch fails
        }
      }
    } catch (err) {
      console.error('Failed to fetch query details:', err);
      alert('Failed to load query details');
    } finally {
      setLoadingQuery(false);
    }
  };

  const saveAnnotations = useCallback(async () => {
    if (!selectedQuery) return;

    setSavingAnnotations(true);
    try {
      // Delete existing annotations for this query
      await axios.delete(`/annotations/by-query/${selectedQuery.id}`);

      // Save new annotations
      if (boundingBoxes.length > 0) {
        const payload = {
          query_id: selectedQuery.id,
          image_blob_path: selectedQuery.image_blob_path || '',
          source: 'human' as const,
          annotations: boundingBoxes.map(box => ({
            x: box.x,
            y: box.y,
            width: box.width,
            height: box.height,
            label: box.label,
            confidence: box.confidence,
          })),
        };
        await axios.post('/annotations/bulk', payload);
      }
    } catch (err) {
      console.error('Failed to save annotations:', err);
      throw err;
    } finally {
      setSavingAnnotations(false);
    }
  }, [selectedQuery, boundingBoxes]);

  const confirmResolve = async () => {
    if (!selected) return;
    try {
      await axios.post(`/escalations/${selected.id}/resolve`);
      setSelected(null);
      setSelectedQuery(null);
      fetchEscalations();
    } catch (err) {
      console.error(err);
    }
  };

  const submitAnnotation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected) return;
    try {
      // 1. Save bounding box annotations if in annotation mode
      if (annotationMode) {
        await saveAnnotations();
      }

      // 2. Submit feedback/annotation
      await axios.post(`/queries/${selected.query_id}/feedback`, {
        label,
        confidence: confidence === '' ? null : Number(confidence),
        notes: notes || null,
        count: count === '' ? null : Number(count),
      });

      // 3. Explicitly set ground_truth for metrics calculation
      await axios.patch(`/queries/${selected.query_id}`, {
        ground_truth: label
      });

      // 4. Resolve the escalation
      await axios.post(`/escalations/${selected.id}/resolve`);
      setSelected(null);
      setSelectedQuery(null);
      setAnnotationMode(false);
      setBoundingBoxes([]);
      fetchEscalations();
    } catch (err) {
      console.error(err);
    }
  };

  const closeModal = () => {
    setSelected(null);
    setSelectedQuery(null);
    setAnnotationMode(false);
    setBoundingBoxes([]);
  };

  return (
    <div className="p-8 bg-gray-900 text-gray-300 min-h-screen">
      <h2 className="text-3xl font-bold text-white mb-8">Escalation Queue</h2>
      
      <div className="bg-gray-800 rounded-lg shadow-md overflow-hidden mb-8">
        <table className="min-w-full divide-y divide-gray-700">
          <thead className="bg-gray-700">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">ID</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Query</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Created</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Reason</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-gray-800 divide-y divide-gray-700">
            {escalations.length === 0 ? (
                <tr>
                    <td colSpan={5} className="px-6 py-4 text-center text-gray-500 italic">No pending escalations.</td>
                </tr>
            ) : escalations.map((esc) => (
              <tr key={esc.id} className="hover:bg-gray-700 transition">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-400">{esc.id.substring(0, 8)}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-blue-400">{esc.query_id.substring(0, 8)}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-400">{new Date(esc.created_at).toLocaleString()}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-yellow-400">{esc.reason}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  <button
                    className="text-green-400 hover:text-green-300 mr-4 transition"
                    onClick={() => handleResolve(esc)}
                  >
                    Resolve
                  </button>
                  <button
                    className="text-blue-400 hover:text-blue-300 transition"
                    onClick={() => handleAnnotate(esc)}
                  >
                    Annotate
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selected && selectedQuery && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center p-4 z-50">
          <div className="bg-gray-800 rounded-lg p-6 max-w-5xl w-full shadow-xl border border-gray-700 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-bold text-white">
                {annotationMode ? 'Annotate Image' : 'Resolve Escalation'}
                <span className="text-blue-400 font-mono ml-2">{selected.query_id.substring(0,8)}</span>
              </h3>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setAnnotationMode(!annotationMode)}
                  className={`px-3 py-1 rounded text-sm ${
                    annotationMode
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  {annotationMode ? 'Drawing Mode' : 'Enable Drawing'}
                </button>
              </div>
            </div>

            {/* Query Image with Annotation Canvas */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-400 mb-2">
                {annotationMode ? 'Draw bounding boxes on the image' : 'Query Image'}
              </label>
              {selectedQuery.image_url ? (
                annotationMode ? (
                  <BoundingBoxAnnotator
                    imageUrl={selectedQuery.image_url}
                    boxes={boundingBoxes}
                    availableLabels={availableLabels}
                    onBoxesChange={setBoundingBoxes}
                    readOnly={false}
                  />
                ) : (
                  <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
                    <img
                      src={selectedQuery.image_url}
                      alt="Query"
                      className="max-w-full max-h-96 mx-auto rounded"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none';
                        (e.target as HTMLImageElement).parentElement!.innerHTML = '<p class="text-red-400 text-center">Failed to load image</p>';
                      }}
                    />
                  </div>
                )
              ) : (
                <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
                  <p className="text-gray-500 text-center">No image available</p>
                </div>
              )}
            </div>

            {/* Query Details */}
            <div className="mb-6 bg-gray-900 rounded-lg p-4 border border-gray-700">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-400">Detector Result:</span>
                  <span className="text-white ml-2 font-semibold">{selectedQuery.result}</span>
                </div>
                <div>
                  <span className="text-gray-400">Confidence:</span>
                  <span className="text-white ml-2 font-mono">{(selectedQuery.confidence * 100).toFixed(1)}%</span>
                </div>
                <div>
                  <span className="text-gray-400">Escalation Reason:</span>
                  <span className="text-yellow-400 ml-2">{selected.reason}</span>
                </div>
                <div>
                  <span className="text-gray-400">Created:</span>
                  <span className="text-white ml-2">{new Date(selectedQuery.created_at).toLocaleString()}</span>
                </div>
              </div>
            </div>

            <form onSubmit={submitAnnotation} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Ground Truth Label</label>
                <select value={label} onChange={(e) => setLabel(e.target.value)} className="block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2">
                  <option value="YES">YES (Correct)</option>
                  <option value="NO">NO (Incorrect)</option>
                  <option value="UNCLEAR">UNCLEAR</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                    <label className="block text-sm font-medium text-gray-400 mb-1">Confidence (0-1)</label>
                    <input
                        type="number"
                        step="0.01"
                        min="0"
                        max="1"
                        value={confidence}
                        onChange={(e) => setConfidence(e.target.value === '' ? '' : Number(e.target.value))}
                        className="block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2"
                        placeholder="e.g. 0.95"
                    />
                </div>
                <div>
                    <label className="block text-sm font-medium text-gray-400 mb-1">Count (optional)</label>
                    <input
                        type="number"
                        min="0"
                        value={count}
                        onChange={(e) => setCount(e.target.value === '' ? '' : Number(e.target.value))}
                        className="block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2"
                    />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Notes</label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={3}
                  className="block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2"
                  placeholder="Add context for retraining..."
                />
              </div>
              <div className="flex justify-end space-x-3 mt-6">
                <button
                  type="button"
                  className="bg-gray-600 hover:bg-gray-500 text-white font-bold py-2 px-4 rounded transition"
                  onClick={closeModal}
                >
                  Cancel
                </button>
                {!annotationMode && label === 'YES' && confidence === '' && notes === '' ? (
                  <button
                    type="button"
                    onClick={confirmResolve}
                    className="bg-green-600 hover:bg-green-500 text-white font-bold py-2 px-4 rounded transition"
                  >
                    Resolve Without Annotation
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={savingAnnotations}
                    className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-4 rounded transition disabled:opacity-50"
                  >
                    {savingAnnotations ? 'Saving...' : annotationMode ? `Save ${boundingBoxes.length} Annotation${boundingBoxes.length !== 1 ? 's' : ''} & Resolve` : 'Submit & Resolve'}
                  </button>
                )}
              </div>
            </form>
          </div>
        </div>
      )}

      {loadingQuery && (
        <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <p className="text-white">Loading query details...</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default EscalationQueuePage;