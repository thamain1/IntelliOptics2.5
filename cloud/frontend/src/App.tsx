import React, { useEffect, useState } from 'react';
import { Route, Routes, Link, useNavigate } from 'react-router-dom';
import axios from 'axios';

// Set base URL for all axios requests
// Production: '/api' — nginx strips prefix and proxies to backend
// Development: set VITE_API_BASE_URL=http://localhost:8000
axios.defaults.baseURL = import.meta.env.VITE_API_BASE_URL || '/api';

import { msalInstance, login, logout, isMsalConfigured } from './utils/auth';
import LoginPage from './pages/LoginPage';
import DetectorsPage from './pages/DetectorsPage';
import QueryHistoryPage from './pages/QueryHistoryPage';
import EscalationQueuePage from './pages/EscalationQueuePage';
import HubStatusPage from './pages/HubStatusPage';
import AdminPage from './pages/AdminPage';
import DetectorConfigPage from './pages/DetectorConfigPage';
import AlertSettingsPage from './pages/AlertSettingsPage';
import DeploymentManagerPage from './pages/DeploymentManagerPage';
import CameraInspectionPage from './pages/CameraInspectionPage';
import DetectorAlertsPage from './pages/DetectorAlertsPage';
import DemoStreamPage from './pages/DemoStreamPage';
import DetectorAlertConfigPage from './pages/DetectorAlertConfigPage';
import OpenVocabPage from './pages/OpenVocabPage';
import VehicleSearchPage from './pages/VehicleSearchPage';
import ForensicSearchPage from './pages/ForensicSearchPage';
import ParkingDashboardPage from './pages/ParkingDashboardPage';

function NavDropdown({ label, items }: { label: string; items: { to: string; label: string }[] }) {
  const [open, setOpen] = useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="px-4 py-2 font-display uppercase tracking-ioWide text-[11px] text-brand-textDim hover:text-brand-primary transition-colors flex items-center gap-1.5"
      >
        {label}
        <svg className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 bg-brand-bg2 border border-brand-line min-w-[200px] py-1 z-50">
          {items.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              onClick={() => setOpen(false)}
              className="block px-4 py-3 font-display uppercase tracking-ioWide text-[11px] text-brand-textDim hover:text-brand-primary hover:bg-brand-panel transition-colors"
            >
              {item.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    localStorage.removeItem('local_access_token');
    setIsAuthenticated(false);
    setAccessToken(null);
  };

  useEffect(() => {
    // Check for local token first
    const localToken = localStorage.getItem('local_access_token');
    if (localToken) {
        setIsAuthenticated(true);
        setAccessToken(localToken);
        axios.defaults.headers.common['Authorization'] = `Bearer ${localToken}`;
        return;
    }

    // Only check MSAL if it's configured
    if (isMsalConfigured && msalInstance) {
      const account = msalInstance.getActiveAccount();
      if (account) {
        setIsAuthenticated(true);
        // Acquire token silently
        msalInstance
          .acquireTokenSilent({
            scopes: ['openid', 'profile', 'email'],
            account,
          })
          .then((res) => {
            setAccessToken(res.accessToken);
            axios.defaults.headers.common['Authorization'] = `Bearer ${res.accessToken}`;
          })
          .catch(() => {
            setIsAuthenticated(false);
          });
      }
    }
  }, []);

  // Axios interceptor to handle 401 errors globally (skip /token — login failures are not session expiry)
  useEffect(() => {
    const interceptor = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        const url = error.config?.url || '';
        if (error.response && error.response.status === 401 && !url.includes('/token')) {
          console.warn('Unauthorized request detected. Clearing session.');
          handleLogout();
        }
        return Promise.reject(error);
      }
    );

    return () => {
      axios.interceptors.response.eject(interceptor);
    };
  }, []);

  const handleLogin = async () => {
    try {
      const res = await login();
      if (res) {
        setIsAuthenticated(true);
        setAccessToken(res.accessToken);
        axios.defaults.headers.common['Authorization'] = `Bearer ${res.accessToken}`;
        navigate('/');
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleLocalLogin = (token: string) => {
    localStorage.setItem('local_access_token', token);
    setAccessToken(token);
    axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    setIsAuthenticated(true);
    navigate('/');
  };

  if (!isAuthenticated) {
    return <LoginPage onLogin={handleLogin} onLocalLogin={handleLocalLogin} />;
  }

  return (
    <div className="min-h-screen bg-brand-bg text-brand-text flex flex-col font-body">
      <nav className="bg-brand-bg border-b border-brand-line relative z-50">
        <div className="max-w-7xl mx-auto px-6 py-3 flex justify-between items-center">
          <div className="flex items-center gap-6">
            <Link to="/" className="flex items-center gap-3 mr-4 group">
              <img
                src="/4wardmotion-logo.png"
                alt="4wardmotion"
                className="h-9 w-auto"
              />
              <div className="leading-tight">
                <div className="font-display uppercase tracking-ioWide text-[15px] text-brand-text group-hover:text-brand-primary transition-colors">
                  Intelli<span className="text-brand-primary">Optics</span>
                </div>
                <div className="font-display uppercase tracking-ioWider text-[8px] text-brand-textDim">
                  by 4wardmotion
                </div>
              </div>
            </Link>

            {/* Operations Dropdown */}
            <NavDropdown label="Operations" items={[
              { to: '/detectors', label: 'Detectors' },
              { to: '/deployments', label: 'Deployments' },
              { to: '/hubs', label: 'Hubs' },
              { to: '/demo', label: 'Live Stream' },
            ]} />

            {/* AI Tools Dropdown */}
            <NavDropdown label="AI Tools" items={[
              { to: '/open-vocab', label: 'Visual Insight' },
              { to: '/vehicles', label: 'Vehicle Search' },
              { to: '/forensic-search', label: 'BOLO Search' },
              { to: '/parking', label: 'Parking' },
            ]} />

            {/* Monitoring Dropdown */}
            <NavDropdown label="Monitoring" items={[
              { to: '/queries', label: 'Query History' },
              { to: '/escalations', label: 'Escalation Queue' },
              { to: '/detector-alerts', label: 'Alerts' },
              { to: '/camera-inspection', label: 'Camera Health' },
            ]} />

            {/* Admin Dropdown */}
            <NavDropdown label="Admin" items={[
              { to: '/settings/alerts', label: 'Alert Settings' },
              { to: '/admin', label: 'System Admin' },
            ]} />
          </div>
          <button
            onClick={handleLogout}
            className="font-display uppercase tracking-ioWide text-[11px] text-red-400 hover:text-red-300 px-4 py-2 border border-red-500/30 hover:border-red-400 transition-colors"
          >
            Sign Out
          </button>
        </div>
      </nav>
      <div className="flex-1 max-w-7xl mx-auto w-full py-4">
        <Routes>
          <Route path="/" element={<DetectorsPage />} />
          <Route path="/detectors" element={<DetectorsPage />} />
          <Route path="/detectors/:id/configure" element={<DetectorConfigPage />} />
          <Route path="/detectors/:detectorId/alert-config" element={<DetectorAlertConfigPage />} />
          <Route path="/queries" element={<QueryHistoryPage />} />
          <Route path="/escalations" element={<EscalationQueuePage />} />
          <Route path="/hubs" element={<HubStatusPage />} />
          <Route path="/camera-inspection" element={<CameraInspectionPage />} />
          <Route path="/detector-alerts" element={<DetectorAlertsPage />} />
          <Route path="/demo" element={<DemoStreamPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/settings/alerts" element={<AlertSettingsPage />} />
          <Route path="/deployments" element={<DeploymentManagerPage />} />
          <Route path="/open-vocab" element={<OpenVocabPage />} />
          <Route path="/vehicles" element={<VehicleSearchPage />} />
          <Route path="/forensic-search" element={<ForensicSearchPage />} />
          <Route path="/parking" element={<ParkingDashboardPage />} />
        </Routes>
      </div>

      {/* Footer */}
      <footer className="py-5 text-center border-t border-brand-line">
        <div className="font-display uppercase tracking-ioWider text-[10px] text-brand-textDim">
          Powered by <span className="text-brand-primary">4wardmotion Solutions</span>
        </div>
      </footer>
    </div>
  );
}

export default App;