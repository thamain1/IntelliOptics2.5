import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

// --- Interface Definitions ---
interface Detector {
  id: string;
  name: string;
  group_name?: string;
}

interface Hub {
  id: string;
  name: string;
}

interface Camera {
  id: string;
  name: string;
  url: string;
  hub_id: string;
  hub_name?: string;
}

// --- Main Page Component ---
const DeploymentManagerPage = () => {
  const [detectors, setDetectors] = useState<Detector[]>([]);
  const [hubs, setHubs] = useState<Hub[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selectedDetector, setSelectedDetector] = useState<string>('');
  const [selectedHubs, setSelectedHubs] = useState<Set<string>>(new Set());
  const [selectedCameras, setSelectedCameras] = useState<Set<string>>(new Set());
  const [generatedConfig, setGeneratedConfig] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [isDeploying, setIsDeploying] = useState(false);
  const [groupFilter, setGroupFilter] = useState<string>('all');

  // Get unique groups from detectors
  const groups = Array.from(new Set(detectors.map(d => d.group_name).filter(Boolean))) as string[];

  // Filter detectors by selected group
  const filteredDetectors = groupFilter === 'all'
    ? detectors
    : detectors.filter(d => d.group_name === groupFilter);

  // Fetch initial data for detectors and hubs
  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const [detectorsRes, hubsRes] = await Promise.all([
          axios.get('/detectors'),
          axios.get('/hubs'),
        ]);
        setDetectors(detectorsRes.data);
        setHubs(hubsRes.data);
      } catch (error) {
        toast.error('Failed to fetch detectors and hubs.');
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  // Fetch cameras when hubs are selected
  useEffect(() => {
    const fetchCameras = async () => {
        if (selectedHubs.size === 0) {
            setCameras([]);
            setSelectedCameras(new Set());
            return;
        }
        try {
            const cameraPromises = Array.from(selectedHubs).map(hubId =>
                axios.get(`/hubs/${hubId}/cameras`).then(res => 
                    res.data.map((cam: any) => ({
                        ...cam,
                        hub_id: hubId,
                        hub_name: hubs.find(h => h.id === hubId)?.name
                    }))
                )
            );
            const results = await Promise.all(cameraPromises);
            const allCameras = results.flatMap(c => c);
            setCameras(allCameras);
            
            // Cleanup selected cameras that are no longer available
            setSelectedCameras(prev => {
                const next = new Set(prev);
                const availableIds = new Set(allCameras.map(c => c.id || c.name)); // Assuming id or name as key
                Array.from(next).forEach(id => {
                    if (!availableIds.has(id)) next.delete(id);
                });
                return next;
            });
        } catch (error) {
            console.error('Failed to fetch cameras:', error);
        }
    };
    fetchCameras();
  }, [selectedHubs, hubs]);

  const handleHubSelection = (hubId: string) => {
    setSelectedHubs((prev) => {
      const newSelection = new Set(prev);
      newSelection.has(hubId) ? newSelection.delete(hubId) : newSelection.add(hubId);
      return newSelection;
    });
  };

  const handleCameraSelection = (cameraId: string) => {
    setSelectedCameras((prev) => {
      const newSelection = new Set(prev);
      newSelection.has(cameraId) ? newSelection.delete(cameraId) : newSelection.add(cameraId);
      return newSelection;
    });
  };

  const handlePreview = async () => {
    if (!selectedDetector || selectedHubs.size === 0) {
      toast.warn('Please select at least one detector and one edge device.');
      return;
    }
    const firstHubId = Array.from(selectedHubs)[0];
    try {
      const response = await axios.get(
        `/deployments/generate-config?hub_id=${firstHubId}&detector_id=${selectedDetector}`,
        { headers: { 'Accept': 'application/x-yaml' } }
      );
      setGeneratedConfig(response.data);
    } catch (error) {
      toast.error('Failed to generate configuration preview.');
    }
  };

  const handleDeploy = async () => {
    if (!selectedDetector || selectedHubs.size === 0) {
      toast.warn('Please select at least one detector and one edge device.');
      return;
    }
    
    if (selectedCameras.size === 0) {
        toast.warn('Please select at least one camera to deploy to.');
        return;
    }

    setIsDeploying(true);

    const deployments = Array.from(selectedHubs).map(hubId => {
      // Filter cameras belonging to this hub
      const hubCameras = cameras.filter(c => c.hub_id === hubId && selectedCameras.has(c.id || c.name));
      
      return axios.post('/deployments', {
        hub_id: hubId,
        detector_id: selectedDetector,
        cameras: hubCameras.map(c => ({
            name: c.name,
            url: c.url,
            sampling_interval: 2.0 // Default
        })),
      });
    });

    try {
      await Promise.all(deployments);
      toast.success(`Successfully initiated deployment to ${selectedHubs.size} device(s).`);
      setGeneratedConfig('');
      setSelectedHubs(new Set());
      setSelectedCameras(new Set());
      setSelectedDetector('');
    } catch (error) {
      toast.error('One or more deployments failed.');
    } finally {
      setIsDeploying(false);
    }
  };

  if (isLoading) {
    return <div className="p-8 text-white text-center">Loading deployment data...</div>;
  }

  return (
    <div className="p-8 bg-gray-900 text-gray-300 min-h-screen flex flex-col">
      <ToastContainer position="top-right" autoClose={5000} hideProgressBar={false} />
      <header className="mb-6">
        <h1 className="text-3xl font-bold text-white">Deployment Manager</h1>
        <p className="text-gray-400">Assign detectors and cameras to your edge devices.</p>
      </header>

      {/* Action buttons - moved to top */}
      <div className="mb-6 flex space-x-4">
        <button onClick={handlePreview} className="bg-gray-600 hover:bg-gray-500 text-white font-bold py-2 px-4 rounded transition-transform transform hover:scale-105">
          Preview Config
        </button>
        <button onClick={handleDeploy} disabled={isDeploying} className="bg-green-600 hover:bg-green-500 text-white font-bold py-2 px-4 rounded disabled:bg-gray-500 disabled:cursor-not-allowed transition-transform transform hover:scale-105">
          {isDeploying ? 'Deploying...' : `Deploy to ${selectedHubs.size} Device(s)`}
        </button>
      </div>

      {/* Three-column selection grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 flex-grow overflow-hidden">
        {/* Column 1: Detectors */}
        <div className="bg-gray-800 rounded-lg p-4 flex flex-col min-h-0 overflow-hidden">
          <div className="flex items-center justify-between mb-2 flex-shrink-0">
            <h2 className="text-lg font-semibold text-white">1. Select a Detector</h2>
            {groups.length > 0 && (
              <select
                value={groupFilter}
                onChange={(e) => setGroupFilter(e.target.value)}
                className="bg-gray-700 text-white text-sm rounded px-2 py-1 border border-gray-600 focus:outline-none focus:border-blue-500"
              >
                <option value="all">All Groups</option>
                {groups.map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            )}
          </div>
          <div className="overflow-y-auto flex-grow pr-2">
            <ul className="space-y-2">
              {filteredDetectors.map((d) => (
                <li key={d.id}
                    className={`p-2 rounded cursor-pointer transition-colors ${selectedDetector === d.id ? 'bg-blue-600 text-white shadow-lg border-l-4 border-blue-300' : 'bg-gray-700 hover:bg-gray-600 border-l-4 border-transparent'}`}
                    onClick={() => setSelectedDetector(d.id)}>
                  <span>{d.name}</span>
                  {d.group_name && <span className="text-xs text-gray-400 ml-2">({d.group_name})</span>}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Column 2: Hubs */}
        <div className="bg-gray-800 rounded-lg p-4 flex flex-col min-h-0 overflow-hidden">
          <h2 className="text-lg font-semibold text-white mb-2 flex-shrink-0">2. Select Edge Devices (Hubs)</h2>
          <div className="overflow-y-auto flex-grow pr-2">
            <ul className="space-y-2">
              {hubs.map((h) => (
                <li key={h.id}
                    className={`p-2 rounded cursor-pointer flex items-center transition-colors ${selectedHubs.has(h.id) ? 'bg-blue-600 text-white' : 'bg-gray-700 hover:bg-gray-600'}`}
                    onClick={() => handleHubSelection(h.id)}>
                  <input type="checkbox" readOnly checked={selectedHubs.has(h.id)} className="mr-3 h-4 w-4 rounded-sm border-gray-500 bg-gray-600 accent-blue-500" />
                  {h.name}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Column 3: Cameras */}
        <div className="bg-gray-800 rounded-lg p-4 flex flex-col min-h-0 overflow-hidden">
          <h2 className="text-lg font-semibold text-white mb-2 flex-shrink-0">3. Assign Cameras</h2>
          <div className="overflow-y-auto flex-grow pr-2">
            {cameras.length === 0 ? (
              <div className="text-gray-500 h-full flex items-center justify-center">
                <p className="text-center italic">Select edge devices to view available cameras.</p>
              </div>
            ) : (
              <ul className="space-y-2">
                {cameras.map((c) => (
                  <li key={c.id || c.name}
                      className={`p-2 rounded cursor-pointer flex items-center transition-colors ${selectedCameras.has(c.id || c.name) ? 'bg-blue-600 text-white' : 'bg-gray-700 hover:bg-gray-600'}`}
                      onClick={() => handleCameraSelection(c.id || c.name)}>
                    <input type="checkbox" readOnly checked={selectedCameras.has(c.id || c.name)} className="mr-3 h-4 w-4 rounded-sm border-gray-500 bg-gray-600 accent-blue-500" />
                    <div>
                      <p className="text-sm font-bold">{c.name}</p>
                      <p className="text-xs opacity-75">{c.hub_name}</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {/* Config preview section */}
      {generatedConfig && (
        <div className="mt-6 bg-gray-800 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-white mb-2">Generated `edge-config.yaml` Preview</h3>
          <pre className="bg-gray-900 p-4 rounded text-sm text-yellow-300 overflow-auto max-h-96">
            <code>{generatedConfig}</code>
          </pre>
        </div>
      )}
    </div>
  );
};

export default DeploymentManagerPage;