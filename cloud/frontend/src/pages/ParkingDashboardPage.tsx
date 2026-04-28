import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

interface ParkingZone {
  id: string;
  name: string;
  camera_id: string | null;
  max_capacity: number;
  current_occupancy: number;
  zone_type: string;
  created_at: string;
  updated_at: string;
}

interface ParkingEvent {
  id: string;
  zone_id: string;
  vehicle_record_id: string | null;
  event_type: string;
  timestamp: string;
}

interface ParkingViolation {
  id: string;
  event_id: string;
  violation_type: string;
  evidence_url: string | null;
  resolved: boolean;
  created_at: string;
}

interface Dashboard {
  total_zones: number;
  total_capacity: number;
  total_occupied: number;
  occupancy_pct: number;
  zones: ParkingZone[];
  recent_events: ParkingEvent[];
  active_violations: number;
}

export default function ParkingDashboardPage() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [violations, setViolations] = useState<ParkingViolation[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateZone, setShowCreateZone] = useState(false);
  const [newZoneName, setNewZoneName] = useState('');
  const [newZoneCapacity, setNewZoneCapacity] = useState(50);
  const [newZoneType, setNewZoneType] = useState('general');

  const fetchDashboard = useCallback(async () => {
    try {
      const [dashRes, violRes] = await Promise.all([
        axios.get('/parking/dashboard'),
        axios.get('/parking/violations', { params: { resolved: false } }),
      ]);
      setDashboard(dashRes.data);
      setViolations(violRes.data);
    } catch (err) {
      console.error('Failed to fetch dashboard:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
    const interval = setInterval(fetchDashboard, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, [fetchDashboard]);

  const createZone = async () => {
    if (!newZoneName.trim()) return;
    try {
      await axios.post('/parking/zones', {
        name: newZoneName,
        max_capacity: newZoneCapacity,
        zone_type: newZoneType,
      });
      setShowCreateZone(false);
      setNewZoneName('');
      setNewZoneCapacity(50);
      fetchDashboard();
    } catch (err) {
      console.error('Failed to create zone:', err);
    }
  };

  const resolveViolation = async (id: string) => {
    try {
      await axios.post(`/parking/violations/${id}/resolve`);
      fetchDashboard();
    } catch (err) {
      console.error('Failed to resolve violation:', err);
    }
  };

  const zoneTypeIcons: Record<string, string> = {
    general: 'P',
    permit: 'PM',
    metered: 'M',
    handicap: 'HC',
    fire: 'FZ',
  };

  const zoneTypeColors: Record<string, string> = {
    general: 'border-blue-500',
    permit: 'border-green-500',
    metered: 'border-yellow-500',
    handicap: 'border-purple-500',
    fire: 'border-red-500',
  };

  const eventTypeColors: Record<string, string> = {
    ENTRY: 'text-green-400',
    EXIT: 'text-blue-400',
    VIOLATION: 'text-red-400',
  };

  if (loading) {
    return <div className="text-center text-gray-500 py-12">Loading parking dashboard...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">IntelliPark</h1>
        <button
          onClick={() => setShowCreateZone(true)}
          className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded text-sm"
        >
          + Add Zone
        </button>
      </div>

      {/* Summary Cards */}
      {dashboard && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="text-3xl font-bold text-white">{dashboard.total_zones}</div>
            <div className="text-sm text-gray-400">Zones</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4">
            <div className="text-3xl font-bold text-white">
              {dashboard.total_occupied}/{dashboard.total_capacity}
            </div>
            <div className="text-sm text-gray-400">Occupied</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4">
            <div className={`text-3xl font-bold ${
              dashboard.occupancy_pct > 90 ? 'text-red-400' :
              dashboard.occupancy_pct > 70 ? 'text-yellow-400' : 'text-green-400'
            }`}>
              {dashboard.occupancy_pct.toFixed(0)}%
            </div>
            <div className="text-sm text-gray-400">Occupancy</div>
          </div>
          <div className="bg-gray-800 rounded-lg p-4">
            <div className={`text-3xl font-bold ${dashboard.active_violations > 0 ? 'text-red-400' : 'text-green-400'}`}>
              {dashboard.active_violations}
            </div>
            <div className="text-sm text-gray-400">Active Violations</div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Zone Cards */}
        <div className="lg:col-span-2">
          <h2 className="text-sm font-medium text-gray-400 mb-3">Parking Zones</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {dashboard?.zones.map(zone => {
              const occupancyPct = zone.max_capacity > 0
                ? (zone.current_occupancy / zone.max_capacity) * 100
                : 0;

              return (
                <div
                  key={zone.id}
                  className={`bg-gray-800 rounded-lg p-4 border-l-4 ${zoneTypeColors[zone.zone_type] || 'border-gray-500'}`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h3 className="text-white font-medium">{zone.name}</h3>
                      <span className="text-xs text-gray-500 uppercase">{zone.zone_type}</span>
                    </div>
                    <span className="text-2xl font-bold text-gray-600">
                      {zoneTypeIcons[zone.zone_type] || 'P'}
                    </span>
                  </div>

                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-gray-400">
                      {zone.current_occupancy} / {zone.max_capacity} spots
                    </span>
                    <span className={`text-sm font-medium ${
                      occupancyPct > 90 ? 'text-red-400' :
                      occupancyPct > 70 ? 'text-yellow-400' : 'text-green-400'
                    }`}>
                      {occupancyPct.toFixed(0)}%
                    </span>
                  </div>

                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all ${
                        occupancyPct > 90 ? 'bg-red-500' :
                        occupancyPct > 70 ? 'bg-yellow-500' : 'bg-green-500'
                      }`}
                      style={{ width: `${Math.min(100, occupancyPct)}%` }}
                    />
                  </div>
                </div>
              );
            })}

            {(!dashboard || dashboard.zones.length === 0) && (
              <div className="col-span-2 text-center text-gray-500 py-8">
                No parking zones configured. Click "Add Zone" to get started.
              </div>
            )}
          </div>
        </div>

        {/* Right Sidebar: Events + Violations */}
        <div className="space-y-4">
          {/* Recent Events */}
          <div className="bg-gray-800 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-400 mb-3">Recent Events</h3>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {dashboard?.recent_events.length === 0 && (
                <p className="text-gray-500 text-xs">No events yet.</p>
              )}
              {dashboard?.recent_events.map(event => (
                <div key={event.id} className="flex items-center justify-between text-xs">
                  <span className={eventTypeColors[event.event_type] || 'text-gray-400'}>
                    {event.event_type}
                  </span>
                  <span className="text-gray-500">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Active Violations */}
          <div className="bg-gray-800 rounded-lg p-4">
            <h3 className="text-sm font-medium text-red-400 mb-3">
              Active Violations ({violations.length})
            </h3>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {violations.length === 0 && (
                <p className="text-gray-500 text-xs">No active violations.</p>
              )}
              {violations.map(v => (
                <div key={v.id} className="bg-gray-700 rounded p-2">
                  <div className="flex justify-between items-center">
                    <span className="text-red-400 text-xs font-medium uppercase">
                      {v.violation_type.replace('_', ' ')}
                    </span>
                    <button
                      onClick={() => resolveViolation(v.id)}
                      className="text-green-400 hover:text-green-300 text-xs"
                    >
                      Resolve
                    </button>
                  </div>
                  <span className="text-gray-500 text-xs">
                    {new Date(v.created_at).toLocaleString()}
                  </span>
                  {v.evidence_url && (
                    <a href={v.evidence_url} target="_blank" rel="noreferrer" className="text-blue-400 text-xs block">
                      View Evidence
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Create Zone Modal */}
      {showCreateZone && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowCreateZone(false)}>
          <div className="bg-gray-800 rounded-lg p-6 max-w-md w-full mx-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-white mb-4">Create Parking Zone</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Zone Name</label>
                <input
                  type="text"
                  value={newZoneName}
                  onChange={e => setNewZoneName(e.target.value)}
                  placeholder="Lot A - Main Entrance"
                  className="w-full bg-gray-700 text-white rounded px-3 py-2 text-sm border border-gray-600"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Max Capacity</label>
                <input
                  type="number"
                  value={newZoneCapacity}
                  onChange={e => setNewZoneCapacity(parseInt(e.target.value) || 0)}
                  className="w-full bg-gray-700 text-white rounded px-3 py-2 text-sm border border-gray-600"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Zone Type</label>
                <select
                  value={newZoneType}
                  onChange={e => setNewZoneType(e.target.value)}
                  className="w-full bg-gray-700 text-white rounded px-3 py-2 text-sm border border-gray-600"
                >
                  <option value="general">General</option>
                  <option value="permit">Permit Only</option>
                  <option value="metered">Metered</option>
                  <option value="handicap">Handicap</option>
                  <option value="fire">Fire Lane</option>
                </select>
              </div>
            </div>
            <div className="flex gap-3 mt-4">
              <button
                onClick={() => setShowCreateZone(false)}
                className="flex-1 bg-gray-600 hover:bg-gray-500 text-white py-2 rounded text-sm"
              >
                Cancel
              </button>
              <button
                onClick={createZone}
                disabled={!newZoneName.trim()}
                className="flex-1 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 text-white py-2 rounded text-sm font-medium"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
