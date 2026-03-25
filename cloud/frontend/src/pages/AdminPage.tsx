import React, { useEffect, useState, FormEvent } from 'react';
import axios from 'axios';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

interface User {
  id: string;
  email: string;
  roles: string;
}

interface RetentionSettings {
  id: string;
  retention_days: number;
  exclude_verified: boolean;
  auto_cleanup_enabled: boolean;
  default_sample_percentage: number;
  stratify_by_label: boolean;
  last_cleanup_at: string | null;
  last_cleanup_count: number | null;
}

interface StorageStats {
  total_queries: number;
  total_with_images: number;
  verified_queries: number;
  unverified_queries: number;
  estimated_size_mb: number;
  queries_by_age: Record<string, number>;
  queries_by_label: Record<string, number>;
  oldest_query_date: string | null;
  newest_query_date: string | null;
}

interface PurgeResponse {
  deleted_count: number;
  deleted_blob_count: number;
  dry_run: boolean;
  message: string;
}

interface ExportResponse {
  total_samples: number;
  samples_by_label: Record<string, number>;
  download_url: string;
  export_id: string;
  message: string;
}

const AdminPage: React.FC = () => {
  // User management state
  const [users, setUsers] = useState<User[]>([]);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('reviewer');

  // Data management state
  const [activeTab, setActiveTab] = useState<'users' | 'data'>('users');
  const [storageStats, setStorageStats] = useState<StorageStats | null>(null);
  const [retentionSettings, setRetentionSettings] = useState<RetentionSettings | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);

  // Purge form state
  const [purgeDays, setPurgeDays] = useState(30);
  const [purgeExcludeVerified, setPurgeExcludeVerified] = useState(true);
  const [purgeLabelFilter, setPurgeLabelFilter] = useState('');
  const [purging, setPurging] = useState(false);

  // Export form state
  const [exportPercentage, setExportPercentage] = useState(10);
  const [exportStratify, setExportStratify] = useState(true);
  const [exportVerifiedOnly, setExportVerifiedOnly] = useState(false);
  const [exportLabelFilter, setExportLabelFilter] = useState('');
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState<ExportResponse | null>(null);

  // Fetch functions
  const fetchUsers = async () => {
    try {
      const res = await axios.get<User[]>('/users');
      setUsers(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchStorageStats = async () => {
    try {
      setLoadingStats(true);
      const res = await axios.get<StorageStats>('/admin/data/storage-stats');
      setStorageStats(res.data);
    } catch (err) {
      console.error(err);
      toast.error('Failed to load storage stats');
    } finally {
      setLoadingStats(false);
    }
  };

  const fetchRetentionSettings = async () => {
    try {
      const res = await axios.get<RetentionSettings>('/admin/data/retention-settings');
      setRetentionSettings(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  useEffect(() => {
    if (activeTab === 'data') {
      fetchStorageStats();
      fetchRetentionSettings();
    }
  }, [activeTab]);

  // User management handlers
  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await axios.post('/users', { email, password, roles: role });
      setEmail('');
      setPassword('');
      setRole('reviewer');
      fetchUsers();
      toast.success('User created');
    } catch (err) {
      console.error(err);
      toast.error('Failed to create user');
    }
  };

  const handleRoleChange = async (id: string, newRole: string) => {
    try {
      await axios.put(`/users/${id}`, { roles: newRole });
      fetchUsers();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await axios.delete(`/users/${id}`);
      fetchUsers();
      toast.success('User deleted');
    } catch (err) {
      console.error(err);
    }
  };

  // Data management handlers
  const handleSaveRetentionSettings = async () => {
    if (!retentionSettings) return;
    try {
      await axios.put('/admin/data/retention-settings', {
        retention_days: retentionSettings.retention_days,
        exclude_verified: retentionSettings.exclude_verified,
        auto_cleanup_enabled: retentionSettings.auto_cleanup_enabled,
      });
      toast.success('Settings saved');
    } catch (err) {
      console.error(err);
      toast.error('Failed to save settings');
    }
  };

  const handlePurge = async (dryRun: boolean) => {
    try {
      setPurging(true);
      const res = await axios.post<PurgeResponse>('/admin/data/purge', {
        older_than_days: purgeDays,
        exclude_verified: purgeExcludeVerified,
        label_filter: purgeLabelFilter || null,
        dry_run: dryRun,
      });
      if (dryRun) {
        toast.info(res.data.message);
      } else {
        toast.success(res.data.message);
        fetchStorageStats();
      }
    } catch (err) {
      console.error(err);
      toast.error('Purge failed');
    } finally {
      setPurging(false);
    }
  };

  const handleExport = async () => {
    try {
      setExporting(true);
      setExportResult(null);
      const res = await axios.post<ExportResponse>('/admin/data/export-training', {
        sample_percentage: exportPercentage,
        stratify_by_label: exportStratify,
        verified_only: exportVerifiedOnly,
        label_filter: exportLabelFilter ? exportLabelFilter.split(',').map(s => s.trim()) : null,
      });
      setExportResult(res.data);
      toast.success(`Export ready: ${res.data.total_samples} samples`);
    } catch (err: any) {
      console.error(err);
      toast.error(err.response?.data?.detail || 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="p-8 bg-gray-900 text-gray-300 min-h-screen">
      <h2 className="text-3xl font-bold text-white mb-8">Admin Panel</h2>

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        <button
          onClick={() => setActiveTab('users')}
          className={`px-4 py-2 rounded font-medium transition ${
            activeTab === 'users'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          User Management
        </button>
        <button
          onClick={() => setActiveTab('data')}
          className={`px-4 py-2 rounded font-medium transition ${
            activeTab === 'data'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          Data Management
        </button>
      </div>

      {/* User Management Tab */}
      {activeTab === 'users' && (
        <>
          <div className="bg-gray-800 rounded-lg shadow-md p-6 mb-8 border border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-4">Add New User</h3>
            <form onSubmit={handleCreate} className="flex gap-4 items-end">
              <div className="flex-grow">
                <label className="block text-sm font-medium text-gray-400 mb-1">Email Address</label>
                <input
                  type="email"
                  placeholder="user@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2"
                  required
                />
              </div>
              <div className="w-1/4">
                <label className="block text-sm font-medium text-gray-400 mb-1">Password</label>
                <input
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2"
                  required
                  minLength={6}
                />
              </div>
              <div className="w-1/4">
                <label className="block text-sm font-medium text-gray-400 mb-1">Role</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm p-2"
                >
                  <option value="admin">Admin</option>
                  <option value="reviewer">Reviewer</option>
                </select>
              </div>
              <button type="submit" className="bg-green-600 hover:bg-green-500 text-white font-bold py-2 px-6 rounded transition h-10 mb-0.5">
                Add User
              </button>
            </form>
          </div>

          <div className="bg-gray-800 rounded-lg shadow-md overflow-hidden border border-gray-700">
            <table className="min-w-full divide-y divide-gray-700">
              <thead className="bg-gray-700">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Email</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Role</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-gray-800 divide-y divide-gray-700">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-gray-700 transition">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-white">{u.email}</td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <select
                        value={u.roles}
                        onChange={(e) => handleRoleChange(u.id, e.target.value)}
                        className="rounded-md bg-gray-700 border-gray-600 text-white text-sm focus:border-blue-500 focus:ring-blue-500 p-1"
                      >
                        <option value="admin">Admin</option>
                        <option value="reviewer">Reviewer</option>
                      </select>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <button
                        className="text-red-400 hover:text-red-300 transition"
                        onClick={() => handleDelete(u.id)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Data Management Tab */}
      {activeTab === 'data' && (
        <div className="space-y-6">
          {/* Storage Stats */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-white">Storage Statistics</h3>
              <button
                onClick={fetchStorageStats}
                disabled={loadingStats}
                className="text-blue-400 hover:text-blue-300 text-sm"
              >
                {loadingStats ? 'Loading...' : 'Refresh'}
              </button>
            </div>
            {storageStats ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-gray-700 rounded p-4">
                  <div className="text-2xl font-bold text-white">{storageStats.total_queries.toLocaleString()}</div>
                  <div className="text-sm text-gray-400">Total Queries</div>
                </div>
                <div className="bg-gray-700 rounded p-4">
                  <div className="text-2xl font-bold text-white">{storageStats.estimated_size_mb.toFixed(1)} MB</div>
                  <div className="text-sm text-gray-400">Est. Storage</div>
                </div>
                <div className="bg-gray-700 rounded p-4">
                  <div className="text-2xl font-bold text-green-400">{storageStats.verified_queries.toLocaleString()}</div>
                  <div className="text-sm text-gray-400">Verified</div>
                </div>
                <div className="bg-gray-700 rounded p-4">
                  <div className="text-2xl font-bold text-yellow-400">{storageStats.unverified_queries.toLocaleString()}</div>
                  <div className="text-sm text-gray-400">Unverified</div>
                </div>
              </div>
            ) : (
              <div className="text-gray-400">Loading...</div>
            )}

            {/* Age breakdown */}
            {storageStats && (
              <div className="mt-4 grid grid-cols-3 gap-4">
                {Object.entries(storageStats.queries_by_age).map(([age, count]) => (
                  <div key={age} className="bg-gray-700/50 rounded p-3 text-center">
                    <div className="text-lg font-semibold text-white">{count.toLocaleString()}</div>
                    <div className="text-xs text-gray-400">{age}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Top labels */}
            {storageStats && (
              <div className="mt-4">
                <div className="text-sm text-gray-400 mb-2">Top Labels:</div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(storageStats.queries_by_label).slice(0, 10).map(([label, count]) => (
                    <span key={label} className="bg-gray-700 px-2 py-1 rounded text-sm">
                      {label}: {count.toLocaleString()}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Retention Settings */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-4">Retention Settings</h3>
            {retentionSettings ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-1">Retention Period (days)</label>
                    <input
                      type="number"
                      min="1"
                      max="365"
                      value={retentionSettings.retention_days}
                      onChange={(e) => setRetentionSettings({
                        ...retentionSettings,
                        retention_days: parseInt(e.target.value) || 30
                      })}
                      className="block w-full rounded-md bg-gray-700 border-gray-600 text-white p-2"
                    />
                  </div>
                  <div className="flex items-center gap-4 pt-6">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={retentionSettings.exclude_verified}
                        onChange={(e) => setRetentionSettings({
                          ...retentionSettings,
                          exclude_verified: e.target.checked
                        })}
                        className="rounded bg-gray-700 border-gray-600"
                      />
                      <span className="text-sm text-gray-300">Exclude verified queries</span>
                    </label>
                  </div>
                </div>
                <div className="flex gap-4 items-center">
                  <button
                    onClick={handleSaveRetentionSettings}
                    className="bg-blue-600 hover:bg-blue-500 text-white font-medium py-2 px-4 rounded transition"
                  >
                    Save Settings
                  </button>
                  {retentionSettings.last_cleanup_at && (
                    <span className="text-sm text-gray-400">
                      Last cleanup: {new Date(retentionSettings.last_cleanup_at).toLocaleString()}
                      {retentionSettings.last_cleanup_count !== null && ` (${retentionSettings.last_cleanup_count} deleted)`}
                    </span>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-gray-400">Loading...</div>
            )}
          </div>

          {/* Purge Data */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-4">Purge Data</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Older than (days)</label>
                <input
                  type="number"
                  min="0"
                  max="365"
                  value={purgeDays}
                  onChange={(e) => setPurgeDays(parseInt(e.target.value) ?? 0)}
                  className="block w-full rounded-md bg-gray-700 border-gray-600 text-white p-2"
                />
                <span className="text-xs text-gray-500">0 = all data from today and earlier</span>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Label filter (optional)</label>
                <input
                  type="text"
                  placeholder="e.g., person"
                  value={purgeLabelFilter}
                  onChange={(e) => setPurgeLabelFilter(e.target.value)}
                  className="block w-full rounded-md bg-gray-700 border-gray-600 text-white p-2"
                />
              </div>
              <div className="flex items-center pt-6">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={purgeExcludeVerified}
                    onChange={(e) => setPurgeExcludeVerified(e.target.checked)}
                    className="rounded bg-gray-700 border-gray-600"
                  />
                  <span className="text-sm text-gray-300">Exclude verified</span>
                </label>
              </div>
            </div>
            <div className="flex gap-4">
              <button
                onClick={() => handlePurge(true)}
                disabled={purging}
                className="bg-gray-600 hover:bg-gray-500 text-white font-medium py-2 px-4 rounded transition"
              >
                {purging ? 'Processing...' : 'Preview (Dry Run)'}
              </button>
              <button
                onClick={() => {
                  if (confirm('Are you sure? This will permanently delete queries and images.')) {
                    handlePurge(false);
                  }
                }}
                disabled={purging}
                className="bg-red-600 hover:bg-red-500 text-white font-medium py-2 px-4 rounded transition"
              >
                {purging ? 'Processing...' : 'Purge Now'}
              </button>
            </div>
          </div>

          {/* Training Export */}
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-4">Training Data Export</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Sample % ({exportPercentage}%)</label>
                <input
                  type="range"
                  min="1"
                  max="100"
                  value={exportPercentage}
                  onChange={(e) => setExportPercentage(parseInt(e.target.value))}
                  className="w-full accent-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Label filter (comma-sep)</label>
                <input
                  type="text"
                  placeholder="e.g., cat, dog, car"
                  value={exportLabelFilter}
                  onChange={(e) => setExportLabelFilter(e.target.value)}
                  className="block w-full rounded-md bg-gray-700 border-gray-600 text-white p-2"
                />
              </div>
              <div className="flex flex-col gap-2 pt-6">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={exportStratify}
                    onChange={(e) => setExportStratify(e.target.checked)}
                    className="rounded bg-gray-700 border-gray-600"
                  />
                  <span className="text-sm text-gray-300">Stratify by label</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={exportVerifiedOnly}
                    onChange={(e) => setExportVerifiedOnly(e.target.checked)}
                    className="rounded bg-gray-700 border-gray-600"
                  />
                  <span className="text-sm text-gray-300">Verified only</span>
                </label>
              </div>
            </div>
            <div className="flex gap-4 items-center">
              <button
                onClick={handleExport}
                disabled={exporting}
                className="bg-green-600 hover:bg-green-500 text-white font-medium py-2 px-4 rounded transition"
              >
                {exporting ? 'Preparing...' : 'Generate Export'}
              </button>
              {exportResult && (
                <a
                  href={`http://localhost:8000${exportResult.download_url}`}
                  className="bg-blue-600 hover:bg-blue-500 text-white font-medium py-2 px-4 rounded transition"
                  download
                >
                  Download ZIP ({exportResult.total_samples} samples)
                </a>
              )}
            </div>
            {exportResult && (
              <div className="mt-4 text-sm text-gray-400">
                <div className="mb-1">Samples by label:</div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(exportResult.samples_by_label).map(([label, count]) => (
                    <span key={label} className="bg-gray-700 px-2 py-1 rounded">
                      {label}: {count}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <ToastContainer position="top-right" autoClose={3000} hideProgressBar={false} theme="dark" />
    </div>
  );
};

export default AdminPage;
