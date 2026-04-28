import React, { useState } from 'react';
import axios from 'axios';

interface Props {
  onLogin: () => void;
  onLocalLogin: (token: string) => void;
}

const LoginPage: React.FC<Props> = ({ onLocalLogin }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleLocalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const response = await axios.post('/token', formData, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      if (response.data && response.data.access_token) {
        onLocalLogin(response.data.access_token);
      } else {
        setError('Login failed. Please check your credentials.');
      }
    } catch (err) {
      console.error(err);
      setError('Invalid email or password.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-brand-bg flex flex-col font-body text-brand-text">
      {/* Hero with pixel-grid + ambient gradients */}
      <div className="relative flex-1 grid lg:grid-cols-[1.2fr_1fr] overflow-hidden">
        {/* Background ambient gradients */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              'radial-gradient(ellipse at 30% 30%, rgba(144,194,38,0.18) 0%, transparent 60%), radial-gradient(ellipse at 70% 70%, rgba(84,160,33,0.12) 0%, transparent 60%)',
          }}
        />
        {/* Pixel grid */}
        <div
          className="absolute inset-0 opacity-25 pointer-events-none"
          style={{
            backgroundImage: 'radial-gradient(circle, rgba(144,194,38,0.4) 1px, transparent 1px)',
            backgroundSize: '32px 32px',
          }}
        />

        {/* Left — pitch */}
        <div className="relative z-10 flex flex-col justify-center px-8 sm:px-14 py-16">
          <div className="inline-flex items-center gap-2 self-start border border-brand-primary/30 bg-brand-primary/[0.08] px-4 py-2 mb-10">
            <span className="w-1.5 h-1.5 rounded-full bg-brand-primary animate-pulse" />
            <span className="font-display uppercase tracking-ioWider text-[10px] text-brand-sage">
              Edge-First · Local Inference · No Cloud Roundtrips
            </span>
          </div>

          <h1 className="font-display uppercase font-bold text-5xl sm:text-6xl lg:text-7xl leading-none tracking-tight mb-6">
            See <span className="text-brand-primary">everything.</span>
            <br />
            Miss <span className="text-brand-sage">nothing.</span>
          </h1>

          <p className="text-brand-textDim max-w-xl text-base leading-relaxed mb-8">
            Real-time vision intelligence at the edge. Detection, scene reasoning, vehicle
            identification, forensic search — all running locally on your hardware.
          </p>

          <div className="flex items-center gap-4">
            <img src="/4wardmotion-logo.png" alt="4wardmotion" className="h-8 w-auto opacity-80" />
            <div className="font-display uppercase tracking-ioWider text-[10px] text-brand-textDim">
              Powered by <span className="text-brand-primary">4wardmotion Solutions</span>
            </div>
          </div>
        </div>

        {/* Right — login form */}
        <div className="relative z-10 bg-black/35 border-l border-brand-line px-8 sm:px-14 py-16 flex flex-col justify-center">
          <div className="font-display uppercase tracking-ioWider text-[11px] text-brand-primary mb-8">
            Sign in
          </div>

          <form onSubmit={handleLocalSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-900/40 border border-red-500/40 text-red-300 px-4 py-3 text-sm">
                {error}
              </div>
            )}

            <div>
              <label
                htmlFor="email"
                className="block font-display uppercase tracking-ioWide text-[10px] text-brand-sage mb-2"
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-black/40 border border-brand-line text-brand-text px-3 py-3 font-mono text-sm focus:border-brand-primary outline-none transition-colors"
                required
                autoComplete="email"
              />
            </div>

            <div>
              <label
                htmlFor="password"
                className="block font-display uppercase tracking-ioWide text-[10px] text-brand-sage mb-2"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-black/40 border border-brand-line text-brand-text px-3 py-3 font-mono text-sm focus:border-brand-primary outline-none transition-colors"
                required
                autoComplete="current-password"
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-brand-primary hover:bg-brand-primaryH text-black font-display uppercase tracking-ioWide font-bold py-3 px-6 text-sm transition-colors disabled:opacity-50"
            >
              {isLoading ? 'Signing In…' : 'Continue'}
            </button>
          </form>

          <div className="mt-8 text-center font-display uppercase tracking-ioWider text-[10px] text-brand-textDim">
            IntelliOptics v2.5
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
