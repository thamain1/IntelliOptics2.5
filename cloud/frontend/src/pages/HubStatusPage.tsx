import React, { useEffect, useState } from 'react';
import axios from 'axios';

interface Hub {
  id: string;
  name: string;
  status: string;
  last_ping?: string;
  location?: string;
}

const HubStatusPage: React.FC = () => {
  const [hubs, setHubs] = useState<Hub[]>([]);

  const fetchHubs = async () => {
    try {
      const res = await axios.get<Hub[]>('/hubs');
      setHubs(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchHubs();
  }, []);

  return (
    <div className="p-8 bg-gray-900 text-gray-300 min-h-screen">
      <h2 className="text-3xl font-bold text-white mb-8">Edge Hub Status</h2>
      <div className="bg-gray-800 rounded-lg shadow-md overflow-hidden">
        <table className="min-w-full divide-y divide-gray-700">
          <thead className="bg-gray-700">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Last Ping</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Location</th>
            </tr>
          </thead>
          <tbody className="bg-gray-800 divide-y divide-gray-700">
            {hubs.length === 0 ? (
                <tr>
                    <td colSpan={4} className="px-6 py-4 text-center text-gray-500 italic">No hubs registered.</td>
                </tr>
            ) : hubs.map((h) => (
              <tr key={h.id} className="hover:bg-gray-700 transition">
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-white">{h.name}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                    h.status === 'online' ? 'bg-green-100 text-green-800' : 
                    h.status === 'offline' ? 'bg-red-100 text-red-800' : 
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {h.status}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-400">{h.last_ping ? new Date(h.last_ping).toLocaleString() : '—'}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">{h.location || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default HubStatusPage;