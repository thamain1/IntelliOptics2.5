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
      await axios.post(`/hubs/${newCamera.hubId}/cameras`, {
        name: newCamera.name.trim(),
        url: newCamera.url.trim(),
      });
      setShowAddCamera(false);
      setNewCamera({ name: '', url: '', hubId: newCamera.hubId });
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
      unknown: 'bg-gray-700 text-gray-400'
    };

    return (
      <span className={`px-3 py-1 rounded-full text-xs font-bold ${colors[status] || 'bg-gray-700'}`}>
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
    <div className="p-8 bg-gray-900 min-h-screen">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-white">Camera Health Inspection</h1>
        <div className="flex gap-3">
          <button
            onClick={() => {
              setAddCameraError(null);
              setShowAddCamera(true);
            }}
            className="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded font-bold transition"
          >
            + Add Camera
          </button>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded font-bold transition"
          >
            {showSettings ? '✕ Close' : '⚙️ Settings'}
          </button>
          <button
            onClick={fetchDashboard}
            className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded font-bold transition"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Add Camera Modal */}
      {showAddCamera && (
        <div
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4"
          onClick={() => !savingCamera && setShowAddCamera(false)}
        >
          <div
            className="bg-gray-800 rounded-lg p-6 max-w-lg w-full border border-gray-700"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-2xl font-bold text-white mb-4">Add Camera</h2>
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
                  className="w-full bg-gray-700 text-white px-3 py-2 rounded border border-gray-600 focus:border-blue-500 outline-none"
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
                  className="w-full bg-gray-700 text-white px-3 py-2 rounded border border-gray-600 focus:border-blue-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Stream URL</label>
                <input
                  type="text"
                  value={newCamera.url}
                  onChange={(e) => setNewCamera({ ...newCamera, url: e.target.value })}
                  disabled={savingCamera}
                  placeholder="rtsp://user:pass@host:port/path  or  https://...m3u8  or  http://...mjpg"
                  className="w-full bg-gray-700 text-white px-3 py-2 rounded border border-gray-600 focus:border-blue-500 outline-none font-mono text-sm"
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

              {addCameraError && (
                <div className="bg-red-900/40 border border-red-700 rounded p-3 text-red-300 text-sm">
                  {addCameraError}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowAddCamera(false)}
                disabled={savingCamera}
                className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded transition disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleAddCamera}
                disabled={savingCamera || hubs.length === 0}
                className="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded font-bold transition disabled:opacity-50"
              >
                {savingCamera ? 'Adding…' : 'Add Camera'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Settings Panel */}
      {showSettings && config && (
        <div className="bg-gray-800 rounded-lg p-6 mb-8 border border-gray-700">
          <h2 className="text-2xl font-bold text-white mb-6">Inspection Configuration</h2>

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
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
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
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
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
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
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
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
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
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
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
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
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
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
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
                  className="w-full bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
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
              className="bg-green-600 hover:bg-green-500 text-white px-6 py-2 rounded font-bold transition disabled:opacity-50"
            >
              {savingConfig ? 'Saving...' : 'Save Configuration'}
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
              <div className="bg-gray-700 rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-800">
                    <tr>
                      <th className="text-left text-xs font-medium text-gray-400 px-4 py-3">Started</th>
                      <th className="text-left text-xs font-medium text-gray-400 px-4 py-3">Status</th>
                      <th className="text-left text-xs font-medium text-gray-400 px-4 py-3">Total</th>
                      <th className="text-left text-xs font-medium text-gray-400 px-4 py-3">Healthy</th>
                      <th className="text-left text-xs font-medium text-gray-400 px-4 py-3">Warning</th>
                      <th className="text-left text-xs font-medium text-gray-400 px-4 py-3">Failed</th>
                      <th className="text-left text-xs font-medium text-gray-400 px-4 py-3">Duration</th>
                      <th className="text-left text-xs font-medium text-gray-400 px-4 py-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentRuns.map(run => {
                      const duration = run.completed_at
                        ? Math.round((new Date(run.completed_at).getTime() - new Date(run.started_at).getTime()) / 1000)
                        : null;
                      return (
                        <tr key={run.id} className="border-t border-gray-600">
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
        <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Total Cameras</h3>
          <div className="text-4xl font-bold text-white">{summary.total}</div>
        </div>
        <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Healthy</h3>
          <div className="text-4xl font-bold text-green-400">
            {summary.healthy}
            <span className="text-sm text-gray-400 ml-2">
              ({summary.total > 0 ? Math.round((summary.healthy / summary.total) * 100) : 0}%)
            </span>
          </div>
        </div>
        <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Warning</h3>
          <div className="text-4xl font-bold text-yellow-400">
            {summary.warning}
            <span className="text-sm text-gray-400 ml-2">
              ({summary.total > 0 ? Math.round((summary.warning / summary.total) * 100) : 0}%)
            </span>
          </div>
        </div>
        <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
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
      <div className="bg-gray-800 p-4 rounded-lg mb-6 flex gap-4">
        <input
          type="text"
          placeholder="Search cameras..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          className="flex-1 bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:border-blue-500 outline-none"
        />
        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 outline-none"
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
            <div key={hubName} className="bg-gray-800 rounded-lg p-6">
              <h2 className="text-xl font-bold text-white mb-4">
                {hubName}
              </h2>

              <div className="space-y-4">
                {hubCameras.map(({ camera, health, alerts }) => (
                  <div key={camera.id} className="bg-gray-700 rounded-lg p-4">
                    {/* Camera Header */}
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <h3 className="text-lg font-bold text-white">{camera.name}</h3>
                        <p className="text-xs text-gray-400 truncate" title={camera.url}>
                          {camera.url}
                        </p>
                      </div>
                      {health && getStatusBadge(health.status)}
                    </div>

                    {/* Health Metrics Grid */}
                    {health && (
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
                        <div>
                          <p className="text-xs text-gray-400">Frame Rate</p>
                          <p className="text-white font-bold">
                            {health.fps?.toFixed(1) || 'N/A'} / {health.expected_fps} FPS
                            {health.fps && health.fps < health.expected_fps * 0.5 && (
                              <span className="text-yellow-400 ml-1">⚠️</span>
                            )}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-400">Resolution</p>
                          <p className="text-white font-bold">{health.resolution || 'N/A'}</p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-400">Last Frame</p>
                          <p className="text-white font-bold">
                            {health.last_frame_at ? new Date(health.last_frame_at).toLocaleTimeString() : 'N/A'}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-400">Uptime (24h)</p>
                          <p className="text-white font-bold">{health.uptime_24h?.toFixed(1) || 'N/A'}%</p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-400">Latency</p>
                          <p className="text-white font-bold">{health.latency_ms || 'N/A'} ms</p>
                        </div>
                        {health.view_similarity_score !== null && health.view_similarity_score !== undefined && (
                          <div>
                            <p className="text-xs text-gray-400">View Similarity</p>
                            <p className="text-white font-bold">
                              {(health.view_similarity_score * 100).toFixed(1)}%
                              {health.view_change_detected && <span className="text-red-400 ml-1">🚨</span>}
                            </p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Alerts */}
                    {alerts.length > 0 && (
                      <div className="bg-gray-800 p-3 rounded mb-4">
                        <h4 className="text-sm font-bold text-white mb-2">Active Alerts</h4>
                        <div className="space-y-2">
                          {alerts.map(alert => (
                            <div key={alert.id} className="flex justify-between items-center bg-gray-700 p-2 rounded">
                              <div>
                                <p className="text-white text-sm">{alert.message}</p>
                                <p className="text-xs text-gray-400">
                                  {new Date(alert.created_at).toLocaleString()}
                                  {alert.muted_until && (
                                    <span className="ml-2 text-yellow-400">
                                      Muted until {new Date(alert.muted_until).toLocaleDateString()}
                                    </span>
                                  )}
                                </p>
                              </div>
                              {!alert.acknowledged && !alert.muted_until && (
                                <button
                                  onClick={() => handleAcknowledgeAlert(camera.id, alert.id)}
                                  className="bg-blue-600 hover:bg-blue-500 text-white text-xs px-3 py-1 rounded"
                                >
                                  Acknowledge
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Action Buttons */}
                    <div className="flex gap-2 flex-wrap">
                      {health?.view_change_detected && (
                        <button
                          onClick={() => handleUpdateBaseline(camera.id)}
                          className="bg-orange-600 hover:bg-orange-500 text-white text-sm px-3 py-1 rounded"
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
                        className="bg-gray-600 text-white text-sm px-3 py-1 rounded"
                      >
                        <option value="">Mute Alerts...</option>
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
