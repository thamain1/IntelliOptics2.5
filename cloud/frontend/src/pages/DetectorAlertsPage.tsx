import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

interface AlertSummary {
  total: number;
  acknowledged: number;
  unacknowledged: number;
  by_severity: {
    critical: number;
    warning: number;
    info: number;
  };
  by_detector: Record<string, number>;
  period_days: number;
}

interface DetectorAlert {
  id: string;
  detector_id: string;
  query_id: string | null;
  alert_type: string;
  severity: string;
  message: string;
  detection_label: string | null;
  detection_confidence: number | null;
  camera_name: string | null;
  image_blob_path: string | null;
  sent_to: string[];
  email_sent: boolean;
  email_sent_at: string | null;
  acknowledged: boolean;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  created_at: string;
}

const DetectorAlertsPage: React.FC = () => {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<AlertSummary | null>(null);
  const [alerts, setAlerts] = useState<DetectorAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [detectors, setDetectors] = useState<Record<string, any>>({});

  // Filters
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [acknowledgedFilter, setAcknowledgedFilter] = useState<string>('');
  const [daysFilter, setDaysFilter] = useState(7);

  useEffect(() => {
    fetchData();
  }, [severityFilter, acknowledgedFilter, daysFilter]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (severityFilter) params.append('severity', severityFilter);
      if (acknowledgedFilter) params.append('acknowledged', acknowledgedFilter);
      params.append('days', daysFilter.toString());
      params.append('limit', '100');

      const [summaryRes, alertsRes, detectorsRes] = await Promise.all([
        axios.get(`/detectors/alerts/summary?days=${daysFilter}`),
        axios.get(`/detectors/alerts/all?${params.toString()}`),
        axios.get('/detectors')
      ]);

      setSummary(summaryRes.data);
      setAlerts(alertsRes.data);

      // Create detector map for quick lookup
      const detectorMap: Record<string, any> = {};
      detectorsRes.data.forEach((d: any) => {
        detectorMap[d.id] = d;
      });
      setDetectors(detectorMap);
    } catch (err) {
      console.error('Failed to fetch detector alerts:', err);
    } finally {
      setLoading(false);
    }
  };

  const acknowledgeAlert = async (alertId: string) => {
    try {
      await axios.post(`/detectors/alerts/${alertId}/acknowledge`, {});
      fetchData();
    } catch (err) {
      console.error('Failed to acknowledge alert:', err);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-900/20 border-red-700 text-red-300';
      case 'warning':
        return 'bg-yellow-900/20 border-yellow-700 text-yellow-300';
      default:
        return 'bg-blue-900/20 border-blue-700 text-blue-300';
    }
  };

  const getSeverityBadgeColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-900 text-red-300';
      case 'warning':
        return 'bg-yellow-900 text-yellow-300';
      default:
        return 'bg-blue-900 text-blue-300';
    }
  };

  return (
    <div className="p-8 bg-gray-900 min-h-screen">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-white">Detector Alerts</h1>
        <button
          onClick={fetchData}
          className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded font-bold transition"
        >
          Refresh
        </button>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-1 md:grid-cols-5 gap-6 mb-8">
          <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
            <h3 className="text-sm font-medium text-gray-400 mb-2">Total Alerts</h3>
            <div className="text-4xl font-bold text-white">{summary.total}</div>
            <p className="text-xs text-gray-500 mt-1">Last {summary.period_days} days</p>
          </div>
          <div className="bg-gray-800 p-6 rounded-lg border border-gray-700">
            <h3 className="text-sm font-medium text-gray-400 mb-2">Unacknowledged</h3>
            <div className="text-4xl font-bold text-yellow-400">{summary.unacknowledged}</div>
            <p className="text-xs text-gray-500 mt-1">Needs attention</p>
          </div>
          <div className="bg-gray-800 p-6 rounded-lg border border-red-700">
            <h3 className="text-sm font-medium text-gray-400 mb-2">Critical</h3>
            <div className="text-4xl font-bold text-red-400">{summary.by_severity.critical}</div>
          </div>
          <div className="bg-gray-800 p-6 rounded-lg border border-yellow-700">
            <h3 className="text-sm font-medium text-gray-400 mb-2">Warning</h3>
            <div className="text-4xl font-bold text-yellow-400">{summary.by_severity.warning}</div>
          </div>
          <div className="bg-gray-800 p-6 rounded-lg border border-blue-700">
            <h3 className="text-sm font-medium text-gray-400 mb-2">Info</h3>
            <div className="text-4xl font-bold text-blue-400">{summary.by_severity.info}</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-gray-800 p-4 rounded-lg mb-6 flex gap-4">
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
        >
          <option value="">All Severities</option>
          <option value="critical">Critical</option>
          <option value="warning">Warning</option>
          <option value="info">Info</option>
        </select>

        <select
          value={acknowledgedFilter}
          onChange={(e) => setAcknowledgedFilter(e.target.value)}
          className="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
        >
          <option value="">All Alerts</option>
          <option value="false">Unacknowledged Only</option>
          <option value="true">Acknowledged Only</option>
        </select>

        <select
          value={daysFilter}
          onChange={(e) => setDaysFilter(parseInt(e.target.value))}
          className="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
        >
          <option value={1}>Last 24 hours</option>
          <option value={7}>Last 7 days</option>
          <option value={30}>Last 30 days</option>
          <option value={90}>Last 90 days</option>
        </select>
      </div>

      {/* Alerts List */}
      {loading ? (
        <div className="text-center text-gray-400 py-8">Loading alerts...</div>
      ) : alerts.length === 0 ? (
        <div className="text-center text-gray-500 py-8">No alerts found</div>
      ) : (
        <div className="space-y-4">
          {alerts.map((alert) => {
            const detector = detectors[alert.detector_id];
            return (
              <div
                key={alert.id}
                className={`p-6 rounded-lg border ${getSeverityColor(alert.severity)} ${
                  alert.acknowledged ? 'opacity-60' : ''
                }`}
              >
                {/* Header */}
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center gap-3">
                    <span className={`px-3 py-1 rounded text-xs font-bold ${getSeverityBadgeColor(alert.severity)}`}>
                      {alert.severity.toUpperCase()}
                    </span>
                    {alert.acknowledged && (
                      <span className="text-xs text-green-400 font-bold">✓ Acknowledged</span>
                    )}
                  </div>
                  <span className="text-xs text-gray-500">
                    {new Date(alert.created_at).toLocaleString()}
                  </span>
                </div>

                {/* Detector Info */}
                {detector && (
                  <div className="mb-3">
                    <button
                      onClick={() => navigate(`/detectors/${detector.id}/configure`)}
                      className="text-blue-400 hover:text-blue-300 font-bold text-sm hover:underline"
                    >
                      {detector.name}
                    </button>
                  </div>
                )}

                {/* Message */}
                <p className="text-white text-lg mb-3">{alert.message}</p>

                {/* Detection Details */}
                <div className="flex flex-wrap gap-4 text-sm text-gray-400 mb-3">
                  {alert.detection_label && (
                    <span>
                      Label: <strong className="text-white">{alert.detection_label}</strong>
                    </span>
                  )}
                  {alert.detection_confidence && (
                    <span>
                      Confidence:{' '}
                      <strong className="text-white">
                        {(alert.detection_confidence * 100).toFixed(1)}%
                      </strong>
                    </span>
                  )}
                  {alert.camera_name && (
                    <span>
                      Camera: <strong className="text-white">{alert.camera_name}</strong>
                    </span>
                  )}
                  {alert.email_sent && (
                    <span className="text-green-400">
                      ✉️ Email sent to {alert.sent_to.length} recipient(s)
                    </span>
                  )}
                </div>

                {/* Actions */}
                <div className="flex gap-3">
                  {!alert.acknowledged && (
                    <button
                      onClick={() => acknowledgeAlert(alert.id)}
                      className="bg-blue-600 hover:bg-blue-500 text-white text-sm font-bold py-2 px-4 rounded transition"
                    >
                      Acknowledge
                    </button>
                  )}
                  {detector && (
                    <button
                      onClick={() => {
                        navigate(`/detectors/${detector.id}/configure`);
                        // TODO: Switch to alerts tab
                      }}
                      className="bg-gray-700 hover:bg-gray-600 text-white text-sm font-bold py-2 px-4 rounded transition"
                    >
                      Configure Alerts
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default DetectorAlertsPage;
