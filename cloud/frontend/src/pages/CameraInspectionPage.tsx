import React, { useEffect, useState } from 'react';
import axios from 'axios';

interface CameraSummary {
  total: number;
  healthy: number;
  warning: number;
  failed: number;
}

interface CameraHealth {
  status: string;
  fps: number;
  expected_fps: number;
  resolution: string;
  last_frame_at: string;
  uptime_24h: number;
  latency_ms: number;
  view_similarity_score?: number;
  view_change_detected: boolean;
  avg_brightness?: number;
  sharpness_score?: number;
}

interface CameraAlert {
  id: string;
  alert_type: string;
  severity: string;
  message: string;
  created_at: string;
  muted_until?: string;
  acknowledged: boolean;
}

interface CameraWithHealth {
  id: string;
  name: string;
  url: string;
  hub_id: string;
  current_status: string;
  health_score?: number;
  baseline_image_path?: string;
  view_change_detected: boolean;
}

interface CameraData {
  camera: CameraWithHealth;
  hub_name: string;
  health: CameraHealth | null;
  alerts: CameraAlert[];
}

interface InspectionConfig {
  id: string;
  inspection_interval_minutes: number;
  offline_threshold_minutes: number;
  fps_drop_threshold_pct: number;
  latency_threshold_ms: number;
  view_change_threshold: number;
  alert_emails: string[];
  dashboard_retention_days: number;
  database_retention_days: number;
}

interface InspectionRun {
  id: string;
  started_at: string;
  completed_at?: string;
  status: string;
  total_cameras: number;
  cameras_inspected: number;
  cameras_healthy: number;
  cameras_warning: number;
  cameras_failed: number;
}

const CameraInspectionPage: React.FC = () => {
  const [summary, setSummary] = useState<CameraSummary>({
    total: 0,
    healthy: 0,
    warning: 0,
    failed: 0
  });
  const [cameras, setCameras] = useState<CameraData[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterHub, setFilterHub] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [config, setConfig] = useState<InspectionConfig | null>(null);
  const [recentRuns, setRecentRuns] = useState<InspectionRun[]>([]);
  const [savingConfig, setSavingConfig] = useState(false);
  const [showAddCamera, setShowAddCamera] = useState(false);
  const [hubs, setHubs] = useState<{ id: string; name: string }[]>([]);
  const [newCamera, setNewCamera] = useState({ name: '', url: '', hubId: '' });
  const [savingCamera, setSavingCamera] = useState(false);
  const [addCameraError, setAddCameraError] = useState<string | null>(null);
  const [testingConnection, setTestingConnection] = useState(false);
  const [previewFrame, setPreviewFrame] = useState<string | null>(null); // data:image/jpeg;base64,...
  const [testError, setTestError] = useState<string | null>(null);
  const [setBaselineOnAdd, setSetBaselineOnAdd] = useState(true);

  // NVR scan state
  const [showNvrScan, setShowNvrScan] = useState(false);
  const [nvrForm, setNvrForm] = useState({ host: '', port: '10554', username: '', password: '', hubId: '' });
  const [scanningNvr, setScanningNvr] = useState(false);
  const [nvrScanError, setNvrScanError] = useState<string | null>(null);
  interface NvrDiscoveredChannel { channel_id: number; url: string; frame_base64: string; name: string; selected: boolean; }
  const [nvrChannels, setNvrChannels] = useState<NvrDiscoveredChannel[]>([]);
  const [addingNvrCameras, setAddingNvrCameras] = useState(false);

  const fetchHubs = async () => {
    try {
      const res = await axios.get('/hubs');
      const list = (res.data || []).map((h: { id: string; name: string }) => ({ id: h.id, name: h.name }));
      setHubs(list);
      if (list.length > 0 && !newCamera.hubId) {
        setNewCamera(prev => ({ ...prev, hubId: list[0].id }));
      }
    } catch (err) {
      console.error('Failed to fetch hubs:', err);
    }
  };

  // Strip credentials from a stream URL for display.
  // rtsp://user:pass@host:port/path  ->  rtsp://host:port/path
  // Falls back to a generic placeholder if the URL is unparseable.
  const maskStreamUrl = (url: string): string => {
    if (!url) return '';
    try {
      const u = new URL(url);
      if (u.username || u.password) {
        u.username = '';
        u.password = '';
        return u.toString();
      }
      return url;
    } catch {
      // URL constructor fails on some valid RTSP URLs — fall back to regex.
      return url.replace(/^([a-z]+:\/\/)[^@/]+@/i, '$1');
    }
  };

  const detectStreamType = (url: string): string => {
    if (!url) return '';
    const u = url.trim().toLowerCase();
    if (u.startsWith('rtsp://')) return 'RTSP';
    if (u.startsWith('rtmp://')) return 'RTMP';
    if (u.includes('youtube.com') || u.includes('youtu.be')) return 'YouTube';
    if (u.match(/\.(mp4|webm|mov|avi|mkv)(\?|$)/)) return 'Video file';
    if (u.match(/\.(m3u8)(\?|$)/)) return 'HLS';
    if (u.includes('mjpg') || u.includes('mjpeg')) return 'MJPEG';
    if (u.startsWith('http://') || u.startsWith('https://')) return 'HTTP stream';
    return '';
  };

  const handleTestConnection = async () => {
    setTestError(null);
    setPreviewFrame(null);
    if (!newCamera.url.trim()) {
      setTestError('Enter a URL first.');
      return;
    }
    try {
      setTestingConnection(true);
      const res = await axios.post('/camera-inspection/cameras/test-url', {
        url: newCamera.url.trim(),
      });
      if (res.data?.ok && res.data?.frame_base64) {
        setPreviewFrame(`data:image/jpeg;base64,${res.data.frame_base64}`);
      } else {
        setTestError(res.data?.error || 'Could not capture a frame.');
      }
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string; message?: string } } };
      setTestError(
        e.response?.data?.detail || e.response?.data?.message || 'Test failed. Check that the backend is reachable.',
      );
    } finally {
      setTestingConnection(false);
    }
  };

  const resetAddCameraForm = () => {
    setShowAddCamera(false);
    setNewCamera({ name: '', url: '', hubId: newCamera.hubId });
    setPreviewFrame(null);
    setTestError(null);
    setAddCameraError(null);
  };

  const handleAddCamera = async () => {
    setAddCameraError(null);
    if (!newCamera.hubId) {
      setAddCameraError('Pick a hub.');
      return;
    }
    if (!newCamera.name.trim()) {
      setAddCameraError('Camera name is required.');
      return;
    }
    if (!newCamera.url.trim()) {
      setAddCameraError('Stream URL is required.');
      return;
    }
    try {
      setSavingCamera(true);
      const res = await axios.post(`/hubs/${newCamera.hubId}/cameras`, {
        name: newCamera.name.trim(),
        url: newCamera.url.trim(),
      });
      const newCameraId: string | undefined = res.data?.id;

      // Auto-set baseline immediately so view-drift detection has a reference frame.
      // Non-fatal: if it fails (e.g. transient stream hiccup) the user can still
      // hit "Update Baseline" later from the camera card.
      if (setBaselineOnAdd && newCameraId) {
        try {
          await axios.post(`/camera-inspection/cameras/${newCameraId}/update-baseline`);
        } catch (e) {
          console.warn('Baseline capture failed (non-fatal):', e);
        }
      }

      resetAddCameraForm();
      fetchDashboard();
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string; message?: string } } };
      setAddCameraError(
        e.response?.data?.detail || e.response?.data?.message || 'Failed to add camera.',
      );
    } finally {
      setSavingCamera(false);
    }
  };

  const handleNvrScan = async () => {
    setNvrScanError(null);
    setNvrChannels([]);
    if (!nvrForm.host.trim()) { setNvrScanError('Host is required.'); return; }
    if (!nvrForm.username.trim()) { setNvrScanError('Username is required.'); return; }
    try {
      setScanningNvr(true);
      const res = await axios.post('/camera-inspection/nvr/scan', {
        host: nvrForm.host.trim(),
        port: parseInt(nvrForm.port) || 10554,
        username: nvrForm.username.trim(),
        password: nvrForm.password,
      });
      const channels: NvrDiscoveredChannel[] = (res.data?.channels || []).map(
        (ch: { channel_id: number; url: string; frame_base64: string }) => ({
          ...ch,
          name: '',
          selected: true,
        })
      );
      setNvrChannels(channels);
      if (channels.length === 0) setNvrScanError('No active streams found on that NVR.');
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setNvrScanError(e.response?.data?.detail || 'Scan failed.');
    } finally {
      setScanningNvr(false);
    }
  };

  const handleAddNvrCameras = async () => {
    const toAdd = nvrChannels.filter((ch) => ch.selected && ch.name.trim());
    if (!nvrForm.hubId) { setNvrScanError('Select a hub first.'); return; }
    if (toAdd.length === 0) { setNvrScanError('Name at least one camera to add.'); return; }
    try {
      setAddingNvrCameras(true);
      for (const ch of toAdd) {
        await axios.post(`/hubs/${nvrForm.hubId}/cameras`, { name: ch.name.trim(), url: ch.url });
      }
      setShowNvrScan(false);
      setNvrChannels([]);
      setNvrForm({ host: '', port: '10554', username: '', password: '', hubId: '' });
      fetchDashboard();
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } };
      setNvrScanError(e.response?.data?.detail || 'Failed to add cameras.');
    } finally {
      setAddingNvrCameras(false);
    }
  };

  const fetchDashboard = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (filterHub) params.append('hub_id', filterHub);
      if (filterStatus) params.append('status_filter', filterStatus);

      const res = await axios.get(`/camera-inspection/dashboard?${params.toString()}`);
      setSummary(res.data.summary);
      setCameras(res.data.cameras);
    } catch (err) {
      console.error('Failed to fetch camera inspection data:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchConfig = async () => {
    try {
      const res = await axios.get('/inspection-config/');
      setConfig(res.data);
    } catch (err) {
      console.error('Failed to fetch inspection config:', err);
    }
  };

  const fetchRecentRuns = async () => {
    try {
      const res = await axios.get('/camera-inspection/runs?limit=5');
      setRecentRuns(res.data);
    } catch (err) {
      console.error('Failed to fetch recent runs:', err);
    }
  };

  const saveConfig = async () => {
    if (!config) return;
    try {
      setSavingConfig(true);
      await axios.put('/inspection-config/', config);
      alert('Configuration saved successfully');
    } catch (err) {
      console.error('Failed to save config:', err);
      alert('Failed to save configuration');
    } finally {
      setSavingConfig(false);
    }
  };

  const triggerManualInspection = async () => {
    try {
      await axios.post('/camera-inspection/runs');
      alert('Manual inspection triggered. This will run in the background.');
      fetchRecentRuns();
    } catch (err) {
      console.error('Failed to trigger inspection:', err);
      alert('Failed to trigger manual inspection');
    }
  };

  const stopInspectionRun = async (runId: string) => {
    try {
      await axios.post(`/camera-inspection/runs/${runId}/stop`);
      fetchRecentRuns();
    } catch (err: any) {
      console.error('Failed to stop inspection run:', err);
      alert(err.response?.data?.detail || 'Failed to stop inspection run');
    }
  };

  const deleteInspectionRun = async (runId: string) => {
    if (!window.confirm('Are you sure you want to delete this inspection run?')) return;
    try {
      await axios.delete(`/camera-inspection/runs/${runId}`);
      fetchRecentRuns();
    } catch (err) {
      console.error('Failed to delete inspection run:', err);
      alert('Failed to delete inspection run');
    }
  };

  useEffect(() => {
    fetchDashboard();
    fetchConfig();
    fetchRecentRuns();
    fetchHubs();
    // No auto-refresh - dashboard updates on login/manual refresh only
  }, [filterHub, filterStatus]);

  const handleMuteAlerts = async (cameraId: string, days: number) => {
    try {
      await axios.post(`/camera-inspection/cameras/${cameraId}/mute-alerts`, { mute_days: days });
      fetchDashboard();
    } catch (err) {
      console.error('Failed to mute alerts:', err);
    }
  };

  const handleAcknowledgeAlert = async (cameraId: string, alertId: string) => {
    try {
      await axios.post(`/camera-inspection/cameras/${cameraId}/acknowledge-alert/${alertId}`);
      fetchDashboard();
    } catch (err) {
      console.error('Failed to acknowledge alert:', err);
    }
  };

  const handleUpdateBaseline = async (cameraId: string) => {
    try {
      await axios.post(`/camera-inspection/cameras/${cameraId}/update-baseline`);
      alert('Baseline image update initiated');
      fetchDashboard();
    } catch (err) {
      console.error('Failed to update baseline:', err);
    }
  };

  const getStatusBadge = (status: string) => {
    const badges: Record<string, string> = {
      connected: '🟢 Healthy',
      degraded: '🟡 Warning',
      offline: '🔴 Offline',
      unknown: '⚪ Unknown'
    };
    const colors: Record<string, string> = {
      connected: 'bg-green-900 text-green-300',
      degraded: 'bg-yellow-900 text-yellow-300',
      offline: 'bg-red-900 text-red-300',
      unknown: 'bg-brand-bg2 text-gray-400'
    };

    return (
      <span className={`px-3 py-1 rounded-full text-xs font-bold ${colors[status] || 'bg-brand-bg2'}`}>
        {badges[status] || status}
      </span>
    );
  };

  // Filter cameras by search query
  const filteredCameras = cameras.filter(c =>
    c.camera.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.hub_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Group cameras by hub
  const groupedByHub = filteredCameras.reduce((acc, cam) => {
    const hubName = cam.hub_name;
    if (!acc[hubName]) acc[hubName] = [];
    acc[hubName].push(cam);
    return acc;
  }, {} as Record<string, CameraData[]>);

  return (
    <div className="p-8 bg-brand-bg min-h-screen">
      <div className="flex justify-between items-center mb-8">
        <h1 className="font-display uppercase tracking-ioWide text-3xl font-bold text-white">
          Camera <span className="text-brand-primary">Health</span>
        </h1>
        <div className="flex gap-3">
          <button
            onClick={() => {
              setNvrScanError(null);
              setNvrChannels([]);
              if (hubs.length > 0) setNvrForm(prev => ({ ...prev, hubId: hubs[0].id }));
              setShowNvrScan(true);
            }}
            className="bg-brand-primary hover:bg-brand-primaryH text-black font-display uppercase tracking-ioWide text-xs font-bold px-5 py-2.5 transition-colors"
          >
            🔍 Scan NVR
          </button>
          <button
            onClick={() => {
              setAddCameraError(null);
              setShowAddCamera(true);
            }}
            className="bg-brand-primary hover:bg-brand-primaryH text-black font-display uppercase tracking-ioWide text-xs font-bold px-5 py-2.5 transition-colors"
          >
            + Add Camera
          </button>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="border border-brand-line hover:border-brand-primary text-brand-sage hover:text-white font-display uppercase tracking-ioWide text-xs font-bold px-5 py-2.5 transition-colors"
          >
            {showSettings ? '✕ Close' : '⚙ Settings'}
          </button>
          <button
            onClick={fetchDashboard}
            className="border border-brand-line hover:border-brand-primary text-brand-sage hover:text-white font-display uppercase tracking-ioWide text-xs font-bold px-5 py-2.5 transition-colors"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Scan NVR Modal */}
      {showNvrScan && (
        <div
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
          onClick={() => !scanningNvr && !addingNvrCameras && setShowNvrScan(false)}
        >
          <div
            className="bg-brand-bg2 rounded-lg p-6 w-full max-w-4xl border border-brand-line max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="font-display uppercase tracking-ioWide text-2xl font-bold text-white mb-1">
              Scan <span className="text-brand-primary">NVR</span>
            </h2>
            <p className="text-sm text-gray-400 mb-6">
              Probe a Hikvision-style NVR for active RTSP channels. Name the cameras you want to register.
            </p>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Hub</label>
                <select
                  value={nvrForm.hubId}
                  onChange={(e) => setNvrForm({ ...nvrForm, hubId: e.target.value })}
                  disabled={scanningNvr || addingNvrCameras}
                  className="w-full bg-brand-bg2 text-white px-3 py-2 rounded border border-brand-line focus:border-purple-500 outline-none"
                >
                  {hubs.length === 0 ? (
                    <option value="">No hubs available</option>
                  ) : (
                    hubs.map((h) => (
                      <option key={h.id} value={h.id}>{h.name}</option>
                    ))
                  )}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">NVR Host / IP</label>
                <input
                  type="text"
                  value={nvrForm.host}
                  onChange={(e) => setNvrForm({ ...nvrForm, host: e.target.value })}
                  disabled={scanningNvr || addingNvrCameras}
                  placeholder="e.g. 10.17.0.202"
                  className="w-full bg-brand-bg2 text-white px-3 py-2 rounded border border-brand-line focus:border-purple-500 outline-none font-mono text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Port</label>
                <input
                  type="number"
                  value={nvrForm.port}
                  onChange={(e) => setNvrForm({ ...nvrForm, port: e.target.value })}
                  disabled={scanningNvr || addingNvrCameras}
                  className="w-full bg-brand-bg2 text-white px-3 py-2 rounded border border-brand-line focus:border-purple-500 outline-none font-mono text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Username</label>
                <input
                  type="text"
                  value={nvrForm.username}
                  onChange={(e) => setNvrForm({ ...nvrForm, username: e.target.value })}
                  disabled={scanningNvr || addingNvrCameras}
                  autoComplete="off"
                  className="w-full bg-brand-bg2 text-white px-3 py-2 rounded border border-brand-line focus:border-purple-500 outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">Password</label>
                <input
                  type="password"
                  value={nvrForm.password}
                  onChange={(e) => setNvrForm({ ...nvrForm, password: e.target.value })}
                  disabled={scanningNvr || addingNvrCameras}
                  autoComplete="off"
                  className="w-full bg-brand-bg2 text-white px-3 py-2 rounded border border-brand-line focus:border-purple-500 outline-none"
                />
              </div>
            </div>

            <button
              onClick={handleNvrScan}
              disabled={scanningNvr || addingNvrCameras}
              className="bg-brand-primary hover:bg-brand-primaryH text-black font-display uppercase tracking-ioWide text-xs font-bold px-6 py-2.5 transition-colors disabled:opacity-50 mb-4"
            >
              {scanningNvr ? 'Scanning…' : '🔍 Scan'}
            </button>

            {nvrScanError && (
              <div className="bg-yellow-900/40 border border-yellow-700 rounded p-3 text-yellow-300 text-sm mb-4">
                {nvrScanError}
              </div>
            )}

            {nvrChannels.length > 0 && (
              <>
                <p className="text-green-400 text-sm font-medium mb-3">
                  {nvrChannels.length} active channel{nvrChannels.length !== 1 ? 's' : ''} found — name the ones you want to add.
                </p>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
                  {nvrChannels.map((ch, idx) => (
                    <div
                      key={ch.channel_id}
                      className={`bg-brand-bg rounded-lg border p-3 transition ${ch.selected ? 'border-purple-500' : 'border-brand-line opacity-50'}`}
                    >
                      <div className="relative mb-2">
                        <img
                          src={`data:image/jpeg;base64,${ch.frame_base64}`}
                          alt={`Channel ${ch.channel_id}`}
                          className="w-full rounded"
                        />
                        <span className="absolute top-1 left-1 bg-black/70 text-gray-300 text-xs font-mono px-1 rounded">
                          ch{ch.channel_id}
                        </span>
                        <input
                          type="checkbox"
                          checked={ch.selected}
                          onChange={(e) => {
                            const updated = [...nvrChannels];
                            updated[idx] = { ...ch, selected: e.target.checked };
                            setNvrChannels(updated);
                          }}
                          className="absolute top-1 right-1 w-4 h-4"
                        />
                      </div>
                      <input
                        type="text"
                        value={ch.name}
                        onChange={(e) => {
                          const updated = [...nvrChannels];
                          updated[idx] = { ...ch, name: e.target.value, selected: e.target.value.trim().length > 0 || ch.selected };
                          setNvrChannels(updated);
                        }}
                        placeholder="Camera name…"
                        disabled={addingNvrCameras}
                        className="w-full bg-brand-bg2 text-white px-2 py-1 rounded border border-brand-line focus:border-purple-500 outline-none text-sm"
                      />
                    </div>
                  ))}
                </div>
              </>
            )}

            <div className="flex justify-end gap-3">
              <button
                onClick={() => { setShowNvrScan(false); setNvrChannels([]); }}
                disabled={scanningNvr || addingNvrCameras}
                className="bg-brand-bg2 hover:bg-gray-600 text-white px-4 py-2 rounded transition disabled:opacity-50"
              >
                Cancel
              </button>
              {nvrChannels.length > 0 && (
                <button
                  onClick={handleAddNvrCameras}
                  disabled={addingNvrCameras || !nvrChannels.some((ch) => ch.selected && ch.name.trim())}
                  className="bg-brand-primary hover:bg-brand-primaryH text-black font-display uppercase tracking-ioWide text-xs font-bold px-6 py-2.5 transition-colors disabled:opacity-50"
                >
                  {addingNvrCameras
                    ? 'Adding…'
                    : `Add ${nvrChannels.filter((ch) => ch.selected && ch.name.trim()).length} Camera${nvrChannels.filter((ch) => ch.selected && ch.name.trim()).length !== 1 ? 's' : ''}`}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Add Camera Modal */}
      {showAddCamera && (
        <div
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
          onClick={() => !savingCamera && !testingConnection && resetAddCameraForm()}
        >
          <div
            className="bg-brand-bg2 rounded-lg p-6 max-w-lg w-full border border-brand-line max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="font-display uppercase tracking-ioWide text-2xl font-bold text-white mb-4">
              Add <span className="text-brand-primary">Camera</span>
            </h2>
            <p className="text-sm text-gray-400 mb-6">
              Register any IP camera or video stream. Supports RTSP, HTTP/MJPEG, HLS, RTMP, video files, and YouTube.
            </p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Hub</label>
                <select
                  value={newCamera.hubId}
                  onChange={(e) => setNewCamera({ ...newCamera, hubId: e.target.value })}
                  disabled={savingCamera}
                  className="w-full bg-brand-bg2 text-white px-3 py-2 rounded border border-brand-line focus:border-brand-primary outline-none"
                >
                  {hubs.length === 0 ? (
                    <option value="">No hubs available</option>
                  ) : (
                    hubs.map((h) => (
                      <option key={h.id} value={h.id}>
                        {h.name}
                      </option>
                    ))
                  )}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Camera Name</label>
                <input
                  type="text"
                  value={newCamera.name}
                  onChange={(e) => setNewCamera({ ...newCamera, name: e.target.value })}
                  disabled={savingCamera}
                  placeholder="e.g., Front Gate, Loading Dock 3, Lobby Cam"
                  className="w-full bg-brand-bg2 text-white px-3 py-2 rounded border border-brand-line focus:border-brand-primary outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Stream URL</label>
                <input
                  type="text"
                  value={newCamera.url}
                  onChange={(e) => {
                    setNewCamera({ ...newCamera, url: e.target.value });
                    if (previewFrame) setPreviewFrame(null);
                    if (testError) setTestError(null);
                  }}
                  disabled={savingCamera}
                  placeholder="rtsp://user:pass@host:port/path  or  https://...m3u8  or  http://...mjpg"
                  className="w-full bg-brand-bg2 text-white px-3 py-2 rounded border border-brand-line focus:border-brand-primary outline-none font-mono text-sm"
                />
                {newCamera.url && (
                  <p className="text-xs text-gray-500 mt-2">
                    Detected: <span className="text-blue-400 font-mono">{detectStreamType(newCamera.url) || 'unknown'}</span>
                  </p>
                )}
                <p className="text-xs text-gray-500 mt-2">
                  Credentials embedded in the URL are stored as part of the camera record. Do not paste shared
                  credentials into demo accounts.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleTestConnection}
                  disabled={testingConnection || savingCamera || !newCamera.url.trim()}
                  className="bg-brand-primary hover:bg-brand-primaryH text-black font-display uppercase tracking-ioWide text-xs font-bold px-5 py-2.5 transition-colors disabled:opacity-50"
                >
                  {testingConnection ? 'Connecting…' : '📷 Test Connection'}
                </button>
                <span className="text-xs text-gray-500">
                  Pulls one frame from the URL. Verifies credentials and reachability.
                </span>
              </div>

              {testError && (
                <div className="bg-yellow-900/40 border border-yellow-700 rounded p-3 text-yellow-300 text-sm">
                  {testError}
                </div>
              )}

              {previewFrame && (
                <div className="bg-brand-bg border border-brand-line rounded p-3">
                  <p className="text-green-400 text-xs font-medium mb-2">✓ Connected — frame captured</p>
                  <img
                    src={previewFrame}
                    alt="Camera preview"
                    className="w-full rounded border border-brand-line"
                  />
                </div>
              )}

              <div>
                <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={setBaselineOnAdd}
                    onChange={(e) => setSetBaselineOnAdd(e.target.checked)}
                    disabled={savingCamera}
                    className="w-4 h-4"
                  />
                  Capture a baseline frame on add (enables view-drift detection)
                </label>
              </div>

              {addCameraError && (
                <div className="bg-red-900/40 border border-red-700 rounded p-3 text-red-300 text-sm">
                  {addCameraError}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={resetAddCameraForm}
                disabled={savingCamera}
                className="bg-brand-bg2 hover:bg-gray-600 text-white px-4 py-2 rounded transition disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleAddCamera}
                disabled={savingCamera || hubs.length === 0}
                className="bg-brand-primary hover:bg-brand-primaryH text-black font-display uppercase tracking-ioWide text-xs font-bold px-6 py-2.5 transition-colors disabled:opacity-50"
              >
                {savingCamera ? 'Adding…' : '+ Add Camera'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Settings Panel */}
      {showSettings && config && (
        <div className="bg-brand-bg2 rounded-lg p-6 mb-8 border border-brand-line">
          <h2 className="font-display uppercase tracking-ioWide text-2xl font-bold text-white mb-6">
            Inspection <span className="text-brand-primary">Configuration</span>
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            {/* Left Column */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Inspection Interval
                </label>
                <select
                  value={config.inspection_interval_minutes}
                  onChange={(e) => setConfig({...config, inspection_interval_minutes: parseInt(e.target.value)})}
                  className="w-full bg-brand-bg2 text-white px-4 py-2 rounded border border-brand-line"
                >
                  <option value={30}>30 minutes</option>
                  <option value={60}>1 hour (Recommended)</option>
                  <option value={120}>2 hours</option>
                  <option value={180}>3 hours</option>
                  <option value={240}>4 hours</option>
                  <option value={360}>6 hours</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Offline Threshold (minutes)
                </label>
                <input
                  type="number"
                  value={config.offline_threshold_minutes}
                  onChange={(e) => setConfig({...config, offline_threshold_minutes: parseInt(e.target.value)})}
                  className="w-full bg-brand-bg2 text-white px-4 py-2 rounded border border-brand-line"
                  min={1}
                  max={60}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  FPS Drop Threshold (%)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={config.fps_drop_threshold_pct * 100}
                  onChange={(e) => setConfig({...config, fps_drop_threshold_pct: parseFloat(e.target.value) / 100})}
                  className="w-full bg-brand-bg2 text-white px-4 py-2 rounded border border-brand-line"
                  min={0}
                  max={100}
                />
                <p className="text-xs text-gray-500 mt-1">Alert if FPS drops below this % of expected</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Latency Threshold (ms)
                </label>
                <input
                  type="number"
                  value={config.latency_threshold_ms}
                  onChange={(e) => setConfig({...config, latency_threshold_ms: parseInt(e.target.value)})}
                  className="w-full bg-brand-bg2 text-white px-4 py-2 rounded border border-brand-line"
                  min={100}
                  max={5000}
                />
              </div>
            </div>

            {/* Right Column */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  View Change Threshold
                </label>
                <input
                  type="number"
                  step="0.05"
                  value={config.view_change_threshold}
                  onChange={(e) => setConfig({...config, view_change_threshold: parseFloat(e.target.value)})}
                  className="w-full bg-brand-bg2 text-white px-4 py-2 rounded border border-brand-line"
                  min={0}
                  max={1}
                />
                <p className="text-xs text-gray-500 mt-1">Lower = more sensitive (0.7 recommended)</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Alert Email Recipients (comma-separated)
                </label>
                <input
                  type="text"
                  value={config.alert_emails.join(', ')}
                  onChange={(e) => setConfig({...config, alert_emails: e.target.value.split(',').map(s => s.trim()).filter(s => s)})}
                  className="w-full bg-brand-bg2 text-white px-4 py-2 rounded border border-brand-line"
                  placeholder="admin@example.com, ops@example.com"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Dashboard Retention (days)
                </label>
                <input
                  type="number"
                  value={config.dashboard_retention_days}
                  onChange={(e) => setConfig({...config, dashboard_retention_days: parseInt(e.target.value)})}
                  className="w-full bg-brand-bg2 text-white px-4 py-2 rounded border border-brand-line"
                  min={1}
                  max={90}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">
                  Database Retention (days)
                </label>
                <input
                  type="number"
                  value={config.database_retention_days}
                  onChange={(e) => setConfig({...config, database_retention_days: parseInt(e.target.value)})}
                  className="w-full bg-brand-bg2 text-white px-4 py-2 rounded border border-brand-line"
                  min={1}
                  max={365}
                />
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 mb-6">
            <button
              onClick={saveConfig}
              disabled={savingConfig}
              className="bg-brand-primary hover:bg-brand-primaryH text-black font-display uppercase tracking-ioWide text-xs font-bold px-6 py-2.5 transition-colors disabled:opacity-50"
            >
              {savingConfig ? 'Saving…' : 'Save Configuration'}
            </button>
            <button
              onClick={triggerManualInspection}
              className="bg-orange-600 hover:bg-orange-500 text-white px-6 py-2 rounded font-bold transition"
            >
              🚀 Trigger Manual Inspection
            </button>
          </div>

          {/* Recent Inspection Runs */}
          {recentRuns.length > 0 && (
            <div>
              <h3 className="text-xl font-bold text-white mb-3">Recent Inspection Runs</h3>
              <div className="bg-brand-bg2 rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-brand-bg2">
                    <tr>
                      <th className="text-left font-display uppercase tracking-ioWide text-[11px] font-bold text-brand-sage px-4 py-3">Started</th>
                      <th className="text-left font-display uppercase tracking-ioWide text-[11px] font-bold text-brand-sage px-4 py-3">Status</th>
                      <th className="text-left font-display uppercase tracking-ioWide text-[11px] font-bold text-brand-sage px-4 py-3">Total</th>
                      <th className="text-left font-display uppercase tracking-ioWide text-[11px] font-bold text-brand-sage px-4 py-3">Healthy</th>
                      <th className="text-left font-display uppercase tracking-ioWide text-[11px] font-bold text-brand-sage px-4 py-3">Warning</th>
                      <th className="text-left font-display uppercase tracking-ioWide text-[11px] font-bold text-brand-sage px-4 py-3">Failed</th>
                      <th className="text-left font-display uppercase tracking-ioWide text-[11px] font-bold text-brand-sage px-4 py-3">Duration</th>
                      <th className="text-left font-display uppercase tracking-ioWide text-[11px] font-bold text-brand-sage px-4 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentRuns.map(run => {
                      const duration = run.completed_at
                        ? Math.round((new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000)
                        : null;
                      return (
                        <tr key={run.id} className="border-t border-brand-line">
                          <td className="text-sm text-gray-300 px-4 py-3">
                            {new Date(run.started_at).toLocaleString()}
                          </td>
                          <td className="text-sm px-4 py-3">
                            <span className={`px-2 py-1 rounded text-xs font-bold ${
                              run.status === 'completed' ? 'bg-green-900 text-green-300' :
                              run.status === 'running' ? 'bg-blue-900 text-blue-300' :
                              'bg-red-900 text-red-300'
                            }`}>
                              {run.status}
                            </span>
                          </td>
                          <td className="text-sm text-gray-300 px-4 py-3">{run.total_cameras || 0}</td>
                          <td className="text-sm text-green-400 px-4 py-3">{run.cameras_healthy || 0}</td>
                          <td className="text-sm text-yellow-400 px-4 py-3">{run.cameras_warning || 0}</td>
                          <td className="text-sm text-red-400 px-4 py-3">{run.cameras_failed || 0}</td>
                          <td className="text-sm text-gray-300 px-4 py-3">
                            {duration ? `${duration}s` : '-'}
                          </td>
                          <td className="text-sm px-4 py-3">
                            <div className="flex gap-2">
                              {run.status === 'running' && (
                                <button
                                  onClick={() => stopInspectionRun(run.id)}
                                  className="bg-yellow-600 hover:bg-yellow-500 text-white text-xs px-3 py-1 rounded font-bold transition"
                                >
                                  Stop
                                </button>
                              )}
                              <button
                                onClick={() => deleteInspectionRun(run.id)}
                                className="bg-red-700 hover:bg-red-600 text-white text-xs px-3 py-1 rounded font-bold transition"
                              >
                                Delete
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-brand-bg2 p-6 rounded-lg border border-brand-line">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Total Cameras</h3>
          <div className="text-4xl font-bold text-white">{summary.total}</div>
        </div>
        <div className="bg-brand-bg2 p-6 rounded-lg border border-brand-line">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Healthy</h3>
          <div className="text-4xl font-bold text-green-400">
            {summary.healthy}
            <span className="text-sm text-gray-400 ml-2">
              ({summary.total > 0 ? Math.round((summary.healthy / summary.total) * 100) : 0}%)
            </span>
          </div>
        </div>
        <div className="bg-brand-bg2 p-6 rounded-lg border border-brand-line">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Warning</h3>
          <div className="text-4xl font-bold text-yellow-400">
            {summary.warning}
            <span className="text-sm text-gray-400 ml-2">
              ({summary.total > 0 ? Math.round((summary.warning / summary.total) * 100) : 0}%)
            </span>
          </div>
        </div>
        <div className="bg-brand-bg2 p-6 rounded-lg border border-brand-line">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Offline</h3>
          <div className="text-4xl font-bold text-red-400">
            {summary.failed}
            <span className="text-sm text-gray-400 ml-2">
              ({summary.total > 0 ? Math.round((summary.failed / summary.total) * 100) : 0}%)
            </span>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-brand-bg2 p-4 rounded-lg mb-6 flex gap-4">
        <input
          type="text"
          placeholder="Search cameras..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          className="flex-1 bg-brand-bg2 text-white px-4 py-2 rounded border border-brand-line focus:border-brand-primary outline-none"
        />
        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="bg-brand-bg2 text-white px-4 py-2 rounded border border-brand-line outline-none"
        >
          <option value="">All Statuses</option>
          <option value="connected">Healthy</option>
          <option value="degraded">Warning</option>
          <option value="offline">Offline</option>
        </select>
      </div>

      {/* Camera List */}
      {loading ? (
        <div className="text-center text-gray-400 py-8">Loading...</div>
      ) : filteredCameras.length === 0 ? (
        <div className="text-center text-gray-500 py-8">No cameras found</div>
      ) : (
        <div className="space-y-6">
          {Object.entries(groupedByHub).map(([hubName, hubCameras]) => (
            <div key={hubName} className="bg-brand-bg2 rounded-lg p-6">
              <h2 className="text-xl font-bold text-white mb-4">
                {hubName}
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {hubCameras.map(({ camera, health, alerts }) => (
                  <div
                    key={camera.id}
                    className="bg-brand-bg border border-brand-line rounded p-4 flex flex-col"
                  >
                    {/* Header: name + status pill */}
                    <div className="flex justify-between items-start gap-3 mb-2">
                      <h3 className="font-display uppercase tracking-ioWide text-sm font-bold text-white truncate">
                        {camera.name}
                      </h3>
                      {health && getStatusBadge(health.status)}
                    </div>

                    {/* Masked stream URL — credentials stripped for display */}
                    <p
                      className="text-[11px] font-mono text-gray-500 truncate mb-3"
                      title={maskStreamUrl(camera.url)}
                    >
                      {maskStreamUrl(camera.url)}
                    </p>

                    {/* Compact 2x2 health metrics — only the ones that read at a glance */}
                    {health && (
                      <div className="grid grid-cols-2 gap-x-4 gap-y-2 mb-3 text-sm">
                        <div>
                          <p className="text-[10px] uppercase tracking-ioWide text-brand-textDim">FPS</p>
                          <p className="text-white font-bold">
                            {health.fps?.toFixed(1) || '—'}
                            <span className="text-brand-textDim text-xs">/{health.expected_fps}</span>
                            {health.fps && health.fps < health.expected_fps * 0.5 && (
                              <span className="text-yellow-400 ml-1">⚠</span>
                            )}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] uppercase tracking-ioWide text-brand-textDim">Resolution</p>
                          <p className="text-white font-bold">{health.resolution || '—'}</p>
                        </div>
                        <div>
                          <p className="text-[10px] uppercase tracking-ioWide text-brand-textDim">Latency</p>
                          <p className={`font-bold ${health.latency_ms && config && health.latency_ms > config.latency_threshold_ms ? 'text-yellow-400' : 'text-white'}`}>
                            {health.latency_ms ? `${health.latency_ms} ms` : '—'}
                            {health.latency_ms && config && health.latency_ms > config.latency_threshold_ms && (
                              <span className="ml-1 text-[10px]">⚠</span>
                            )}
                          </p>
                        </div>
                        <div>
                          <p className="text-[10px] uppercase tracking-ioWide text-brand-textDim">Last Frame</p>
                          <p className="text-white font-bold">
                            {health.last_frame_at ? new Date(health.last_frame_at).toLocaleTimeString() : '—'}
                          </p>
                        </div>
                        {health.uptime_24h !== null && health.uptime_24h !== undefined && (
                          <div>
                            <p className="text-[10px] uppercase tracking-ioWide text-brand-textDim">Uptime 24h</p>
                            <p className="text-white font-bold">{health.uptime_24h.toFixed(1)}%</p>
                          </div>
                        )}
                        {health.view_similarity_score !== null && health.view_similarity_score !== undefined && (
                          <div>
                            <p className="text-[10px] uppercase tracking-ioWide text-brand-textDim">View Match</p>
                            <p className="text-white font-bold">
                              {(health.view_similarity_score * 100).toFixed(0)}%
                              {health.view_change_detected && <span className="text-red-400 ml-1">🚨</span>}
                            </p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Alerts — compact, only show count + most recent */}
                    {alerts.length > 0 && (
                      <div className="border border-yellow-700/50 bg-yellow-900/15 px-3 py-2 mb-3 text-xs">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-yellow-300 font-bold uppercase tracking-ioWide text-[10px]">
                            {alerts.length} alert{alerts.length === 1 ? '' : 's'}
                          </span>
                          {alerts[0] && !alerts[0].acknowledged && !alerts[0].muted_until && (
                            <button
                              onClick={() => handleAcknowledgeAlert(camera.id, alerts[0].id)}
                              className="bg-brand-primary hover:bg-brand-primaryH text-black font-display uppercase tracking-ioWide text-[10px] font-bold px-2 py-1"
                            >
                              Ack
                            </button>
                          )}
                        </div>
                        <p className="text-yellow-200 mt-1 truncate" title={alerts[0]?.message}>
                          {alerts[0]?.message}
                        </p>
                      </div>
                    )}

                    {/* Footer actions — pinned to card bottom */}
                    <div className="mt-auto flex gap-2 flex-wrap items-center pt-2 border-t border-brand-line">
                      {health?.view_change_detected && (
                        <button
                          onClick={() => handleUpdateBaseline(camera.id)}
                          className="border border-brand-line hover:border-brand-primary text-brand-sage hover:text-white font-display uppercase tracking-ioWide text-[10px] font-bold px-2.5 py-1 transition-colors"
                        >
                          Update Baseline
                        </button>
                      )}
                      <select
                        onChange={(e) => {
                          if (e.target.value) {
                            handleMuteAlerts(camera.id, parseInt(e.target.value));
                            e.target.value = '';
                          }
                        }}
                        className="bg-brand-bg2 border border-brand-line text-brand-textDim font-display uppercase tracking-ioWide text-[10px] font-bold px-2 py-1 ml-auto"
                      >
                        <option value="">Mute…</option>
                        <option value="1">1 Day</option>
                        <option value="7">7 Days</option>
                        <option value="14">14 Days</option>
                        <option value="30">30 Days</option>
                      </select>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default CameraInspectionPage;
