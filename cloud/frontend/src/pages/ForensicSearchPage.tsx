import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';

interface SearchJob {
  id: string;
  query_text: string;
  source_type: string;
  source_url: string;
  status: string;
  progress_pct: number;
  total_frames: number;
  frames_scanned: number;
  matches_found: number;
  created_at: string;
}

interface SearchResult {
  id: string;
  job_id: string;
  timestamp_sec: number | null;
  camera_id: string | null;
  confidence: number;
  bbox: number[] | null;
  label: string | null;
  description: string | null;
  frame_url: string | null;
  created_at: string;
}

export default function ForensicSearchPage() {
  const [jobs, setJobs] = useState<SearchJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<SearchJob | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);

  // New job form
  const [queryText, setQueryText] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceType, setSourceType] = useState('video_file');
  const [uploading, setUploading] = useState(false);
  const [uploadedFilename, setUploadedFilename] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const pollRef = useRef<ReturnType<typeof setInterval>>();

  const fetchJobs = useCallback(async () => {
    try {
      const res = await axios.get('/forensic-search/jobs');
      setJobs(res.data);
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
    }
  }, []);

  const fetchResults = useCallback(async (jobId: string) => {
    try {
      const res = await axios.get(`/forensic-search/jobs/${jobId}/results`);
      setResults(res.data);
    } catch (err) {
      console.error('Failed to fetch results:', err);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Poll active job for progress
  useEffect(() => {
    if (selectedJob && (selectedJob.status === 'RUNNING' || selectedJob.status === 'PENDING')) {
      pollRef.current = setInterval(async () => {
        try {
          const res = await axios.get(`/forensic-search/jobs/${selectedJob.id}`);
          setSelectedJob(res.data);
          if (res.data.matches_found > 0) {
            fetchResults(selectedJob.id);
          }
          if (res.data.status !== 'RUNNING' && res.data.status !== 'PENDING') {
            clearInterval(pollRef.current);
            fetchResults(selectedJob.id);
            fetchJobs();
          }
        } catch (err) {
          console.error('Poll failed:', err);
        }
      }, 2000);

      return () => clearInterval(pollRef.current);
    }
  }, [selectedJob, fetchResults, fetchJobs]);

  const createJob = async () => {
    if (!queryText.trim() || !sourceUrl.trim()) return;
    setCreating(true);
    try {
      const res = await axios.post('/forensic-search/jobs', {
        query_text: queryText,
        source_type: sourceType,
        source_url: sourceUrl,
      });
      setSelectedJob(res.data);
      setQueryText('');
      setSourceUrl('');
      setUploadedFilename('');
      fetchJobs();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create search job');
    } finally {
      setCreating(false);
    }
  };

  const stopJob = async (jobId: string) => {
    try {
      const res = await axios.post(`/forensic-search/jobs/${jobId}/stop`);
      setSelectedJob(res.data);
      fetchJobs();
    } catch (err) {
      console.error('Failed to stop job:', err);
    }
  };

  const deleteJob = async (jobId: string) => {
    if (!confirm('Delete this search job and all its results?')) return;
    try {
      await axios.delete(`/forensic-search/jobs/${jobId}`);
      if (selectedJob?.id === jobId) {
        setSelectedJob(null);
        setResults([]);
      }
      fetchJobs();
    } catch (err) {
      console.error('Failed to delete job:', err);
    }
  };

  const deleteAllJobs = async () => {
    if (!confirm(`Delete all ${jobs.length} search jobs?`)) return;
    try {
      await Promise.all(jobs.map(j => axios.delete(`/forensic-search/jobs/${j.id}`)));
      setSelectedJob(null);
      setResults([]);
      fetchJobs();
    } catch (err) {
      console.error('Failed to delete jobs:', err);
    }
  };

  const uploadVideo = async (file: File) => {
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await axios.post('/forensic-search/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000,
      });
      const path = res.data.path;
      setSourceUrl(path);
      setUploadedFilename(res.data.filename);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to upload video');
    } finally {
      setUploading(false);
    }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('video/')) {
      uploadVideo(file);
    }
  };

  const formatTime = (seconds: number | null) => {
    if (seconds === null) return '—';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const statusColors: Record<string, string> = {
    PENDING: 'bg-yellow-600',
    RUNNING: 'bg-blue-600',
    COMPLETED: 'bg-green-600',
    CANCELLED: 'bg-gray-600',
    ERROR: 'bg-red-600',
  };

  return (
    <div className="space-y-6">
      <h1 className="font-display uppercase tracking-ioWide text-3xl font-bold text-white">
        Forensic <span className="text-brand-primary">Search</span>
      </h1>

      {/* Create New Search */}
      <div className="bg-gray-800 rounded-lg p-4 space-y-3">
        <h2 className="text-sm font-medium text-gray-400">New Search</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-2">
            <label className="block text-sm text-gray-400 mb-1">Search Query</label>
            <input
              type="text"
              value={queryText}
              onChange={e => setQueryText(e.target.value)}
              placeholder="Man with red backpack near Lot C around 3PM"
              className="w-full bg-brand-bg2 text-white rounded px-3 py-2 text-sm border border-brand-line"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Source Type</label>
            <select
              value={sourceType}
              onChange={e => setSourceType(e.target.value)}
              className="w-full bg-brand-bg2 text-white rounded px-3 py-2 text-sm border border-brand-line"
            >
              <option value="video_file">Video File</option>
              <option value="dvr">DVR Recording</option>
              <option value="rtsp_recording">RTSP Recording</option>
            </select>
          </div>
        </div>
        {/* Video Upload */}
        <div>
          <label className="block text-sm text-gray-400 mb-1">Video Source</label>
          <div
            className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${
              uploading ? 'border-blue-500 bg-blue-900/20' :
              uploadedFilename ? 'border-green-500 bg-green-900/20' :
              'border-brand-line hover:border-gray-400'
            }`}
            onDragOver={e => e.preventDefault()}
            onDrop={handleFileDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              className="hidden"
              onChange={e => {
                const file = e.target.files?.[0];
                if (file) uploadVideo(file);
              }}
            />
            {uploading ? (
              <p className="text-blue-400 text-sm">Uploading video...</p>
            ) : uploadedFilename ? (
              <p className="text-green-400 text-sm">Uploaded: {uploadedFilename} (click to change)</p>
            ) : (
              <p className="text-gray-400 text-sm">
                Click or drag & drop a video file (MP4, MKV, AVI, MOV)
              </p>
            )}
          </div>
        </div>

        <div className="flex justify-end">
          <button
            onClick={createJob}
            disabled={creating || uploading || !queryText.trim() || !sourceUrl.trim()}
            className="bg-brand-primary hover:bg-brand-primaryH text-black disabled:bg-gray-600 text-white px-6 py-2 rounded text-sm font-medium whitespace-nowrap"
          >
            {creating ? 'Creating...' : 'Start Search'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Job List */}
        <div className="space-y-3">
          <div className="flex justify-between items-center">
            <h2 className="text-sm font-medium text-gray-400">Search Jobs</h2>
            {jobs.length > 0 && (
              <button
                onClick={deleteAllJobs}
                className="text-red-400 hover:text-red-300 text-xs"
              >
                Clear All
              </button>
            )}
          </div>
          {jobs.length === 0 ? (
            <p className="text-gray-500 text-sm">No search jobs yet.</p>
          ) : (
            jobs.map(job => (
              <div
                key={job.id}
                className={`bg-gray-800 rounded-lg p-3 cursor-pointer border ${
                  selectedJob?.id === job.id ? 'border-blue-500' : 'border-transparent'
                } hover:border-brand-line`}
                onClick={() => {
                  setSelectedJob(job);
                  fetchResults(job.id);
                }}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-white text-sm font-medium truncate max-w-[200px]">
                    {job.query_text}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded ${statusColors[job.status] || 'bg-gray-600'}`}>
                    {job.status}
                  </span>
                </div>
                {job.status === 'RUNNING' && (
                  <div className="w-full bg-brand-bg2 rounded-full h-1.5 mt-2">
                    <div
                      className="bg-blue-500 h-1.5 rounded-full transition-all"
                      style={{ width: `${job.progress_pct}%` }}
                    />
                  </div>
                )}
                <div className="flex justify-between items-center text-gray-500 text-xs mt-1">
                  <span>{job.matches_found} matches</span>
                  <span>{new Date(job.created_at + 'Z').toLocaleString()}</span>
                </div>
                <button
                  onClick={e => { e.stopPropagation(); deleteJob(job.id); }}
                  className="mt-2 w-full text-center text-xs text-red-400 hover:text-red-300 hover:bg-red-900/20 rounded py-1 transition-colors"
                >
                  Delete
                </button>
              </div>
            ))
          )}
        </div>

        {/* Selected Job Details + Results */}
        <div className="lg:col-span-2 space-y-4">
          {selectedJob ? (
            <>
              {/* Job Info */}
              <div className="bg-gray-800 rounded-lg p-4">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h3 className="text-white font-medium">{selectedJob.query_text}</h3>
                    <p className="text-gray-500 text-xs mt-1">{selectedJob.source_url}</p>
                  </div>
                  {(selectedJob.status === 'RUNNING' || selectedJob.status === 'PENDING') && (
                    <button
                      onClick={() => stopJob(selectedJob.id)}
                      className="bg-red-600 hover:bg-red-500 text-white px-3 py-1 rounded text-sm"
                    >
                      Stop
                    </button>
                  )}
                </div>

                {/* Progress */}
                <div className="grid grid-cols-3 gap-4 text-center">
                  <div>
                    <div className="font-display text-3xl font-bold text-brand-primary">{selectedJob.frames_scanned}</div>
                    <div className="text-xs text-gray-500">Frames Scanned</div>
                  </div>
                  <div>
                    <div className="font-display text-3xl font-bold text-brand-primary">{selectedJob.matches_found}</div>
                    <div className="text-xs text-gray-500">Matches Found</div>
                  </div>
                  <div>
                    <div className="font-display text-3xl font-bold text-brand-primary">{selectedJob.progress_pct.toFixed(0)}%</div>
                    <div className="text-xs text-gray-500">Progress</div>
                  </div>
                </div>

                {selectedJob.status === 'RUNNING' && (
                  <div className="w-full bg-brand-bg2 rounded-full h-2 mt-3">
                    <div
                      className="bg-blue-500 h-2 rounded-full transition-all"
                      style={{ width: `${selectedJob.progress_pct}%` }}
                    />
                  </div>
                )}
              </div>

              {/* Results Gallery */}
              <div className="bg-gray-800 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-400 mb-3">
                  Results ({results.length})
                </h3>
                {results.length === 0 ? (
                  <p className="text-gray-500 text-sm text-center py-8">
                    {selectedJob.status === 'RUNNING' ? 'Searching...' : 'No matches found.'}
                  </p>
                ) : (
                  <div className="space-y-4">
                    {results.map(result => (
                      <div key={result.id} className="bg-brand-bg2 rounded-lg overflow-hidden flex flex-col md:flex-row">
                        {/* Frame image */}
                        <div className="md:w-1/2 flex-shrink-0">
                          {result.frame_url ? (
                            <img
                              src={result.frame_url}
                              alt={result.label || 'Match'}
                              className="w-full h-48 md:h-full object-contain bg-black"
                            />
                          ) : (
                            <div className="w-full h-48 bg-gray-600 flex items-center justify-center text-gray-400 text-sm">
                              No Preview
                            </div>
                          )}
                        </div>
                        {/* Details */}
                        <div className="p-4 flex-1 space-y-2">
                          <div className="flex justify-between items-start">
                            <div>
                              <span className="text-white font-medium text-sm capitalize">{result.label || 'Match'}</span>
                              <span className="text-gray-500 text-xs ml-2">@ {formatTime(result.timestamp_sec)}</span>
                            </div>
                            <span className="bg-green-600 text-white text-xs px-2 py-0.5 rounded">
                              {(result.confidence * 100).toFixed(0)}%
                            </span>
                          </div>
                          {result.description && (
                            <p className="text-gray-300 text-sm leading-relaxed">{result.description}</p>
                          )}
                          {result.bbox && (
                            <div className="text-gray-500 text-xs">
                              Bbox: [{result.bbox.map(v => v.toFixed(3)).join(', ')}]
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="bg-gray-800 rounded-lg p-8 text-center text-gray-500">
              Select a search job to view results, or create a new search above.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
