import React, { useState, useEffect } from 'react';

interface KeyValuePair {
  key: string;
  value: string;
}

interface KeyValueEditorProps {
  value: Record<string, any> | null | undefined;
  onChange: (value: Record<string, any> | null) => void;
  placeholder?: string;
}

const KeyValueEditor: React.FC<KeyValueEditorProps> = ({ value, onChange, placeholder }) => {
  const [mode, setMode] = useState<'pairs' | 'json'>('pairs');
  const [pairs, setPairs] = useState<KeyValuePair[]>([]);
  const [jsonText, setJsonText] = useState('');
  const [jsonError, setJsonError] = useState<string | null>(null);

  // Initialize from value
  useEffect(() => {
    if (value && typeof value === 'object') {
      const newPairs = Object.entries(value).map(([key, val]) => ({
        key,
        value: typeof val === 'string' ? val : JSON.stringify(val)
      }));
      setPairs(newPairs.length > 0 ? newPairs : [{ key: '', value: '' }]);
      setJsonText(JSON.stringify(value, null, 2));
    } else {
      setPairs([{ key: '', value: '' }]);
      setJsonText('{}');
    }
  }, []);

  // Convert pairs to object and notify parent
  const updateFromPairs = (newPairs: KeyValuePair[]) => {
    setPairs(newPairs);
    const obj: Record<string, any> = {};
    newPairs.forEach(pair => {
      if (pair.key.trim()) {
        // Try to parse value as JSON, otherwise keep as string
        try {
          obj[pair.key.trim()] = JSON.parse(pair.value);
        } catch {
          obj[pair.key.trim()] = pair.value;
        }
      }
    });
    onChange(Object.keys(obj).length > 0 ? obj : null);
    setJsonText(JSON.stringify(obj, null, 2));
  };

  // Update from JSON text
  const updateFromJson = (text: string) => {
    setJsonText(text);
    try {
      const parsed = JSON.parse(text);
      if (typeof parsed !== 'object' || Array.isArray(parsed)) {
        setJsonError('Must be a JSON object');
        return;
      }
      setJsonError(null);
      onChange(parsed);
      const newPairs = Object.entries(parsed).map(([key, val]) => ({
        key,
        value: typeof val === 'string' ? val : JSON.stringify(val)
      }));
      setPairs(newPairs.length > 0 ? newPairs : [{ key: '', value: '' }]);
    } catch (err: any) {
      setJsonError(err.message || 'Invalid JSON');
    }
  };

  const addPair = () => {
    updateFromPairs([...pairs, { key: '', value: '' }]);
  };

  const removePair = (index: number) => {
    const newPairs = pairs.filter((_, i) => i !== index);
    updateFromPairs(newPairs.length > 0 ? newPairs : [{ key: '', value: '' }]);
  };

  const updatePair = (index: number, field: 'key' | 'value', newValue: string) => {
    const newPairs = pairs.map((pair, i) =>
      i === index ? { ...pair, [field]: newValue } : pair
    );
    updateFromPairs(newPairs);
  };

  return (
    <div className="border border-gray-700 rounded-lg p-4 bg-gray-800/50">
      {/* Mode Toggle */}
      <div className="flex justify-between items-center mb-3">
        <div className="flex space-x-2">
          <button
            type="button"
            onClick={() => setMode('pairs')}
            className={`px-3 py-1 text-xs rounded ${
              mode === 'pairs'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
            }`}
          >
            Key-Value Pairs
          </button>
          <button
            type="button"
            onClick={() => setMode('json')}
            className={`px-3 py-1 text-xs rounded ${
              mode === 'json'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
            }`}
          >
            JSON
          </button>
        </div>
        {mode === 'pairs' && (
          <button
            type="button"
            onClick={addPair}
            className="text-blue-400 hover:text-blue-300 text-xs font-bold"
          >
            + Add Pair
          </button>
        )}
      </div>

      {/* Pairs Mode */}
      {mode === 'pairs' && (
        <div className="space-y-2">
          {pairs.length === 0 ? (
            <div className="text-center py-4 text-gray-500 text-xs">
              No metadata. Click "+ Add Pair" to start.
            </div>
          ) : (
            pairs.map((pair, index) => (
              <div key={index} className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="key"
                  value={pair.key}
                  onChange={(e) => updatePair(index, 'key', e.target.value)}
                  className="flex-1 rounded-md bg-gray-700 border-gray-600 text-white p-2 text-xs placeholder-gray-500"
                />
                <span className="text-gray-500">=</span>
                <input
                  type="text"
                  placeholder="value"
                  value={pair.value}
                  onChange={(e) => updatePair(index, 'value', e.target.value)}
                  className="flex-1 rounded-md bg-gray-700 border-gray-600 text-white p-2 text-xs placeholder-gray-500"
                />
                <button
                  type="button"
                  onClick={() => removePair(index)}
                  className="text-red-400 hover:text-red-300 p-2 text-sm"
                  title="Remove"
                >
                  ✕
                </button>
              </div>
            ))
          )}
        </div>
      )}

      {/* JSON Mode */}
      {mode === 'json' && (
        <div>
          <textarea
            value={jsonText}
            onChange={(e) => updateFromJson(e.target.value)}
            rows={6}
            placeholder={placeholder || '{\n  "key1": "value1",\n  "key2": "value2"\n}'}
            className={`w-full rounded-md bg-gray-700 border-gray-600 text-white p-2 text-xs font-mono ${
              jsonError ? 'border-red-500' : ''
            }`}
          />
          {jsonError && (
            <p className="text-red-500 text-xs mt-1">⚠️ {jsonError}</p>
          )}
        </div>
      )}
    </div>
  );
};

export default KeyValueEditor;
