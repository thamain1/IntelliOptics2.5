import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

interface Detection {
  label: string;
  confidence: number;
  bbox?: number[];  // [x, y, width, height] normalized 0-1
}

interface Query {
  id: string;
  detector_id?: string | null;
  created_at: string;
  image_blob_path?: string;
  image_url?: string;
  result_label?: string;
  confidence?: number;
  status: string;
  local_inference: boolean;
  escalated: boolean;
  ground_truth?: string;
  is_correct?: boolean;
  detections_json?: Detection[];
}

interface QueryListResponse {
  queries: Query[];
  total: number;
  skip: number;
  limit: number;
}

const QueryHistoryPage: React.FC = () => {
  const [queries, setQueries] = useState<Query[]>([]);
  const [detectors, setDetectors] = useState<{ id: string; name: string }[]>([]);
  const [showVerified, setShowVerified] = useState(false);
  const [previewQuery, setPreviewQuery] = useState<Query | null>(null);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [loading, setLoading] = useState(false);
  const [labelFilter, setLabelFilter] = useState<string>('');
  const [maxConfidence, setMaxConfidence] = useState<number>(1.0);
  const limit = 20;

  const fetchQueries = async (resetSkip = false) => {
    try {
      setLoading(true);
      const currentSkip = resetSkip ? 0 : skip;
      const params: Record<string, any> = { skip: currentSkip, limit, show_verified: showVerified };
      if (labelFilter) params.label_filter = labelFilter;
      if (maxConfidence < 1.0) params.max_confidence = maxConfidence;
      const res = await axios.get<QueryListResponse>('/queries', { params });
      setQueries(res.data.queries);
      setTotal(res.data.total);
      if (resetSkip) setSkip(0);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchDetectors = async () => {
    try {
      const res = await axios.get<{ id: string; name: string }[]>('/detectors');
      setDetectors(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchQueries(true);
    fetchDetectors();
  }, []);

  useEffect(() => {
    fetchQueries(true);
  }, [showVerified, labelFilter, maxConfidence]);

  const handleVerifyGroundTruth = async (queryId: string, groundTruth: string) => {
    try {
      await axios.patch(`/queries/${queryId}`, {
        ground_truth: groundTruth
      });
      toast.success('Ground truth saved');
      // Remove from local state immediately
      setQueries(prev => prev.filter(q => q.id !== queryId));
      setTotal(prev => prev - 1);
    } catch (err) {
      toast.error('Failed to save ground truth');
      console.error(err);
    }
  };

  const handleSkip = async (queryId: string) => {
    try {
      await axios.patch(`/queries/${queryId}`, {
        ground_truth: 'skipped'
      });
      toast.info('Query skipped');
      // Remove from local state
      setQueries(prev => prev.filter(q => q.id !== queryId));
      setTotal(prev => prev - 1);
    } catch (err) {
      toast.error('Failed to skip query');
      console.error(err);
    }
  };

  const handleDelete = async (queryId: string) => {
    if (!confirm('Are you sure you want to permanently delete this query and its image?')) {
      return;
    }
    try {
      await axios.delete(`/queries/${queryId}`);
      toast.success('Query deleted');
      // Remove from local state
      setQueries(prev => prev.filter(q => q.id !== queryId));
      setTotal(prev => prev - 1);
    } catch (err) {
      toast.error('Failed to delete query');
      console.error(err);
    }
  };

  const handleLoadMore = () => {
    const newSkip = skip + limit;
    setSkip(newSkip);
    const params: Record<string, any> = { skip: newSkip, limit, show_verified: showVerified };
    if (labelFilter) params.label_filter = labelFilter;
    if (maxConfidence < 1.0) params.max_confidence = maxConfidence;
    axios.get<QueryListResponse>('/queries', { params }).then(res => {
      setQueries(prev => [...prev, ...res.data.queries]);
      setTotal(res.data.total);
    }).catch(err => console.error(err));
  };

  const getDetectorName = (detectorId: string | null | undefined) => {
    if (!detectorId) return 'Unknown';
    const detector = detectors.find(d => d.id === detectorId);
    return detector?.name || detectorId.substring(0, 8);
  };

  // Queries are now filtered server-side
  const hasMore = queries.length < total;

  return (
    <div className="p-8 bg-gray-900 text-gray-300 min-h-screen">
      <h2 className="text-3xl font-bold text-white mb-8">Image Queries</h2>

      {/* Filter Controls */}
      <div className="bg-gray-800 rounded-lg p-4 mb-6 border border-gray-700">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <h3 className="text-xl font-semibold text-white">
              {showVerified ? 'All Queries' : 'Pending Review'}
            </h3>
            <span className="text-sm text-gray-400">
              (showing {queries.length} of {total})
            </span>
          </div>
          <div className="flex items-center gap-4 flex-wrap">
            {/* Label Filter */}
            <input
              type="text"
              placeholder="Filter by label..."
              value={labelFilter}
              onChange={(e) => setLabelFilter(e.target.value)}
              className="px-3 py-2 rounded bg-gray-700 border border-gray-600 text-white text-sm focus:border-blue-500 focus:outline-none w-40"
            />
            {/* Confidence Slider */}
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-400 whitespace-nowrap">
                Max Confidence:
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={maxConfidence}
                onChange={(e) => setMaxConfidence(parseFloat(e.target.value))}
                className="w-24 accent-blue-500"
              />
              <span className="text-sm text-white w-12">
                {maxConfidence < 1.0 ? `< ${(maxConfidence * 100).toFixed(0)}%` : 'All'}
              </span>
            </div>
            {/* Show All Toggle */}
            <button
              onClick={() => setShowVerified(!showVerified)}
              className={`px-4 py-2 rounded text-sm font-medium transition ${
                showVerified
                  ? 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  : 'bg-blue-600 text-white hover:bg-blue-500'
              }`}
            >
              {showVerified ? 'Show Pending Only' : 'Show All'}
            </button>
          </div>
        </div>
      </div>

      {/* Query Cards Grid */}
      {loading && queries.length === 0 ? (
        <div className="bg-gray-800 rounded-lg p-12 text-center border border-gray-700">
          <p className="text-gray-400 text-lg">Loading...</p>
        </div>
      ) : queries.length === 0 ? (
        <div className="bg-gray-800 rounded-lg p-12 text-center border border-gray-700">
          <p className="text-gray-400 text-lg">
            {showVerified ? 'No queries found.' : 'No pending queries to review.'}
          </p>
        </div>
      ) : (
        <>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {queries.map((q) => (
            <div
              key={q.id}
              className="bg-gray-800 rounded-lg overflow-hidden border border-gray-700 hover:border-gray-600 transition"
            >
              {/* Image with Bounding Boxes */}
              <div
                className="aspect-video bg-gray-900 flex items-center justify-center cursor-pointer relative"
                onClick={() => setPreviewQuery(q)}
              >
                {q.image_url ? (
                  <>
                    <img
                      src={q.image_url}
                      alt="Query"
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none';
                      }}
                    />
                    {/* Bounding Box Overlays */}
                    {q.detections_json?.map((det, idx) => det.bbox && (
                      <div
                        key={idx}
                        className="absolute border-2 border-green-400 pointer-events-none"
                        style={{
                          left: `${det.bbox[0] * 100}%`,
                          top: `${det.bbox[1] * 100}%`,
                          width: `${det.bbox[2] * 100}%`,
                          height: `${det.bbox[3] * 100}%`,
                        }}
                      >
                        <span className="absolute -top-5 left-0 bg-green-500 text-white text-xs px-1 rounded whitespace-nowrap">
                          {det.label} {(det.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    ))}
                  </>
                ) : (
                  <span className="text-gray-600 text-sm">No image</span>
                )}
              </div>

              {/* Info */}
              <div className="p-4">
                {/* Status & Result */}
                <div className="flex items-center justify-between mb-2">
                  <span className={`px-2 py-1 text-xs font-semibold rounded ${
                    q.status === 'DONE' ? 'bg-green-900/50 text-green-400' :
                    q.status === 'ESCALATED' ? 'bg-red-900/50 text-red-400' :
                    'bg-yellow-900/50 text-yellow-400'
                  }`}>
                    {q.status}
                  </span>
                  {q.result_label && (
                    <span className="text-white font-medium">{q.result_label}</span>
                  )}
                </div>

                {/* Confidence */}
                {q.confidence !== undefined && (
                  <div className="mb-2">
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>Confidence</span>
                      <span>{(q.confidence * 100).toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-1.5">
                      <div
                        className={`h-1.5 rounded-full ${
                          q.confidence >= 0.8 ? 'bg-green-500' :
                          q.confidence >= 0.5 ? 'bg-yellow-500' : 'bg-red-500'
                        }`}
                        style={{ width: `${q.confidence * 100}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Detector & Time */}
                <div className="text-xs text-gray-500 mb-3">
                  <div>{getDetectorName(q.detector_id)}</div>
                  <div>{new Date(q.created_at).toLocaleString()}</div>
                </div>

                {/* Ground Truth Actions */}
                {q.ground_truth ? (
                  <div className={`text-center py-2 rounded ${
                    q.ground_truth === 'skipped' ? 'bg-gray-700 text-gray-400' :
                    q.is_correct ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
                  }`}>
                    <span className="text-xs font-medium">
                      {q.ground_truth === 'skipped' ? 'Skipped' :
                       q.is_correct ? 'Correct' : 'Incorrect'}: {q.ground_truth}
                    </span>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleVerifyGroundTruth(q.id, q.result_label || 'yes')}
                        className="flex-1 bg-green-600 hover:bg-green-500 text-white text-sm font-medium py-2 px-3 rounded transition"
                      >
                        Correct
                      </button>
                      <button
                        onClick={() => {
                          const gt = prompt('Enter correct label:', q.result_label === 'yes' ? 'no' : 'yes');
                          if (gt) handleVerifyGroundTruth(q.id, gt);
                        }}
                        className="flex-1 bg-red-600 hover:bg-red-500 text-white text-sm font-medium py-2 px-3 rounded transition"
                      >
                        Wrong
                      </button>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleSkip(q.id)}
                        className="flex-1 bg-gray-600 hover:bg-gray-500 text-white text-sm font-medium py-1.5 px-3 rounded transition"
                      >
                        Skip
                      </button>
                      <button
                        onClick={() => handleDelete(q.id)}
                        className="flex-1 bg-red-900 hover:bg-red-800 text-red-300 text-sm font-medium py-1.5 px-3 rounded transition border border-red-700"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Load More Button */}
        {hasMore && (
          <div className="mt-6 text-center">
            <button
              onClick={handleLoadMore}
              className="bg-gray-700 hover:bg-gray-600 text-white font-medium py-2 px-6 rounded transition"
            >
              Load More ({total - queries.length} remaining)
            </button>
          </div>
        )}
        </>
      )}

      <ToastContainer position="top-right" autoClose={3000} hideProgressBar={false} theme="dark" />

      {/* Image Preview Modal */}
      {previewQuery && (
        <div
          className="fixed inset-0 bg-black bg-opacity-90 flex items-center justify-center p-4 z-50"
          onClick={() => setPreviewQuery(null)}
        >
          <div
            className="bg-gray-800 rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-4 border-b border-gray-700 flex justify-between items-center">
              <div>
                <h3 className="text-lg font-bold text-white">Query Details</h3>
                <p className="text-sm text-gray-400">ID: {previewQuery.id}</p>
              </div>
              <button
                className="text-gray-400 hover:text-white text-2xl"
                onClick={() => setPreviewQuery(null)}
              >
                &times;
              </button>
            </div>
            <div className="p-4">
              {previewQuery.image_url ? (
                <div className="relative inline-block mx-auto">
                  <img
                    src={previewQuery.image_url}
                    alt="Query"
                    className="max-h-[60vh] rounded"
                  />
                  {/* Bounding Box Overlays */}
                  {previewQuery.detections_json?.map((det, idx) => det.bbox && (
                    <div
                      key={idx}
                      className="absolute border-2 border-green-400 pointer-events-none"
                      style={{
                        left: `${det.bbox[0] * 100}%`,
                        top: `${det.bbox[1] * 100}%`,
                        width: `${det.bbox[2] * 100}%`,
                        height: `${det.bbox[3] * 100}%`,
                      }}
                    >
                      <span className="absolute -top-6 left-0 bg-green-500 text-white text-sm px-2 py-0.5 rounded whitespace-nowrap">
                        {det.label} {(det.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="h-64 bg-gray-900 rounded flex items-center justify-center">
                  <span className="text-gray-500">No image available</span>
                </div>
              )}
            </div>
            <div className="p-4 border-t border-gray-700 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-gray-400">Result:</span>
                <span className="text-white ml-2 font-medium">{previewQuery.result_label || '—'}</span>
              </div>
              <div>
                <span className="text-gray-400">Confidence:</span>
                <span className="text-white ml-2">{previewQuery.confidence ? (previewQuery.confidence * 100).toFixed(1) + '%' : '—'}</span>
              </div>
              <div>
                <span className="text-gray-400">Status:</span>
                <span className="text-white ml-2">{previewQuery.status}</span>
              </div>
              <div>
                <span className="text-gray-400">Detector:</span>
                <span className="text-white ml-2">{getDetectorName(previewQuery.detector_id)}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default QueryHistoryPage;
