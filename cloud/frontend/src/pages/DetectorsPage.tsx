import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { useForm, Controller, useFieldArray } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import KeyValueEditor from '../components/KeyValueEditor';

// --- Zod Schema for Form Validation ---

const DetectorCreateSchema = z.object({
  name: z.string().min(3, "Name must be at least 3 characters").max(128),
  description: z.string().max(500).optional().or(z.literal('')),
  query_text: z.string().max(200).optional().or(z.literal('')),
  group_name: z.string().max(128).optional().or(z.literal('')),
  metadata: z.record(z.any()).nullable().optional(),
  mode: z.enum(["BINARY", "MULTICLASS", "COUNTING", "BOUNDING_BOX"]),
  class_names: z.array(z.string().min(1, "Class name cannot be empty")).optional(),
  confidence_threshold: z.number().min(0).max(1).default(0.85),
  edge_inference_profile: z.enum(["default", "offline", "aggressive"]).default("default"),
  patience_time: z.number().min(0).max(300).default(30.0),
  min_time_between_escalations: z.number().min(0).max(60).default(2.0),
  mode_configuration: z.record(z.any()).nullable().optional(),
  pipeline_config: z.string().optional().or(z.literal('')),
  max_count: z.number().positive().optional(),
  max_num_bboxes: z.number().positive().optional(),
}).refine((data) => {
  if (data.mode !== "BINARY") {
    if (!data.class_names || data.class_names.length === 0) return false;
    if (data.mode === "MULTICLASS" && data.class_names.length < 2) return false;
  }
  return true;
}, {
  message: "At least one class name is required (minimum 2 for MULTICLASS)",
  path: ["class_names"],
});

type DetectorCreateFormData = z.infer<typeof DetectorCreateSchema>;

interface Detector {
  id: string;
  name: string;
  description?: string;
  query_text?: string;
  group_name?: string;
  model_blob_path?: string;
  primary_model_blob_path?: string;
  oodd_model_blob_path?: string;
  created_at?: string;
  config?: {
    mode?: string;
    confidence_threshold?: number;
  };
}

// --- Helper Components ---

const ModeCard = ({ mode, currentMode, onSelect, icon, label, description, examples }: any) => {
  const isSelected = mode === currentMode;
  return (
    <div 
      onClick={() => onSelect(mode)}
      className={`cursor-pointer p-4 rounded-lg border-2 transition-all ${
        isSelected ? 'border-blue-500 bg-blue-900/20' : 'border-gray-700 bg-gray-800 hover:border-gray-600'
      }`}
    >
      <div className="flex items-center space-x-3 mb-2">
        <span className="text-2xl">{icon}</span>
        <h3 className="font-bold text-white">{label}</h3>
        {isSelected && <span className="ml-auto text-blue-400">✓</span>}
      </div>
      <p className="text-xs text-gray-400 mb-2">{description}</p>
      <div className="text-[10px] text-gray-500 italic">
        e.g., {examples.join(', ')}
      </div>
    </div>
  );
};

const DetectorsPage: React.FC = () => {
  const [detectors, setDetectors] = useState<Detector[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [groups, setGroups] = useState<string[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<string>('');
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    control,
    watch,
    setValue,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<DetectorCreateFormData>({
    resolver: zodResolver(DetectorCreateSchema),
    defaultValues: {
      mode: "BINARY",
      confidence_threshold: 0.85,
      edge_inference_profile: "default",
      patience_time: 30.0,
      min_time_between_escalations: 2.0,
      class_names: [],
    }
  });

  const { fields, append, remove } = useFieldArray({
    control,
    name: "class_names" as any,
  });

  const selectedMode = watch("mode");

  const fetchDetectors = async () => {
    setIsLoading(true);
    try {
      const params: Record<string, any> = {};
      if (selectedGroup) params.group_name = selectedGroup;
      const res = await axios.get<Detector[]>('/detectors', { params });
      setDetectors(res.data);
    } catch (err) {
      toast.error('Failed to fetch detectors');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchGroups = async () => {
    try {
      const res = await axios.get<string[]>('/detectors/groups');
      setGroups(res.data);
    } catch (err) {
      console.error('Failed to fetch groups:', err);
    }
  };

  const handleDeleteDetector = async (detectorId: string, detectorName: string) => {
    try {
      await axios.delete(`/detectors/${detectorId}`);
      toast.success(`Detector "${detectorName}" deleted successfully`);
      setDeleteConfirm(null);
      fetchDetectors();
      fetchGroups();
    } catch (err) {
      toast.error('Failed to delete detector');
      console.error('Error deleting detector:', err);
    }
  };

  useEffect(() => {
    fetchDetectors();
    fetchGroups();
  }, []);

  useEffect(() => {
    fetchDetectors();
  }, [selectedGroup]);

  const onSubmit = async (data: DetectorCreateFormData) => {
    try {
      // Build mode_configuration based on mode type
      let mode_configuration = null;
      if (data.mode === "COUNTING" && data.max_count) {
        mode_configuration = {
          class_name: data.class_names?.[0] || "",
          max_count: data.max_count
        };
      } else if (data.mode === "BOUNDING_BOX" && data.max_num_bboxes) {
        mode_configuration = {
          class_name: data.class_names?.[0] || "",
          max_num_bboxes: data.max_num_bboxes
        };
      }

      // Clean up data before sending to backend
      const payload = {
        name: data.name,
        description: data.description || null,
        query_text: data.query_text || null,
        group_name: data.group_name || null,
        metadata: data.metadata || null,
        mode: data.mode,
        class_names: data.mode === "BINARY" ? null : data.class_names,
        confidence_threshold: data.confidence_threshold,
        edge_inference_profile: data.edge_inference_profile,
        patience_time: data.patience_time,
        min_time_between_escalations: data.min_time_between_escalations,
        mode_configuration: mode_configuration,
        pipeline_config: data.pipeline_config || null,
      };

      const res = await axios.post<Detector>('/detectors/', payload);
      toast.success(`Detector "${res.data.name}" created successfully!`);
      setShowForm(false);
      reset();
      fetchDetectors();
    } catch (err) {
      toast.error('Failed to create detector');
      console.error('Error creating detector:', err);
    }
  };

  return (
    <div className="p-8 bg-gray-900 text-gray-300 min-h-screen">
      <ToastContainer position="top-right" autoClose={5000} hideProgressBar={false} />
      
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-white">Detectors</h1>
        {!showForm && (
          <button 
            onClick={() => setShowForm(true)}
            className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-6 rounded-md transition"
          >
            + Create New Detector
          </button>
        )}
      </div>

      {showForm && (
        <div className="bg-gray-800 rounded-lg shadow-xl p-8 mb-8 border border-gray-700 animate-fadeIn">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold text-white">New Detector Configuration</h2>
            <button onClick={() => setShowForm(false)} className="text-gray-500 hover:text-gray-300">✕</button>
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
            {/* Section 1: Basic Information */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-blue-400 border-b border-gray-700 pb-2 uppercase tracking-wider">
                1. Basic Information
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Detector Name *</label>
                  <input
                    {...register("name")}
                    type="text"
                    placeholder="e.g., Vehicle Detection - Lot A"
                    className={`w-full rounded-md bg-gray-700 border-gray-600 text-white p-2 focus:ring-blue-500 focus:border-blue-500 ${errors.name ? 'border-red-500' : ''}`}
                  />
                  {errors.name && <p className="text-red-500 text-xs mt-1">{errors.name.message}</p>}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Query Text (Recommended)</label>
                  <input
                    {...register("query_text")}
                    type="text"
                    placeholder="e.g., Is there a vehicle in the space?"
                    className="w-full rounded-md bg-gray-700 border-gray-600 text-white p-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <p className="text-[10px] text-gray-500 mt-1 italic">💡 Helps human reviewers understand the context</p>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Description</label>
                <textarea
                  {...register("description")}
                  rows={2}
                  placeholder="What does this detector do? Where is it used?"
                  className="w-full rounded-md bg-gray-700 border-gray-600 text-white p-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Detector Group (Optional)</label>
                <input
                  {...register("group_name")}
                  type="text"
                  placeholder="e.g., Building A Security, Production Line 1"
                  className="w-full rounded-md bg-gray-700 border-gray-600 text-white p-2 focus:ring-blue-500 focus:border-blue-500"
                />
                <p className="text-[10px] text-gray-500 mt-1 italic">💡 Organize detectors into logical groups</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Metadata (Optional)</label>
                <Controller
                  name="metadata"
                  control={control}
                  render={({ field }) => (
                    <KeyValueEditor
                      value={field.value}
                      onChange={field.onChange}
                      placeholder='{"hub_id": "hub-123", "location": "Warehouse A"}'
                    />
                  )}
                />
                <p className="text-[10px] text-gray-500 mt-1 italic">💡 Store deployment info: hub_id, camera_id, location, contact, etc.</p>
              </div>
            </div>

            {/* Section 2: Detection Type */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-blue-400 border-b border-gray-700 pb-2 uppercase tracking-wider">
                2. Detection Type *
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <ModeCard 
                  mode="BINARY" currentMode={selectedMode} onSelect={(m:any) => setValue("mode", m)}
                  icon="🔵" label="BINARY" description="Yes/No questions" 
                  examples={["Is vehicle present?", "Is there a defect?"]}
                />
                <ModeCard 
                  mode="MULTICLASS" currentMode={selectedMode} onSelect={(m:any) => setValue("mode", m)}
                  icon="🎨" label="MULTICLASS" description="Categorize into types" 
                  examples={["sedan, truck, SUV", "crack, dent, good"]}
                />
                <ModeCard 
                  mode="COUNTING" currentMode={selectedMode} onSelect={(m:any) => setValue("mode", m)}
                  icon="🔢" label="COUNTING" description="Count instances" 
                  examples={["person", "product", "defect"]}
                />
                <ModeCard 
                  mode="BOUNDING_BOX" currentMode={selectedMode} onSelect={(m:any) => setValue("mode", m)}
                  icon="📦" label="BOUNDING BOX" description="Locate & classify" 
                  examples={["Detect vehicles", "Locate workers"]}
                />
              </div>
            </div>

            {/* Section 3: Classes (Conditional) */}
            {selectedMode !== "BINARY" && (
              <div className="space-y-4 animate-fadeIn">
                <h3 className="text-lg font-semibold text-blue-400 border-b border-gray-700 pb-2 uppercase tracking-wider">
                  3. Define Classes *
                </h3>
                <div className="bg-gray-700/30 p-4 rounded-lg border border-gray-700">
                  <div className="space-y-2 mb-4">
                    {fields.map((field, index) => (
                      <div key={field.id} className="flex items-center gap-2">
                        <input
                          {...register(`class_names.${index}` as const)}
                          placeholder="Enter class name"
                          className="flex-1 rounded-md bg-gray-700 border-gray-600 text-white p-2 text-sm focus:ring-blue-500"
                        />
                        <button
                          type="button"
                          onClick={() => remove(index)}
                          className="text-red-400 hover:text-red-300 p-2"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={() => append("")}
                    className="text-blue-400 hover:text-blue-300 text-sm font-bold flex items-center"
                  >
                    + Add Another Class
                  </button>
                  {errors.class_names && <p className="text-red-500 text-xs mt-2">{errors.class_names.message}</p>}
                </div>
              </div>
            )}

            {/* Section 3.5: Mode Configuration (Conditional) */}
            {selectedMode === "COUNTING" && (
              <div className="space-y-4 animate-fadeIn">
                <h3 className="text-lg font-semibold text-blue-400 border-b border-gray-700 pb-2 uppercase tracking-wider">
                  4. Counting Configuration
                </h3>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Maximum Expected Count (Optional)</label>
                  <input
                    type="number"
                    {...register("max_count", { valueAsNumber: true })}
                    placeholder="e.g., 100"
                    min="1"
                    className="w-full rounded-md bg-gray-700 border-gray-600 text-white p-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <p className="text-[10px] text-gray-500 mt-1 italic">💡 Set upper limit for count validation (alerts if exceeded)</p>
                </div>
              </div>
            )}

            {selectedMode === "BOUNDING_BOX" && (
              <div className="space-y-4 animate-fadeIn">
                <h3 className="text-lg font-semibold text-blue-400 border-b border-gray-700 pb-2 uppercase tracking-wider">
                  4. Bounding Box Configuration
                </h3>
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Maximum Bounding Boxes (Optional)</label>
                  <input
                    type="number"
                    {...register("max_num_bboxes", { valueAsNumber: true })}
                    placeholder="e.g., 50"
                    min="1"
                    className="w-full rounded-md bg-gray-700 border-gray-600 text-white p-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <p className="text-[10px] text-gray-500 mt-1 italic">💡 Limit number of detected objects per frame</p>
                </div>
              </div>
            )}

            {/* Section 4/5: Settings */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold text-blue-400 border-b border-gray-700 pb-2 uppercase tracking-wider">
                {selectedMode === "BINARY" ? "3. Settings" : selectedMode === "MULTICLASS" ? "4. Settings" : "5. Settings"}
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="block text-sm font-medium text-gray-400">Confidence Threshold</label>
                    <span className="text-blue-400 font-bold font-mono text-lg">{Math.round(watch("confidence_threshold") * 100)}%</span>
                  </div>
                  <Controller
                    name="confidence_threshold"
                    control={control}
                    render={({ field }) => (
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.01"
                        {...field}
                        onChange={(e) => field.onChange(parseFloat(e.target.value))}
                        className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-600"
                      />
                    )}
                  />
                  <div className="flex justify-between text-[10px] text-gray-500 mt-1">
                    <span>Sensitive (All escalate)</span>
                    <span>Conservative (Never escalate)</span>
                  </div>
                  <p className="text-[10px] text-gray-500 mt-2 italic">💡 Results below this threshold will be sent for human review</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Edge Inference Profile</label>
                  <select
                    {...register("edge_inference_profile")}
                    className="w-full rounded-md bg-gray-700 border-gray-600 text-white p-2 focus:ring-blue-500"
                  >
                    <option value="default">Default (Cloud Escalation Enabled)</option>
                    <option value="offline">Offline Mode (No Cloud Escalation)</option>
                    <option value="aggressive">Aggressive Escalation (High Accuracy)</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Advanced Toggle */}
            <div className="pt-2">
              <button 
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="text-gray-500 hover:text-gray-400 text-xs font-semibold flex items-center"
              >
                {showAdvanced ? '▼' : '▶'} Advanced Settings
              </button>
              
              {showAdvanced && (
                <div className="mt-4 p-4 bg-gray-900/50 rounded-lg border border-gray-800 space-y-6 animate-fadeIn">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label className="block text-sm font-medium text-gray-400 mb-1">Patience Time (seconds)</label>
                      <input
                        {...register("patience_time", { valueAsNumber: true })}
                        type="number"
                        step="0.1"
                        className="w-full rounded-md bg-gray-700 border-gray-600 text-white p-2 text-sm"
                      />
                      <p className="text-[10px] text-gray-500 mt-1">Debounce time between queries for this detector</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-400 mb-1">Min Time Between Escalations (s)</label>
                      <input
                        {...register("min_time_between_escalations", { valueAsNumber: true })}
                        type="number"
                        step="0.1"
                        className="w-full rounded-md bg-gray-700 border-gray-600 text-white p-2 text-sm"
                      />
                      <p className="text-[10px] text-gray-500 mt-1">Avoid flooding human reviewers</p>
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-400 mb-1">
                      Pipeline Configuration (Expert Only) <span className="text-orange-500 ml-1">⚠️</span>
                    </label>
                    <textarea
                      {...register("pipeline_config")}
                      rows={4}
                      placeholder='{"preprocessing": {...}, "inference": {...}}'
                      className="w-full rounded-md bg-gray-700 border-gray-600 text-white p-2 text-xs font-mono"
                    />
                    <p className="text-[10px] text-orange-400 mt-1">⚠️ Advanced users only: Custom AI pipeline configuration (JSON)</p>
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end space-x-4 pt-6 border-t border-gray-700">
              <button 
                type="button" 
                onClick={() => setShowForm(false)}
                className="bg-gray-700 hover:bg-gray-600 text-white font-bold py-2 px-6 rounded-md transition"
              >
                Cancel
              </button>
              <button 
                type="submit" 
                disabled={isSubmitting}
                className="bg-green-600 hover:bg-green-500 text-white font-bold py-2 px-8 rounded-md transition disabled:bg-gray-600"
              >
                {isSubmitting ? 'Creating...' : 'Create Detector'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-gray-800 rounded-lg p-4 mb-6 border border-gray-700">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <h3 className="text-xl font-semibold text-white">All Detectors</h3>
            <span className="text-sm text-gray-400">
              ({detectors.length} total)
            </span>
          </div>
          <div className="flex items-center gap-4">
            <select
              value={selectedGroup}
              onChange={(e) => setSelectedGroup(e.target.value)}
              className="px-3 py-2 rounded bg-gray-700 border border-gray-600 text-white text-sm focus:border-blue-500 focus:outline-none"
            >
              <option value="">All Groups</option>
              {groups.map(g => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Detector Cards Grid */}
      {isLoading ? (
        <div className="bg-gray-800 rounded-lg p-12 text-center border border-gray-700">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
          <p className="text-sm text-gray-500 mt-2">Loading detectors...</p>
        </div>
      ) : detectors.length === 0 ? (
        <div className="bg-gray-800 rounded-lg p-12 text-center border border-gray-700">
          <p className="text-gray-400 text-lg">
            {selectedGroup ? `No detectors in group "${selectedGroup}".` : 'No detectors found. Create one to get started!'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {detectors.map((det: any) => (
            <div
              key={det.id}
              className="bg-gray-800 rounded-lg overflow-hidden border border-gray-700 hover:border-gray-600 transition group relative"
            >
              {/* Delete Confirmation Overlay */}
              {deleteConfirm === det.id && (
                <div className="absolute inset-0 bg-gray-900/95 z-10 flex flex-col items-center justify-center p-4 rounded-lg">
                  <p className="text-white text-center mb-4">Delete "<span className="font-bold">{det.name}</span>"?</p>
                  <p className="text-gray-400 text-xs text-center mb-4">Historical data will be preserved.</p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setDeleteConfirm(null)}
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded text-sm"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => handleDeleteDetector(det.id, det.name)}
                      className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded text-sm"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              )}

              {/* Card Header */}
              <div className="p-4 border-b border-gray-700">
                <div className="flex items-center justify-between mb-2">
                  <span className={`px-2 py-1 text-xs font-semibold rounded uppercase ${
                    det.config?.mode === 'BINARY' ? 'bg-blue-900/50 text-blue-400' :
                    det.config?.mode === 'MULTICLASS' ? 'bg-purple-900/50 text-purple-400' :
                    det.config?.mode === 'COUNTING' ? 'bg-green-900/50 text-green-400' :
                    det.config?.mode === 'BOUNDING_BOX' ? 'bg-orange-900/50 text-orange-400' :
                    'bg-gray-700 text-gray-400'
                  }`}>
                    {det.config?.mode || 'UNKNOWN'}
                  </span>
                  <div className="flex items-center gap-2">
                    {det.primary_model_blob_path ? (
                      <span className="bg-green-900/30 text-green-400 text-[10px] font-bold px-2 py-0.5 rounded-full border border-green-800/50">
                        READY
                      </span>
                    ) : (
                      <span className="bg-yellow-900/30 text-yellow-400 text-[10px] font-bold px-2 py-0.5 rounded-full border border-yellow-800/50">
                        NO MODEL
                      </span>
                    )}
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setDeleteConfirm(det.id);
                      }}
                      className="p-1 hover:bg-red-900/50 rounded text-red-400 hover:text-red-300"
                      title="Delete detector"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
                <Link to={`/detectors/${det.id}/configure`} className="block">
                  <h3 className="font-bold text-white text-lg group-hover:text-blue-400 transition truncate">
                    {det.name}
                  </h3>
                  {det.query_text && (
                    <p className="text-sm text-blue-400 mt-1 truncate">{det.query_text}</p>
                  )}
                </Link>
              </div>

              {/* Card Body */}
              <Link to={`/detectors/${det.id}/configure`} className="block p-4">
                {/* Description */}
                {det.description && (
                  <p className="text-xs text-gray-400 mb-3 line-clamp-2">{det.description}</p>
                )}

                {/* Group Badge */}
                {det.group_name && (
                  <div className="mb-3">
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs bg-gray-700 text-gray-300 border border-gray-600">
                      <span className="mr-1">📁</span> {det.group_name}
                    </span>
                  </div>
                )}

                {/* Confidence Threshold */}
                {det.config?.confidence_threshold !== undefined && (
                  <div className="mb-2">
                    <div className="flex justify-between text-xs text-gray-400 mb-1">
                      <span>Confidence Threshold</span>
                      <span>{Math.round(det.config.confidence_threshold * 100)}%</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-1.5">
                      <div
                        className="h-1.5 rounded-full bg-blue-500"
                        style={{ width: `${det.config.confidence_threshold * 100}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Footer */}
                <div className="flex items-center justify-between pt-3 border-t border-gray-700 mt-3">
                  <span className="text-xs text-gray-500">
                    {det.created_at ? new Date(det.created_at).toLocaleDateString() : ''}
                  </span>
                  <span className="text-blue-400 text-sm font-medium group-hover:translate-x-1 transition-transform">
                    Configure →
                  </span>
                </div>
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DetectorsPage;