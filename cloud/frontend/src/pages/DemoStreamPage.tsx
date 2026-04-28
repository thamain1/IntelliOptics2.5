import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast, ToastContainer } from 'react-toastify';
import YouTube from 'react-youtube';
import LiveBboxOverlay, { Detection as BboxDetection } from '../components/LiveBboxOverlay';

interface DemoSession {
  id: string;
  name: string;
  youtube_url: string;
  youtube_video_id: string;
  capture_mode: 'polling' | 'motion' | 'manual' | 'yoloworld' | 'yoloe';
  polling_interval_ms: number;
  motion_threshold: number;
  detector_ids: string[];
  status: string;
  total_frames_captured: number;
  total_detections: number;
  started_at: string;
  error_message?: string;
  last_frame_at?: string;
  yoloworld_prompts?: string;
}

interface DetectionResult {
  id: string;
  detector_id: string;
  result_label: string;
  confidence: number;
  status: string;
  created_at: string;
  frame_number: number;
}

interface Detector {
  id: string;
  name: string;
}

const DemoStreamPage: React.FC = () => {
  // Session state
  const [activeSession, setActiveSession] = useState<DemoSession | null>(null);
  const [results, setResults] = useState<DetectionResult[]>([]);

  // Configuration state
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [captureMode, setCaptureMode] = useState<'polling' | 'motion' | 'manual' | 'webcam' | 'yoloworld' | 'yoloe'>('polling');
  const [pollingInterval, setPollingInterval] = useState(2000);
  const [selectedDetectors, setSelectedDetectors] = useState<string[]>([]);
  const [detectors, setDetectors] = useState<Detector[]>([]);
  const [detectorGroups, setDetectorGroups] = useState<string[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<string>('all');
  const [detectorSearch, setDetectorSearch] = useState<string>('');

  // YOLOWorld/YOLOE state
  const [yoloworldPrompts, setYoloworldPrompts] = useState<string>('person, car, fire, smoke');
  const yoloworldPromptsRef = useRef<string>('person, car, fire, smoke');
  const captureModeRef = useRef<string>('polling');

  // Live overlay state
  const [overlayDetections, setOverlayDetections] = useState<BboxDetection[]>([]);
  const [showOverlay, setShowOverlay] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const overlayVideoRef = useRef<HTMLVideoElement | HTMLImageElement | null>(null);
  const detectionPollingRef = useRef<number | null>(null);

  // Video player state
  const [player, setPlayer] = useState<any>(null);

  // Live frame preview state
  const [latestFrameUrl, setLatestFrameUrl] = useState<string | null>(null);
  const framePollingRef = useRef<number | null>(null);

  // Webcam state
  const [webcamStream, setWebcamStream] = useState<MediaStream | null>(null);
  const webcamVideoRef = useRef<HTMLVideoElement>(null);
  const webcamCaptureRef = useRef<number | null>(null);

  // Canvas for manual/webcam capture
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Refs for values needed in intervals (to avoid stale closures)
  const activeSessionRef = useRef<DemoSession | null>(null);
  const selectedDetectorsRef = useRef<string[]>([]);

  // Polling for results
  const resultsPollingRef = useRef<number | null>(null);

  useEffect(() => {
    fetchDetectors();
    fetchDetectorGroups();
    return () => {
      stopResultsPolling();
      stopFramePolling();
      stopDetectionPolling();
      stopWebcam();
    };
  }, []);

  // Keep refs updated for use in intervals
  useEffect(() => {
    activeSessionRef.current = activeSession;
  }, [activeSession]);

  useEffect(() => {
    selectedDetectorsRef.current = selectedDetectors;
  }, [selectedDetectors]);

  useEffect(() => {
    yoloworldPromptsRef.current = yoloworldPrompts;
  }, [yoloworldPrompts]);

  useEffect(() => {
    captureModeRef.current = captureMode;
  }, [captureMode]);

  // Attach webcam stream to video element when both are available
  useEffect(() => {
    if (webcamStream && webcamVideoRef.current) {
      console.log('Attaching webcam stream to video element');
      webcamVideoRef.current.srcObject = webcamStream;
      webcamVideoRef.current.play().catch(e => console.log('Video autoplay error:', e));
    }
  }, [webcamStream, activeSession]); // activeSession triggers re-check when session starts

  // Note: Server-side capture is now handled by the backend for polling and motion modes
  // Client-side capture is only used for manual mode via the "Capture Frame Now" button

  const fetchDetectors = async () => {
    try {
      const res = await axios.get('/detectors');
      setDetectors(res.data);
    } catch (err) {
      toast.error('Failed to load detectors');
    }
  };

  const fetchDetectorGroups = async () => {
    try {
      const res = await axios.get('/detectors/groups');
      setDetectorGroups(res.data);
    } catch (err) {
      console.error('Failed to load detector groups');
    }
  };

  const filteredDetectors = detectors.filter(det => {
    const matchesGroup = selectedGroup === 'all' || (det as any).group_name === selectedGroup;
    const matchesSearch = det.name.toLowerCase().includes(detectorSearch.toLowerCase());
    return matchesGroup && matchesSearch;
  });

  const extractYouTubeId = (url: string): string | null => {
    const patterns = [
      /(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)/,
      /youtube\.com\/embed\/([^&\n?#]+)/,
    ];
    for (const pattern of patterns) {
      const match = url.match(pattern);
      if (match) return match[1];
    }
    return null;
  };

  const isYouTubeUrl = (url: string): boolean => {
    return url.includes('youtube.com') || url.includes('youtu.be');
  };

  const startSession = async () => {
    // Determine if IntelliSearch/YOLOE will use webcam or stream URL
    const isOpenVocab = captureMode === 'yoloworld' || captureMode === 'yoloe';
    const openVocabUseWebcam = isOpenVocab && !youtubeUrl.trim();
    const openVocabUseStream = isOpenVocab && youtubeUrl.trim();

    // Webcam mode doesn't need a URL, but other modes do (except open-vocab with webcam)
    if (captureMode !== 'webcam' && !openVocabUseWebcam && !youtubeUrl) {
      toast.error('Please enter a stream URL');
      return;
    }
    // Open-vocab modes need prompts instead of detectors
    if (isOpenVocab) {
      if (!yoloworldPrompts.trim()) {
        toast.error('Please enter detection prompts');
        return;
      }
    } else if (selectedDetectors.length === 0) {
      toast.error('Please select at least one detector');
      return;
    }

    // For webcam mode or open-vocab without URL, start the camera first
    if (captureMode === 'webcam' || openVocabUseWebcam) {
      const webcamStarted = await startWebcam();
      if (!webcamStarted) return;
    }

    try {
      // Determine URL and capture mode based on settings
      let sessionUrl: string;
      let sessionCaptureMode: string;

      if (captureMode === 'webcam' || openVocabUseWebcam) {
        // Webcam or open-vocab with webcam
        sessionUrl = 'webcam://local';
        sessionCaptureMode = 'manual';
      } else if (openVocabUseStream) {
        // Open-vocab with stream URL - use polling for server-side capture
        sessionUrl = youtubeUrl;
        sessionCaptureMode = 'polling';
      } else {
        // Regular detector modes
        sessionUrl = youtubeUrl;
        sessionCaptureMode = captureMode;
      }

      const sessionData: any = {
        youtube_url: sessionUrl,
        capture_mode: sessionCaptureMode,
        polling_interval_ms: pollingInterval,
        detector_ids: isOpenVocab ? [] : selectedDetectors,
      };

      // Add prompts if in open-vocab mode
      if (isOpenVocab) {
        sessionData.yoloworld_prompts = yoloworldPrompts;
      }

      const res = await axios.post<DemoSession>('/demo-streams/sessions', sessionData);

      setActiveSession(res.data);
      setResults([]);

      if (openVocabUseStream) {
        toast.success(`${captureMode === 'yoloe' ? 'Detect' : 'IntelliSearch'} stream demo started!`);
      } else if (isOpenVocab) {
        toast.success(`${captureMode === 'yoloe' ? 'Detect' : 'IntelliSearch'} webcam demo started!`);
      } else {
        toast.success('Demo session started!');
      }

      // Start polling for results
      startResultsPolling(res.data.id);

      // Start detection overlay polling for open-vocab modes
      if (isOpenVocab) {
        startDetectionPolling(res.data.id);
      }

      // For webcam/open-vocab-webcam mode, start client-side capture; otherwise poll for server frames
      if (captureMode === 'webcam' || openVocabUseWebcam) {
        startWebcamCapture(res.data.id);
      } else {
        startFramePolling(res.data.id);
      }
    } catch (err) {
      toast.error('Failed to start session');
      console.error(err);
      // Clean up webcam if session creation failed
      if (captureMode === 'webcam' || openVocabUseWebcam) {
        stopWebcam();
      }
    }
  };

  const stopSession = async () => {
    if (!activeSession) return;

    try {
      await axios.post(`/demo-streams/sessions/${activeSession.id}/stop`);
      stopResultsPolling();
      stopFramePolling();
      stopDetectionPolling();
      stopWebcam();
      setActiveSession(null);
      toast.success('Demo session stopped');
    } catch (err) {
      toast.error('Failed to stop session');
    }
  };

  const captureFrame = async () => {
    // Manual capture for manual mode only
    console.log('Manual capture triggered');
    if (!player || !canvasRef.current || !activeSession) {
      console.log('Skipping capture - missing requirements');
      return;
    }

    try {
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');

      if (!ctx) {
        console.log('No canvas context');
        return;
      }

      // Create placeholder frame (CORS prevents actual YouTube frame capture)
      canvas.width = 640;
      canvas.height = 360;
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#fff';
      ctx.font = '20px Arial';
      ctx.fillText('Manual capture from YouTube', 150, 160);
      ctx.font = '16px Arial';
      ctx.fillStyle = '#888';
      ctx.fillText(new Date().toLocaleTimeString(), 230, 200);

      // Convert to base64
      const imageData = canvas.toDataURL('image/jpeg', 0.8);
      const base64Data = imageData.split(',')[1];

      console.log('Submitting manual frame to', selectedDetectors.length, 'detectors');

      // Submit to each selected detector
      for (const detectorId of selectedDetectors) {
        await submitFrame(base64Data, detectorId, 'manual');
      }
    } catch (err) {
      console.error('Frame capture error:', err);
    }
  };

  const submitFrame = async (base64Data: string, detectorId: string, method: string) => {
    if (!activeSession) {
      console.log('No active session, skipping submit');
      return;
    }

    try {
      console.log('Submitting frame to detector:', detectorId, 'method:', method);
      const response = await axios.post(`/demo-streams/sessions/${activeSession.id}/submit-frame`, {
        detector_id: detectorId,
        image_data: base64Data,
        capture_method: method,
      });
      console.log('Frame submitted successfully:', response.data);
    } catch (err) {
      console.error('Frame submission error:', err);
      toast.error('Failed to submit frame');
    }
  };

  // Client-side capture functions removed - server handles polling and motion detection

  const startResultsPolling = (sessionId: string) => {
    resultsPollingRef.current = window.setInterval(async () => {
      try {
        // Fetch both session stats and results
        const [sessionRes, resultsRes] = await Promise.all([
          axios.get(`/demo-streams/sessions/${sessionId}`),
          axios.get(`/demo-streams/sessions/${sessionId}/results`)
        ]);

        setActiveSession(sessionRes.data);
        setResults(resultsRes.data);
      } catch (err) {
        console.error('Results polling error:', err);
      }
    }, 2000);
  };

  const stopResultsPolling = () => {
    if (resultsPollingRef.current) {
      clearInterval(resultsPollingRef.current);
      resultsPollingRef.current = null;
    }
  };

  const startFramePolling = (sessionId: string) => {
    // Poll for latest captured frame every 500ms
    framePollingRef.current = window.setInterval(async () => {
      try {
        // Fetch frame as blob and create object URL
        const response = await axios.get(`/demo-streams/sessions/${sessionId}/latest-frame`, {
          responseType: 'blob'
        });
        const url = URL.createObjectURL(response.data);
        setLatestFrameUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev); // Clean up old URL
          return url;
        });
      } catch (err) {
        // Frame not available yet - this is expected initially
      }
    }, 500);
  };

  const stopFramePolling = () => {
    if (framePollingRef.current) {
      clearInterval(framePollingRef.current);
      framePollingRef.current = null;
    }
    if (latestFrameUrl) {
      URL.revokeObjectURL(latestFrameUrl);
      setLatestFrameUrl(null);
    }
  };

  // Detection overlay polling (for LiveBboxOverlay)
  const startDetectionPolling = (sessionId: string) => {
    detectionPollingRef.current = window.setInterval(async () => {
      try {
        const res = await axios.get(`/demo-streams/sessions/${sessionId}/latest-detections`);
        const dets = (res.data.detections || []).map((d: any) => ({
          label: d.label || 'unknown',
          confidence: d.confidence || 0,
          bbox: d.bbox || [],
        }));
        setOverlayDetections(dets);
      } catch {
        // Ignore errors during polling
      }
    }, 500);
  };

  const stopDetectionPolling = () => {
    if (detectionPollingRef.current) {
      clearInterval(detectionPollingRef.current);
      detectionPollingRef.current = null;
    }
    setOverlayDetections([]);
  };

  // Webcam functions
  const startWebcam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720 }
      });
      setWebcamStream(stream);
      // useEffect will attach stream to video element when it renders
      return true;
    } catch (err) {
      console.error('Failed to access webcam:', err);
      toast.error('Failed to access webcam. Please check permissions.');
      return false;
    }
  };

  const stopWebcam = () => {
    if (webcamCaptureRef.current) {
      clearInterval(webcamCaptureRef.current);
      webcamCaptureRef.current = null;
    }
    if (webcamStream) {
      webcamStream.getTracks().forEach(track => track.stop());
      setWebcamStream(null);
    }
  };

  const startWebcamCapture = (sessionId: string) => {
    webcamCaptureRef.current = window.setInterval(() => {
      captureWebcamFrame();
    }, pollingInterval);
  };

  const captureWebcamFrame = async () => {
    const session = activeSessionRef.current;
    const detectorIds = selectedDetectorsRef.current;
    const prompts = yoloworldPromptsRef.current;

    if (!webcamVideoRef.current || !canvasRef.current || !session) {
      console.log('Webcam capture skipped - missing:', {
        video: !!webcamVideoRef.current,
        canvas: !!canvasRef.current,
        session: !!session
      });
      return;
    }

    const video = webcamVideoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Check if video is ready
    if (video.readyState < 2) {
      console.log('Video not ready yet, readyState:', video.readyState);
      return;
    }

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const imageData = canvas.toDataURL('image/jpeg', 0.85);
    const base64Data = imageData.split(',')[1];

    // Check if this is an open-vocab session (no detectors, has prompts)
    const isOpenVocabSession = session.yoloworld_prompts || (detectorIds.length === 0 && prompts);
    // Determine if we should use YOLOE endpoint (default for new sessions)
    const useYoloe = captureModeRef.current === 'yoloe';

    if (isOpenVocabSession) {
      // Open-vocab mode - send to YOLOE or YOLOWorld endpoint
      const endpoint = useYoloe ? 'submit-yoloe-frame' : 'submit-yoloworld-frame';
      console.log(`Capturing webcam frame for ${useYoloe ? 'IO-E' : 'YOLOWorld'} with prompts: ${prompts}`);
      try {
        await axios.post(`/demo-streams/sessions/${session.id}/${endpoint}`, {
          image_data: base64Data,
          prompts: prompts,
          capture_method: useYoloe ? 'yoloe' : 'yoloworld',
        });
      } catch (err) {
        console.error('Open-vocab frame submission error:', err);
      }
    } else {
      // Regular mode - submit to all selected detectors
      console.log(`Capturing webcam frame, submitting to ${detectorIds.length} detectors`);
      for (const detectorId of detectorIds) {
        try {
          await axios.post(`/demo-streams/sessions/${session.id}/submit-frame`, {
            detector_id: detectorId,
            image_data: base64Data,
            capture_method: 'webcam',
          });
        } catch (err) {
          console.error('Frame submission error:', err);
        }
      }
    }
  };

  const onPlayerReady = (event: any) => {
    setPlayer(event.target);
  };

  const videoId = extractYouTubeId(youtubeUrl);

  // Calculate detection counts by class
  const getDetectionCounts = () => {
    const totalCounts: { [key: string]: number } = {};
    const latestFrameCounts: { [key: string]: number } = {};

    // Get latest frame number
    const latestFrame = results.length > 0 ? Math.max(...results.map(r => r.frame_number)) : 0;

    results.forEach(result => {
      if (result.result_label && result.result_label !== 'no_detection') {
        // Total counts
        totalCounts[result.result_label] = (totalCounts[result.result_label] || 0) + 1;

        // Latest frame counts
        if (result.frame_number === latestFrame) {
          latestFrameCounts[result.result_label] = (latestFrameCounts[result.result_label] || 0) + 1;
        }
      }
    });

    return { totalCounts, latestFrameCounts, latestFrame };
  };

  const { totalCounts, latestFrameCounts, latestFrame } = activeSession ? getDetectionCounts() : { totalCounts: {}, latestFrameCounts: {}, latestFrame: 0 };

  return (
    <div className="p-8 bg-gray-900 text-gray-300 min-h-screen">
      <ToastContainer />
      <h1 className="text-3xl font-bold text-white mb-8">Live Stream Demo</h1>

      {/* Configuration Section */}
      {!activeSession && (
        <div className="bg-gray-800 rounded-lg p-6 mb-6">
          <h2 className="text-xl font-bold text-white mb-4">Configuration</h2>

          <div className="space-y-4">
            {captureMode !== 'webcam' && (
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Stream URL
                </label>
                <input
                  type="text"
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  placeholder="rtsp://user:pass@host:port/path  ·  https://...m3u8  ·  YouTube/EarthCam URL"
                  className="w-full rounded-md bg-gray-700 border-gray-600 text-white p-2 font-mono text-sm"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Supports RTSP, RTMP, HLS, MJPEG, direct video, plus YouTube and EarthCam.
                </p>
              </div>
            )}

            {captureMode === 'webcam' && (
              <div className="p-3 bg-green-900/30 border border-green-700 rounded">
                <p className="text-green-400 text-sm">
                  Local Camera mode will use your device's webcam or USB camera.
                  Browser will request camera permission when you start the session.
                </p>
              </div>
            )}

            {captureMode === 'yoloe' && (
              <div className="p-3 bg-orange-900/30 border border-orange-700 rounded">
                <p className="text-orange-400 text-sm">
                  <strong>Real-time Detection</strong> — Type what you want to detect! Live bounding boxes rendered over video.
                  {youtubeUrl.trim()
                    ? ' Server will capture frames from the stream URL.'
                    : ' Leave the URL empty to use your webcam, or enter a stream URL.'}
                </p>
              </div>
            )}

            {captureMode === 'yoloworld' && (
              <div className="p-3 bg-purple-900/30 border border-purple-700 rounded">
                <p className="text-purple-400 text-sm">
                  <strong>IntelliSearch — Describe to Find</strong> — Type what you want to detect!
                  {youtubeUrl.trim()
                    ? ' Server will capture frames from the stream URL and run AI detection based on your prompts.'
                    : ' Leave the URL empty to use your webcam, or enter a stream URL for server-side capture.'}
                </p>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">
                Capture Mode
              </label>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => setCaptureMode('polling')}
                  className={`px-4 py-2 rounded ${
                    captureMode === 'polling'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-400'
                  }`}
                >
                  Polling
                </button>
                <button
                  onClick={() => setCaptureMode('motion')}
                  className={`px-4 py-2 rounded ${
                    captureMode === 'motion'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-400'
                  }`}
                >
                  Motion Detection
                </button>
                <button
                  onClick={() => setCaptureMode('manual')}
                  className={`px-4 py-2 rounded ${
                    captureMode === 'manual'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-400'
                  }`}
                >
                  Manual
                </button>
                <button
                  onClick={() => setCaptureMode('webcam')}
                  className={`px-4 py-2 rounded ${
                    captureMode === 'webcam'
                      ? 'bg-green-600 text-white'
                      : 'bg-gray-700 text-gray-400'
                  }`}
                >
                  Local Camera
                </button>
                <button
                  onClick={() => setCaptureMode('yoloe')}
                  className={`px-4 py-2 rounded ${
                    captureMode === 'yoloe'
                      ? 'bg-orange-600 text-white'
                      : 'bg-gray-700 text-gray-400'
                  }`}
                >
                  Detect
                </button>
                <button
                  onClick={() => setCaptureMode('yoloworld')}
                  className={`px-4 py-2 rounded ${
                    captureMode === 'yoloworld'
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-700 text-gray-400'
                  }`}
                >
                  IntelliSearch
                </button>
              </div>
            </div>

            {(captureMode === 'polling' || captureMode === 'webcam' || captureMode === 'yoloworld' || captureMode === 'yoloe') && (
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Capture Interval (ms): {pollingInterval}
                </label>
                <input
                  type="range"
                  min="500"
                  max="10000"
                  step="500"
                  value={pollingInterval}
                  onChange={(e) => setPollingInterval(Number(e.target.value))}
                  className="w-full"
                />
              </div>
            )}

            {(captureMode === 'yoloworld' || captureMode === 'yoloe') && (
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  What do you want to detect? (comma-separated)
                </label>
                <input
                  type="text"
                  value={yoloworldPrompts}
                  onChange={(e) => setYoloworldPrompts(e.target.value)}
                  placeholder="person, car, fire, smoke, hard hat, safety vest"
                  className="w-full rounded-md bg-gray-700 border-gray-600 text-white p-2"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Examples: "forklift, person, pallet" or "fire, smoke" or "dog, cat, bird"
                </p>
              </div>
            )}

            {captureMode !== 'yoloworld' && captureMode !== 'yoloe' && (
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">
                Select Detectors
              </label>
              
              <div className="flex flex-col md:flex-row gap-4 mb-4">
                <div className="flex-1">
                  <input
                    type="text"
                    placeholder="Search detectors..."
                    value={detectorSearch}
                    onChange={(e) => setDetectorSearch(e.target.value)}
                    className="w-full rounded-md bg-gray-700 border-gray-600 text-white p-2 text-sm"
                  />
                </div>
                <div className="w-full md:w-48">
                  <select
                    value={selectedGroup}
                    onChange={(e) => setSelectedGroup(e.target.value)}
                    className="w-full rounded-md bg-gray-700 border-gray-600 text-white p-2 text-sm"
                  >
                    <option value="all">All Groups</option>
                    {detectorGroups.map(group => (
                      <option key={group} value={group}>{group}</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={() => {
                    const filteredIds = filteredDetectors.map(d => d.id);
                    const allSelected = filteredIds.every(id => selectedDetectors.includes(id));
                    if (allSelected) {
                      setSelectedDetectors(selectedDetectors.filter(id => !filteredIds.includes(id)));
                    } else {
                      setSelectedDetectors([...new Set([...selectedDetectors, ...filteredIds])]);
                    }
                  }}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-xs rounded text-gray-300 transition"
                >
                  {filteredDetectors.every(d => selectedDetectors.includes(d.id)) && filteredDetectors.length > 0 ? 'Deselect All Filtered' : 'Select All Filtered'}
                </button>
              </div>

              <div className="space-y-2 max-h-48 overflow-y-auto p-2 bg-gray-900/50 rounded border border-gray-700">
                {filteredDetectors.length > 0 ? (
                  filteredDetectors.map((det) => (
                    <label key={det.id} className="flex items-center space-x-2 hover:bg-gray-700/50 p-1 rounded cursor-pointer transition">
                      <input
                        type="checkbox"
                        checked={selectedDetectors.includes(det.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedDetectors([...selectedDetectors, det.id]);
                          } else {
                            setSelectedDetectors(
                              selectedDetectors.filter((id) => id !== det.id)
                            );
                          }
                        }}
                        className="rounded border-gray-600 text-blue-600 focus:ring-blue-500 bg-gray-700"
                      />
                      <div className="flex flex-col">
                        <span className="text-sm text-gray-200">{det.name}</span>
                        {(det as any).group_name && (
                          <span className="text-[10px] text-blue-400 font-mono">{(det as any).group_name}</span>
                        )}
                      </div>
                    </label>
                  ))
                ) : (
                  <p className="text-center text-gray-500 text-sm py-4">No detectors found matching criteria</p>
                )}
              </div>
              <p className="mt-2 text-xs text-gray-500">{selectedDetectors.length} detector(s) selected</p>
            </div>
            )}

            <button
              onClick={startSession}
              className={`w-full font-bold py-2 px-4 rounded ${
                captureMode === 'yoloe'
                  ? 'bg-orange-600 hover:bg-orange-500 text-white'
                  : captureMode === 'yoloworld'
                    ? 'bg-purple-600 hover:bg-purple-500 text-white'
                    : 'bg-green-600 hover:bg-green-500 text-white'
              }`}
            >
              {captureMode === 'yoloe'
                ? (youtubeUrl.trim() ? 'Start Detect (Stream)' : 'Start Detect (Webcam)')
                : captureMode === 'yoloworld'
                  ? (youtubeUrl.trim() ? 'Start IntelliSearch (Stream)' : 'Start IntelliSearch (Webcam)')
                  : 'Start Demo Session'}
            </button>
          </div>
        </div>
      )}

      {/* Active Session */}
      {activeSession && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Video Player */}
          <div className="bg-gray-800 rounded-lg p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-white">
                {activeSession.yoloworld_prompts
                  ? (captureMode === 'yoloe' ? 'Detect Stream' : 'IntelliSearch Stream')
                  : 'Stream'}
              </h2>
              <button
                onClick={stopSession}
                className="bg-red-600 hover:bg-red-500 text-white font-bold py-2 px-4 rounded"
              >
                Stop Session
              </button>
            </div>

            {/* Open-vocab live prompt input */}
            {activeSession.yoloworld_prompts != null && (
              <div className={`mb-4 p-3 rounded border ${
                captureMode === 'yoloe' ? 'bg-orange-900/30 border-orange-700' : 'bg-purple-900/30 border-purple-700'
              }`}>
                <label className={`block text-sm font-medium mb-2 ${
                  captureMode === 'yoloe' ? 'text-orange-300' : 'text-purple-300'
                }`}>
                  Detecting (change anytime):
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={yoloworldPrompts}
                    onChange={(e) => setYoloworldPrompts(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && activeSession && yoloworldPrompts.trim()) {
                        axios.put(`/demo-streams/sessions/${activeSession.id}/prompts`, {
                          prompts: yoloworldPrompts,
                        }).then(() => toast.info(`Now detecting: ${yoloworldPrompts}`))
                          .catch(() => toast.error('Failed to update prompts'));
                      }
                    }}
                    placeholder="person, car, fire, smoke"
                    className="flex-1 rounded-md bg-gray-700 border-purple-600 text-white p-2"
                  />
                  <button
                    onClick={() => {
                      if (activeSession && yoloworldPrompts.trim()) {
                        axios.put(`/demo-streams/sessions/${activeSession.id}/prompts`, {
                          prompts: yoloworldPrompts,
                        }).then(() => toast.info(`Now detecting: ${yoloworldPrompts}`))
                          .catch(() => toast.error('Failed to update prompts'));
                      }
                    }}
                    className={`px-4 py-2 rounded font-bold text-white ${
                      captureMode === 'yoloe' ? 'bg-orange-600 hover:bg-orange-500' : 'bg-purple-600 hover:bg-purple-500'
                    }`}
                  >
                    Update
                  </button>
                </div>
                <p className="mt-1 text-xs text-gray-500">Type new prompts and click Update or press Enter</p>
              </div>
            )}

            <style>{`
              .video-zoom-wrapper {
                position: relative;
                width: 100%;
                padding-bottom: 56.25%;
                overflow: hidden;
                background: #000;
                border-radius: 0.5rem;
              }
              .video-zoom-wrapper iframe,
              .video-zoom-wrapper img,
              .video-zoom-wrapper video {
                position: absolute !important;
                top: 0 !important;
                left: 0 !important;
                width: 100% !important;
                height: 100% !important;
                border: none;
                object-fit: contain;
              }
            `}</style>
            <div className="video-zoom-wrapper" style={{ position: 'relative' }}>
              {webcamStream ? (
                <video
                  ref={(el) => {
                    (webcamVideoRef as any).current = el;
                    overlayVideoRef.current = el;
                  }}
                  autoPlay
                  playsInline
                  muted
                  style={{ transform: 'scaleX(-1)' }}
                />
              ) : isYouTubeUrl(activeSession.youtube_url) && videoId ? (
                <YouTube
                  videoId={videoId}
                  opts={{
                    width: '100%',
                    height: '100%',
                    playerVars: {
                      autoplay: 1,
                      controls: 1,
                    },
                  }}
                  onReady={onPlayerReady}
                />
              ) : latestFrameUrl ? (
                <img
                  ref={(el) => { overlayVideoRef.current = el; }}
                  src={latestFrameUrl}
                  alt="Live capture preview"
                  className="bg-black"
                />
              ) : (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900 text-center p-4">
                  <p className="text-gray-300 mb-2 animate-pulse">Waiting for first frame...</p>
                  <p className="text-gray-500 text-sm mb-4">
                    The server is capturing frames from the stream.
                  </p>
                  <a
                    href={activeSession.youtube_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded transition"
                  >
                    Open Stream in New Tab
                  </a>
                </div>
              )}
              {/* Live bounding box overlay */}
              {showOverlay && overlayDetections.length > 0 && overlayVideoRef.current && (
                <LiveBboxOverlay
                  videoRef={overlayVideoRef}
                  detections={overlayDetections}
                  showLabels={showLabels}
                  showConfidence={true}
                  mirrored={!!webcamStream}
                />
              )}
            </div>

            {/* Overlay controls */}
            {activeSession.yoloworld_prompts && (
              <div className="mt-2 flex items-center gap-4 text-sm">
                <label className="flex items-center gap-1 text-gray-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showOverlay}
                    onChange={(e) => setShowOverlay(e.target.checked)}
                    className="rounded border-gray-600 bg-gray-700"
                  />
                  Show Overlay
                </label>
                <label className="flex items-center gap-1 text-gray-400 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={showLabels}
                    onChange={(e) => setShowLabels(e.target.checked)}
                    className="rounded border-gray-600 bg-gray-700"
                  />
                  Show Labels
                </label>
                <span className="text-gray-500">
                  {overlayDetections.length} detection{overlayDetections.length !== 1 ? 's' : ''}
                </span>
              </div>
            )}

            {webcamStream && (
              <p className="mt-2 text-xs text-green-400 text-center">
                Local camera active - capturing every {pollingInterval}ms
              </p>
            )}
            {!webcamStream && !isYouTubeUrl(activeSession.youtube_url) && latestFrameUrl && (
              <p className="mt-2 text-xs text-green-400 text-center">
                Live preview from server capture (updates ~2x/sec)
              </p>
            )}

            {captureMode === 'manual' && (
              <button
                onClick={captureFrame}
                className="mt-4 w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-4 rounded"
              >
                Capture Frame Now
              </button>
            )}

            <div className="mt-4 space-y-3">
              {/* Session Stats */}
              <div className="bg-gray-700 rounded p-3">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="text-sm font-semibold text-white">Session Stats</h3>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${
                    activeSession.status === 'active' ? 'bg-green-900 text-green-400' : 
                    activeSession.status === 'error' ? 'bg-red-900 text-red-400' : 'bg-gray-600 text-gray-300'
                  }`}>
                    {activeSession.status}
                  </span>
                </div>
                
                {activeSession.error_message && (
                  <div className="mb-3 p-2 bg-red-900/30 border border-red-800 rounded text-xs text-red-400">
                    <strong>Error:</strong> {activeSession.error_message}
                  </div>
                )}

                <div className="grid grid-cols-2 gap-2 text-sm text-gray-300">
                  <div>
                    <span className="text-gray-400">Frames:</span>
                    <span className="ml-2 font-bold text-white">{activeSession.total_frames_captured}</span>
                  </div>
                  <div>
                    <span className="text-gray-400">Detections:</span>
                    <span className="ml-2 font-bold text-white">{activeSession.total_detections}</span>
                  </div>
                </div>
                {webcamStream && (
                  <p className="mt-2 text-xs text-green-400">
                    📷 Local camera capture active
                  </p>
                )}
                {!webcamStream && (activeSession.capture_mode === 'polling' || activeSession.capture_mode === 'motion') && (
                  <p className="mt-2 text-xs text-blue-400">
                    🎥 Server-side {activeSession.capture_mode} active
                  </p>
                )}
                {!webcamStream && activeSession.total_frames_captured === 0 && activeSession.status === 'active' && (
                  <p className="mt-2 text-xs text-yellow-500 animate-pulse">
                    ⏳ Waiting for first frame from server...
                  </p>
                )}
              </div>

              {/* Total Detection Counts by Class */}
              {Object.keys(totalCounts).length > 0 && (
                <div className="bg-gray-700 rounded p-3">
                  <h3 className="text-sm font-semibold text-white mb-2">Total Detections by Class</h3>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    {Object.entries(totalCounts)
                      .sort((a, b) => b[1] - a[1])
                      .map(([label, count]) => (
                        <div key={label} className="flex justify-between items-center">
                          <span className="text-gray-300 capitalize">{label}:</span>
                          <span className="font-bold text-blue-400">{count}</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}

              {/* Latest Frame Detection Counts */}
              {Object.keys(latestFrameCounts).length > 0 && (
                <div className="bg-gray-700 rounded p-3">
                  <h3 className="text-sm font-semibold text-white mb-2">
                    Current Frame #{latestFrame}
                  </h3>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    {Object.entries(latestFrameCounts)
                      .sort((a, b) => b[1] - a[1])
                      .map(([label, count]) => (
                        <div key={label} className="flex justify-between items-center">
                          <span className="text-gray-300 capitalize">{label}:</span>
                          <span className="font-bold text-green-400">{count}</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>

            <canvas ref={canvasRef} style={{ display: 'none' }} />
          </div>

          {/* Results Feed */}
          <div className="bg-gray-800 rounded-lg p-6">
            <h2 className="text-xl font-bold text-white mb-4">Detection Results</h2>
            <div className="space-y-2 max-h-[600px] overflow-y-auto">
              {results.map((result) => (
                <div
                  key={result.id}
                  className="bg-gray-700 rounded-lg p-3 border-l-4 border-blue-500"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="text-white font-bold">{result.result_label}</p>
                      <p className="text-xs text-gray-400">
                        Frame #{result.frame_number} •{' '}
                        {detectors.find((d) => d.id === result.detector_id)?.name}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-bold text-blue-400">
                        {(result.confidence * 100).toFixed(1)}%
                      </p>
                      <p className="text-xs text-gray-500">
                        {new Date(result.created_at + (result.created_at.endsWith('Z') ? '' : 'Z')).toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
              {results.length === 0 && (
                <p className="text-center text-gray-500 py-10">
                  No results yet. Waiting for detections...
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DemoStreamPage;
