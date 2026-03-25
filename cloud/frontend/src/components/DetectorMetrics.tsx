import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import axios from 'axios';

interface MetricsData {
  detector_id: string;
  balanced_accuracy: number | null;
  sensitivity: number | null;
  specificity: number | null;
  true_positives: number;
  true_negatives: number;
  false_positives: number;
  false_negatives: number;
  total_queries: number;
  time_range: string;
  message?: string;
}

interface Props {
  detectorId: string;
  timeRange?: string;
}

const DetectorMetrics: React.FC<Props> = ({ detectorId, timeRange = '7d' }) => {
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    console.log("DetectorMetrics: Mounted/Updated for ID", detectorId);
    fetchMetrics();
  }, [detectorId, timeRange]);

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);
    console.log(`Fetching metrics for detector ${detectorId} (${timeRange})...`);

    try {
      const response = await axios.get(`/detectors/${detectorId}/metrics`, {
        params: { time_range: timeRange }
      });
      console.log('Metrics received:', response.data);
      setMetrics(response.data);
    } catch (err: any) {
      console.error('Metrics fetch error:', err);
      setError(err.response?.data?.detail || 'Failed to load metrics');
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="text-center p-4 text-gray-400">Loading metrics...</div>;
  if (error) return <div className="text-red-400 p-4 bg-red-900/20 border border-red-900/50 rounded">Error: {error}</div>;
  if (!metrics || metrics.total_queries === 0) {
    return (
      <div className="bg-blue-900/20 border border-blue-900/50 rounded p-6 text-center">
        <p className="text-blue-300">
          {metrics?.message || 'No ground truth data available for this time range. Start reviewing queries to see accuracy metrics.'}
        </p>
      </div>
    );
  }

  // Prepare data for bar chart
  const chartData = [
    {
      name: 'Balanced Acc',
      value: (metrics.balanced_accuracy || 0) * 100,
      color: '#8884d8'
    },
    {
      name: 'Sensitivity',
      value: (metrics.sensitivity || 0) * 100,
      color: '#10b981' // Green
    },
    {
      name: 'Specificity',
      value: (metrics.specificity || 0) * 100,
      color: '#3b82f6' // Blue
    }
  ];

  return (
    <div className="bg-gray-800 rounded-lg shadow-md p-6 border border-gray-700">
      <h3 className="text-lg font-bold mb-6 text-white uppercase tracking-wider">Detection Performance</h3>

      {/* Metrics Chart */}
      <div className="h-[300px] w-full mb-8">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
            <XAxis dataKey="name" stroke="#9ca3af" tick={{ fontSize: 12 }} />
            <YAxis 
                domain={[0, 100]} 
                stroke="#9ca3af" 
                tick={{ fontSize: 12 }}
                label={{ value: 'Accuracy (%)', angle: -90, position: 'insideLeft', fill: '#9ca3af', style: { textAnchor: 'middle' } }} 
            />
            <Tooltip 
                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', color: '#f3f4f6' }}
                itemStyle={{ color: '#f3f4f6' }}
                formatter={(value: number) => [`${value.toFixed(2)}%`, 'Accuracy']} 
            />
            <Bar dataKey="value" radius={[4, 4, 0, 0]}>
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Confusion Matrix Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div className="bg-gray-900/50 p-4 rounded-lg border border-gray-700">
          <div className="text-2xl font-mono font-bold text-green-400">{metrics.true_positives}</div>
          <div className="text-[10px] text-gray-500 uppercase font-bold">True Positives</div>
        </div>
        <div className="bg-gray-900/50 p-4 rounded-lg border border-gray-700">
          <div className="text-2xl font-mono font-bold text-blue-400">{metrics.true_negatives}</div>
          <div className="text-[10px] text-gray-500 uppercase font-bold">True Negatives</div>
        </div>
        <div className="bg-gray-900/50 p-4 rounded-lg border border-gray-700">
          <div className="text-2xl font-mono font-bold text-red-400">{metrics.false_positives}</div>
          <div className="text-[10px] text-gray-500 uppercase font-bold">False Positives</div>
        </div>
        <div className="bg-gray-900/50 p-4 rounded-lg border border-gray-700">
          <div className="text-2xl font-mono font-bold text-yellow-400">{metrics.false_negatives}</div>
          <div className="text-[10px] text-gray-500 uppercase font-bold">False Negatives</div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="flex justify-between items-center pt-4 border-t border-gray-700 text-xs text-gray-500">
        <div>Total Verified Queries: <span className="text-white font-mono">{metrics.total_queries}</span></div>
        <div className="italic">Data for: {timeRange === 'all' ? 'All Time' : `Last ${timeRange}`}</div>
      </div>
    </div>
  );
};

export default DetectorMetrics;
