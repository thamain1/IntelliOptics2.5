import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

interface AlertConfig {
  id: string;
  detector_id: string;
  enabled: boolean;
  alert_name: string | null;
  condition_type: string;
  condition_value: string | null;
  consecutive_count: number;
  time_window_minutes: number | null;
  confirm_with_cloud: boolean;
  alert_emails: string[];
  alert_phones: string[];
  include_image_sms: boolean;
  alert_webhooks: string[];
  webhook_template: string | null;
  webhook_headers: Record<string, string> | null;
  severity: string;
  cooldown_minutes: number;
  include_image: boolean;
  custom_message: string | null;
}

interface Detector {
  id: string;
  name: string;
  labels?: string[];
}

const DetectorAlertConfigPage: React.FC = () => {
  const { detectorId } = useParams<{ detectorId: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [detector, setDetector] = useState<Detector | null>(null);
  const [config, setConfig] = useState<AlertConfig | null>(null);

  // Form state
  const [enabled, setEnabled] = useState(false);
  const [alertName, setAlertName] = useState('');
  const [conditionType, setConditionType] = useState('LABEL_MATCH');
  const [conditionValue, setConditionValue] = useState('YES');
  const [consecutiveCount, setConsecutiveCount] = useState(1);
  const [countMode, setCountMode] = useState<'consecutive' | 'time_window'>('consecutive');
  const [timeWindowMinutes, setTimeWindowMinutes] = useState<number | null>(null);
  const [confirmWithCloud, setConfirmWithCloud] = useState(false);

  // Recipients
  const [alertEmails, setAlertEmails] = useState<string[]>([]);
  const [newEmail, setNewEmail] = useState('');
  const [alertPhones, setAlertPhones] = useState<string[]>([]);
  const [newPhone, setNewPhone] = useState('');
  const [includeImageSms, setIncludeImageSms] = useState(true);

  // Webhook
  const [alertWebhooks, setAlertWebhooks] = useState<string[]>([]);
  const [newWebhook, setNewWebhook] = useState('');
  const [webhookTemplate, setWebhookTemplate] = useState('');

  // Settings
  const [severity, setSeverity] = useState('warning');
  const [cooldownMinutes, setCooldownMinutes] = useState(5);
  const [includeImage, setIncludeImage] = useState(true);
  const [customMessage, setCustomMessage] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      if (!detectorId) return;

      try {
        // Fetch detector info
        const detectorRes = await axios.get(`/detectors/${detectorId}`);
        setDetector(detectorRes.data);

        // Fetch alert config
        const configRes = await axios.get(`/detectors/${detectorId}/alert-config`);
        const cfg = configRes.data;
        setConfig(cfg);

        // Populate form
        setEnabled(cfg.enabled);
        setAlertName(cfg.alert_name || `Alert for ${detectorRes.data.name}`);
        setConditionType(cfg.condition_type);
        setConditionValue(cfg.condition_value || 'YES');
        setConsecutiveCount(cfg.consecutive_count || 1);
        setTimeWindowMinutes(cfg.time_window_minutes);
        setCountMode(cfg.time_window_minutes ? 'time_window' : 'consecutive');
        setConfirmWithCloud(cfg.confirm_with_cloud || false);
        setAlertEmails(cfg.alert_emails || []);
        setAlertPhones(cfg.alert_phones || []);
        setIncludeImageSms(cfg.include_image_sms !== false);
        setAlertWebhooks(cfg.alert_webhooks || []);
        setWebhookTemplate(cfg.webhook_template || '{\n  "detector_name": "{{detector_name}}",\n  "detection": "{{detection_label}}",\n  "confidence": "{{confidence}}",\n  "image_url": "{{image_url}}"\n}');
        setSeverity(cfg.severity || 'warning');
        setCooldownMinutes(cfg.cooldown_minutes || 5);
        setIncludeImage(cfg.include_image !== false);
        setCustomMessage(cfg.custom_message || '');
      } catch (err) {
        toast.error('Failed to load alert configuration');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [detectorId]);

  const handleSave = async () => {
    if (!detectorId) return;

    setSaving(true);
    try {
      const payload = {
        enabled,
        alert_name: alertName,
        condition_type: conditionType,
        condition_value: conditionValue,
        consecutive_count: consecutiveCount,
        time_window_minutes: countMode === 'time_window' ? timeWindowMinutes : null,
        confirm_with_cloud: confirmWithCloud,
        alert_emails: alertEmails,
        alert_phones: alertPhones,
        include_image_sms: includeImageSms,
        alert_webhooks: alertWebhooks,
        webhook_template: webhookTemplate || null,
        severity,
        cooldown_minutes: cooldownMinutes,
        include_image: includeImage,
        custom_message: customMessage || null,
      };

      await axios.put(`/detectors/${detectorId}/alert-config`, payload);
      toast.success('Alert configuration saved!');
    } catch (err) {
      toast.error('Failed to save alert configuration');
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const addEmail = () => {
    if (newEmail && !alertEmails.includes(newEmail)) {
      setAlertEmails([...alertEmails, newEmail]);
      setNewEmail('');
    }
  };

  const removeEmail = (email: string) => {
    setAlertEmails(alertEmails.filter((e) => e !== email));
  };

  const addPhone = () => {
    if (newPhone && !alertPhones.includes(newPhone)) {
      setAlertPhones([...alertPhones, newPhone]);
      setNewPhone('');
    }
  };

  const removePhone = (phone: string) => {
    setAlertPhones(alertPhones.filter((p) => p !== phone));
  };

  const addWebhook = () => {
    if (newWebhook && !alertWebhooks.includes(newWebhook)) {
      setAlertWebhooks([...alertWebhooks, newWebhook]);
      setNewWebhook('');
    }
  };

  const removeWebhook = (url: string) => {
    setAlertWebhooks(alertWebhooks.filter((w) => w !== url));
  };

  if (loading) {
    return (
      <div className="p-8 bg-gray-900 text-gray-300 min-h-screen">
        <p>Loading alert configuration...</p>
      </div>
    );
  }

  const labelOptions = detector?.labels || ['YES', 'NO'];

  return (
    <div className="p-8 bg-gray-900 text-gray-300 min-h-screen">
      <ToastContainer position="top-right" autoClose={5000} />

      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate(-1)}
            className="text-gray-400 hover:text-white"
          >
            &larr; Back
          </button>
          <div>
            <h1 className="text-2xl font-bold text-white">Edit Alert</h1>
            <p className="text-gray-400">Configure alert for {detector?.name}</p>
          </div>
        </div>
        <div className="flex items-center space-x-4">
          <span className="text-gray-400">Alert Enabled</span>
          <button
            onClick={() => setEnabled(!enabled)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              enabled ? 'bg-blue-600' : 'bg-gray-600'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                enabled ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Alert Name */}
      <div className="bg-gray-800 rounded-lg p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">Alert Name</label>
            <input
              type="text"
              value={alertName}
              onChange={(e) => setAlertName(e.target.value)}
              className="w-full bg-gray-700 border border-gray-600 rounded px-4 py-2 text-white focus:outline-none focus:border-blue-500"
              placeholder="IntelliOptics Alert"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">Detector</label>
            <input
              type="text"
              value={detector?.name || ''}
              disabled
              className="w-full bg-gray-700 border border-gray-600 rounded px-4 py-2 text-gray-400"
            />
          </div>
        </div>
      </div>

      {/* Trigger Condition - Boolean Logic Builder */}
      <div className="bg-gray-800 rounded-lg p-6 mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">Send alert when detector:</h2>

        <div className="flex flex-wrap items-center gap-4 mb-4">
          {/* Condition Type */}
          <select
            value={conditionType}
            onChange={(e) => setConditionType(e.target.value)}
            className="bg-gray-700 border border-gray-600 rounded px-4 py-2 text-white focus:outline-none focus:border-blue-500"
          >
            <option value="LABEL_MATCH">Gives answer</option>
            <option value="CONFIDENCE_ABOVE">Confidence above</option>
            <option value="CONFIDENCE_BELOW">Confidence below</option>
            <option value="ALWAYS">Always (any result)</option>
          </select>

          {/* Condition Value */}
          {conditionType === 'LABEL_MATCH' && (
            <select
              value={conditionValue}
              onChange={(e) => setConditionValue(e.target.value)}
              className="bg-gray-700 border border-gray-600 rounded px-4 py-2 text-white focus:outline-none focus:border-blue-500 min-w-[120px]"
            >
              {labelOptions.map((label) => (
                <option key={label} value={label}>
                  {label}
                </option>
              ))}
            </select>
          )}

          {(conditionType === 'CONFIDENCE_ABOVE' || conditionType === 'CONFIDENCE_BELOW') && (
            <input
              type="number"
              min="0"
              max="1"
              step="0.05"
              value={conditionValue}
              onChange={(e) => setConditionValue(e.target.value)}
              className="bg-gray-700 border border-gray-600 rounded px-4 py-2 text-white focus:outline-none focus:border-blue-500 w-24"
              placeholder="0.85"
            />
          )}

          {/* For X times */}
          <span className="text-gray-400">For</span>
          <input
            type="number"
            min="1"
            max="100"
            value={consecutiveCount}
            onChange={(e) => setConsecutiveCount(parseInt(e.target.value) || 1)}
            className="bg-gray-700 border border-gray-600 rounded px-4 py-2 text-white focus:outline-none focus:border-blue-500 w-20"
          />

          {/* Count Mode */}
          <select
            value={countMode}
            onChange={(e) => setCountMode(e.target.value as 'consecutive' | 'time_window')}
            className="bg-gray-700 border border-gray-600 rounded px-4 py-2 text-white focus:outline-none focus:border-blue-500"
          >
            <option value="consecutive">Consecutive answer(s)</option>
            <option value="time_window">Times within</option>
          </select>

          {/* Time Window */}
          {countMode === 'time_window' && (
            <>
              <input
                type="number"
                min="1"
                max="1440"
                value={timeWindowMinutes || 5}
                onChange={(e) => setTimeWindowMinutes(parseInt(e.target.value) || 5)}
                className="bg-gray-700 border border-gray-600 rounded px-4 py-2 text-white focus:outline-none focus:border-blue-500 w-20"
              />
              <span className="text-gray-400">minutes</span>
            </>
          )}
        </div>

        {/* Confirm with cloud */}
        <label className="flex items-center space-x-2 text-gray-300 cursor-pointer">
          <input
            type="checkbox"
            checked={confirmWithCloud}
            onChange={(e) => setConfirmWithCloud(e.target.checked)}
            className="rounded bg-gray-700 border-gray-600 text-blue-600 focus:ring-blue-500"
          />
          <span>Confirm with cloud labelers before triggering action</span>
        </label>
      </div>

      {/* Recipients */}
      <div className="bg-gray-800 rounded-lg p-6 mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">Send alert to:</h2>

        {/* Email Recipients */}
        <div className="mb-6">
          <div className="flex items-center gap-4 mb-2">
            <span className="bg-blue-600 text-white px-3 py-1 rounded text-sm">Email</span>
            <input
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && addEmail()}
              placeholder="recipient@example.com"
              className="flex-grow bg-gray-700 border border-gray-600 rounded px-4 py-2 text-white focus:outline-none focus:border-blue-500"
            />
            <button
              onClick={addEmail}
              className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded"
            >
              Add
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {alertEmails.map((email) => (
              <span
                key={email}
                className="bg-gray-700 text-gray-300 px-3 py-1 rounded-full text-sm flex items-center gap-2"
              >
                {email}
                <button onClick={() => removeEmail(email)} className="text-red-400 hover:text-red-300">
                  &times;
                </button>
              </span>
            ))}
          </div>
          <label className="flex items-center space-x-2 text-gray-300 cursor-pointer mt-2">
            <input
              type="checkbox"
              checked={includeImage}
              onChange={(e) => setIncludeImage(e.target.checked)}
              className="rounded bg-gray-700 border-gray-600 text-blue-600 focus:ring-blue-500"
            />
            <span>Include image in email</span>
          </label>
        </div>

        {/* SMS Recipients */}
        <div className="mb-6">
          <div className="flex items-center gap-4 mb-2">
            <span className="bg-green-600 text-white px-3 py-1 rounded text-sm">SMS</span>
            <input
              type="tel"
              value={newPhone}
              onChange={(e) => setNewPhone(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && addPhone()}
              placeholder="+1 555 123 4567"
              className="flex-grow bg-gray-700 border border-gray-600 rounded px-4 py-2 text-white focus:outline-none focus:border-blue-500"
            />
            <button
              onClick={addPhone}
              className="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded"
            >
              Add
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {alertPhones.map((phone) => (
              <span
                key={phone}
                className="bg-gray-700 text-gray-300 px-3 py-1 rounded-full text-sm flex items-center gap-2"
              >
                {phone}
                <button onClick={() => removePhone(phone)} className="text-red-400 hover:text-red-300">
                  &times;
                </button>
              </span>
            ))}
          </div>
          <label className="flex items-center space-x-2 text-gray-300 cursor-pointer mt-2">
            <input
              type="checkbox"
              checked={includeImageSms}
              onChange={(e) => setIncludeImageSms(e.target.checked)}
              className="rounded bg-gray-700 border-gray-600 text-blue-600 focus:ring-blue-500"
            />
            <span>Include image in message (Only for US phone #s)</span>
          </label>
        </div>

        {/* Webhook Recipients */}
        <div>
          <div className="flex items-center gap-4 mb-2">
            <span className="bg-purple-600 text-white px-3 py-1 rounded text-sm">Webhook</span>
            <input
              type="url"
              value={newWebhook}
              onChange={(e) => setNewWebhook(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && addWebhook()}
              placeholder="https://api.example.com/webhook"
              className="flex-grow bg-gray-700 border border-gray-600 rounded px-4 py-2 text-white focus:outline-none focus:border-blue-500"
            />
            <button
              onClick={addWebhook}
              className="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded"
            >
              Add
            </button>
          </div>
          <div className="flex flex-wrap gap-2 mb-4">
            {alertWebhooks.map((url) => (
              <span
                key={url}
                className="bg-gray-700 text-gray-300 px-3 py-1 rounded-full text-sm flex items-center gap-2"
              >
                {url}
                <button onClick={() => removeWebhook(url)} className="text-red-400 hover:text-red-300">
                  &times;
                </button>
              </span>
            ))}
          </div>

          {alertWebhooks.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">
                Template (jinja):
              </label>
              <textarea
                value={webhookTemplate}
                onChange={(e) => setWebhookTemplate(e.target.value)}
                rows={6}
                className="w-full bg-gray-700 border border-gray-600 rounded px-4 py-2 text-yellow-300 font-mono text-sm focus:outline-none focus:border-blue-500"
                placeholder='{"detector_name": "{{detector_name}}", ...}'
              />
              <p className="text-xs text-gray-500 mt-1">
                Available variables: detector_name, detector_id, detection_label, confidence, image_url, timestamp
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Settings */}
      <div className="bg-gray-800 rounded-lg p-6 mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">Alert Settings</h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">Severity</label>
            <select
              value={severity}
              onChange={(e) => setSeverity(e.target.value)}
              className="w-full bg-gray-700 border border-gray-600 rounded px-4 py-2 text-white focus:outline-none focus:border-blue-500"
            >
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">
              Snooze after alert for
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="1"
                max="1440"
                value={cooldownMinutes}
                onChange={(e) => setCooldownMinutes(parseInt(e.target.value) || 5)}
                className="flex-grow bg-gray-700 border border-gray-600 rounded px-4 py-2 text-white focus:outline-none focus:border-blue-500"
              />
              <span className="text-gray-400">minutes</span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">Custom Message</label>
            <input
              type="text"
              value={customMessage}
              onChange={(e) => setCustomMessage(e.target.value)}
              className="w-full bg-gray-700 border border-gray-600 rounded px-4 py-2 text-white focus:outline-none focus:border-blue-500"
              placeholder="Optional custom message..."
            />
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex justify-end space-x-4">
        <button
          onClick={() => navigate(-1)}
          className="bg-gray-600 hover:bg-gray-500 text-white font-bold py-2 px-6 rounded"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={saving}
          className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-6 rounded disabled:bg-gray-500"
        >
          {saving ? 'Saving...' : 'Save Alert'}
        </button>
      </div>
    </div>
  );
};

export default DetectorAlertConfigPage;
