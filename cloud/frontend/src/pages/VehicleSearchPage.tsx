import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

interface VehicleRecord {
  id: string;
  plate_text: string | null;
  vehicle_color: string | null;
  vehicle_type: string | null;
  vehicle_make_model: string | null;
  confidence: number;
  bbox: number[] | null;
  image_url: string | null;
  camera_id: string | null;
  captured_at: string;
}

export default function VehicleSearchPage() {
  const [vehicles, setVehicles] = useState<VehicleRecord[]>([]);
  const [plateSearch, setPlateSearch] = useState('');
  const [colorFilter, setColorFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedVehicle, setSelectedVehicle] = useState<VehicleRecord | null>(null);

  const searchVehicles = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (plateSearch) params.plate_text = plateSearch;
      if (colorFilter) params.vehicle_color = colorFilter;
      if (typeFilter) params.vehicle_type = typeFilter;

      const res = await axios.get('/vehicles/search', { params });
      setVehicles(res.data);
    } catch (err) {
      console.error('Search failed:', err);
    } finally {
      setLoading(false);
    }
  }, [plateSearch, colorFilter, typeFilter]);

  useEffect(() => {
    searchVehicles();
  }, []);

  const handleExportCSV = () => {
    if (vehicles.length === 0) return;
    const headers = ['Plate', 'Color', 'Type', 'Make/Model', 'Confidence', 'Camera', 'Captured At'];
    const rows = vehicles.map(v => [
      v.plate_text || '',
      v.vehicle_color || '',
      v.vehicle_type || '',
      v.vehicle_make_model || '',
      v.confidence.toFixed(2),
      v.camera_id || '',
      new Date(v.captured_at).toLocaleString(),
    ]);
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'vehicles.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-display uppercase tracking-ioWide text-3xl font-bold text-white">
          Vehicle <span className="text-brand-primary">Search</span>
        </h1>
        <button
          onClick={handleExportCSV}
          disabled={vehicles.length === 0}
          className="bg-green-600 hover:bg-green-500 disabled:bg-gray-600 text-white px-4 py-2 rounded text-sm"
        >
          Export CSV
        </button>
      </div>

      {/* Search Controls */}
      <div className="bg-gray-800 rounded-lg p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Plate Number</label>
            <input
              type="text"
              value={plateSearch}
              onChange={e => setPlateSearch(e.target.value)}
              placeholder="ABC-1234"
              className="w-full bg-brand-bg2 text-white rounded px-3 py-2 text-sm border border-gray-600"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Color</label>
            <select
              value={colorFilter}
              onChange={e => setColorFilter(e.target.value)}
              className="w-full bg-brand-bg2 text-white rounded px-3 py-2 text-sm border border-gray-600"
            >
              <option value="">Any Color</option>
              {['White', 'Black', 'Silver', 'Gray', 'Red', 'Blue', 'Green', 'Yellow', 'Brown', 'Orange'].map(c => (
                <option key={c} value={c.toLowerCase()}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Vehicle Type</label>
            <select
              value={typeFilter}
              onChange={e => setTypeFilter(e.target.value)}
              className="w-full bg-brand-bg2 text-white rounded px-3 py-2 text-sm border border-gray-600"
            >
              <option value="">Any Type</option>
              {['car', 'truck', 'van', 'suv', 'vehicle'].map(t => (
                <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <button
              onClick={searchVehicles}
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 text-white py-2 rounded text-sm font-medium"
            >
              {loading ? 'Searching...' : 'Search'}
            </button>
          </div>
        </div>
      </div>

      {/* Results Table */}
      <div className="bg-gray-800 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-brand-bg2">
            <tr>
              <th className="text-left p-3 font-display uppercase tracking-ioWide text-[11px] font-bold text-brand-sage">Plate</th>
              <th className="text-left p-3 font-display uppercase tracking-ioWide text-[11px] font-bold text-brand-sage">Color</th>
              <th className="text-left p-3 font-display uppercase tracking-ioWide text-[11px] font-bold text-brand-sage">Type</th>
              <th className="text-left p-3 font-display uppercase tracking-ioWide text-[11px] font-bold text-brand-sage">Make/Model</th>
              <th className="text-left p-3 font-display uppercase tracking-ioWide text-[11px] font-bold text-brand-sage">Confidence</th>
              <th className="text-left p-3 font-display uppercase tracking-ioWide text-[11px] font-bold text-brand-sage">Camera</th>
              <th className="text-left p-3 font-display uppercase tracking-ioWide text-[11px] font-bold text-brand-sage">Time</th>
            </tr>
          </thead>
          <tbody>
            {vehicles.length === 0 ? (
              <tr>
                <td colSpan={7} className="p-8 text-center text-gray-500">
                  {loading ? 'Searching...' : 'No vehicles found. Adjust filters and search.'}
                </td>
              </tr>
            ) : (
              vehicles.map(v => (
                <tr
                  key={v.id}
                  className="border-t border-brand-line hover:bg-brand-bg2/50 cursor-pointer"
                  onClick={() => setSelectedVehicle(v)}
                >
                  <td className="p-3 text-white font-mono">{v.plate_text || '—'}</td>
                  <td className="p-3 text-gray-300">{v.vehicle_color || '—'}</td>
                  <td className="p-3 text-gray-300">{v.vehicle_type || '—'}</td>
                  <td className="p-3 text-gray-300">{v.vehicle_make_model || '—'}</td>
                  <td className="p-3">
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      v.confidence > 0.8 ? 'bg-green-600' : v.confidence > 0.5 ? 'bg-yellow-600' : 'bg-red-600'
                    }`}>
                      {(v.confidence * 100).toFixed(0)}%
                    </span>
                  </td>
                  <td className="p-3 text-gray-400 text-xs">{v.camera_id || '—'}</td>
                  <td className="p-3 text-gray-400 text-xs">
                    {new Date(v.captured_at).toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Vehicle Detail Modal */}
      {selectedVehicle && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setSelectedVehicle(null)}>
          <div className="bg-gray-800 rounded-lg p-6 max-w-lg w-full mx-4" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-white">Vehicle Details</h3>
              <button onClick={() => setSelectedVehicle(null)} className="text-gray-400 hover:text-white">X</button>
            </div>

            {selectedVehicle.image_url && (
              <img
                src={selectedVehicle.image_url}
                alt="Vehicle"
                className="w-full rounded mb-4"
              />
            )}

            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><span className="text-gray-400">Plate:</span> <span className="text-white font-mono ml-2">{selectedVehicle.plate_text || '—'}</span></div>
              <div><span className="text-gray-400">Color:</span> <span className="text-white ml-2">{selectedVehicle.vehicle_color || '—'}</span></div>
              <div><span className="text-gray-400">Type:</span> <span className="text-white ml-2">{selectedVehicle.vehicle_type || '—'}</span></div>
              <div><span className="text-gray-400">Make/Model:</span> <span className="text-white ml-2">{selectedVehicle.vehicle_make_model || '—'}</span></div>
              <div><span className="text-gray-400">Confidence:</span> <span className="text-white ml-2">{(selectedVehicle.confidence * 100).toFixed(1)}%</span></div>
              <div><span className="text-gray-400">Camera:</span> <span className="text-white ml-2">{selectedVehicle.camera_id || '—'}</span></div>
            </div>

            <p className="text-gray-500 text-xs mt-3">
              Captured: {new Date(selectedVehicle.captured_at).toLocaleString()}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
