import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useForm, Controller } from 'react-hook-form';
import axios from 'axios';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import DetectorMetrics from '../components/DetectorMetrics';

// --- Zod Schemas for Form Validation (matching backend) ---

const EdgeInferenceConfigSchema = z.object({
  always_return_edge_prediction: z.boolean().default(false),
  disable_cloud_escalation: z.boolean().default(false),
  min_time_between_escalations: z.number().min(0).default(2.0),
});

const ModelInputConfigSchema = z.object({
  width: z.number().min(1).default(640),
  height: z.number().min(1).default(640),
  color_space: z.enum(["RGB", "BGR", "GRAYSCALE"]).default("RGB"),
  normalization_mean: z.string().default("0.485, 0.456, 0.406"),
  normalization_std: z.string().default("0.229, 0.224, 0.225"),
});

const ModelOutputConfigSchema = z.object({
  output_format: z.enum(["probabilities", "logits", "bboxes", "segmentation"]).default("probabilities"),
  apply_sigmoid: z.boolean().default(false),
  apply_softmax: z.boolean().default(false),
  bbox_format: z.enum(["xyxy", "xywh", "cxcywh"]).optional(),
  bbox_normalized: z.boolean().optional(),
});

const DetectionParamsSchema = z.object({
  nms_threshold: z.number().min(0).max(1).default(0.45),
  iou_threshold: z.number().min(0).max(1).default(0.50),
  max_detections: z.number().min(1).max(1000).default(100),
  min_score: z.number().min(0).max(1).default(0.25),
  min_object_size: z.number().min(0).default(0),
  max_object_size: z.number().min(0).default(999999),
});

const DetectorConfigSchema = z.object({
  mode: z.string().default('OPEN_VOCAB'),
  open_vocab_prompts: z.array(z.string()).nullable().optional().transform(val => val ?? []),
  class_names: z.array(z.string()).nullable().optional().transform(val => val ?? []),
  per_class_thresholds: z.record(z.string(), z.number().min(0).max(1)).nullable().optional(),
  confidence_threshold: z.number().min(0).max(1).default(0.85),
  patience_time: z.number().min(0).default(30.0),

  model_input_config: ModelInputConfigSchema.nullable().optional().transform(val => val ?? {}),
  model_output_config: ModelOutputConfigSchema.nullable().optional().transform(val => val ?? {}),
  detection_params: DetectionParamsSchema.nullable().optional(),

  edge_inference_config: EdgeInferenceConfigSchema.nullable().optional().transform(val => val ?? {}),
});

type DetectorConfigFormData = z.infer<typeof DetectorConfigSchema>;

// --- Helper Components ---
const Card = ({ title, children }: { title: string, children: React.ReactNode }) => (
    <div className="bg-gray-800 rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-xl font-semibold text-white mb-4">{title}</h2>
        <div className="space-y-4">{children}</div>
    </div>
);

const Input = ({ label, id, ...props }: any) => (
    <div>
        <label htmlFor={id} className="block text-sm font-medium text-gray-400">{label}</label>
        <input id={id} {...props} className="mt-1 block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm" />
    </div>
);

const Select = ({ label, id, children, ...props }: any) => (
    <div>
        <label htmlFor={id} className="block text-sm font-medium text-gray-400">{label}</label>
        <select id={id} {...props} className="mt-1 block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm">
            {children}
        </select>
    </div>
);

const Checkbox = ({ label, id, ...props }: any) => (
    <div className="flex items-center">
        <input id={id} {...props} type="checkbox" className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-600 rounded" />
        <label htmlFor={id} className="ml-2 block text-sm text-gray-300">{label}</label>
    </div>
);


interface Deployment {
    id: string;
    hub_id: string;
    hub_name?: string;
    status: string;
    deployed_at: string;
}

const DetectorConfigPage = () => {
    const { id: detectorId } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const [detector, setDetector] = useState<any>(null);
    const [deployments, setDeployments] = useState<Deployment[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isUploadingPrimary, setIsUploadingPrimary] = useState(false);
    const [isUploadingOODD, setIsUploadingOODD] = useState(false);
    const [groupSuggestions, setGroupSuggestions] = useState<string[]>([]);

    // Test Interface State
    const [testImage, setTestImage] = useState<File | null>(null);
    const [testResult, setTestResult] = useState<any>(null);
    const [isTestRunning, setIsTestRunning] = useState(false);
    const [metricsTimeRange, setMetricsTimeRange] = useState('7d');

    // Tab State
    const [activeTab, setActiveTab] = useState<'config' | 'alerts' | 'training'>('config');

    const {
        handleSubmit,
        control,
        reset,
        watch,
        formState: { errors, isSubmitting },
    } = useForm<any>({
        resolver: zodResolver(DetectorConfigSchema.extend({
            name: z.string().min(1, "Name is required"),
            description: z.string().optional(),
            group_name: z.string().max(128).optional().or(z.literal('')),
        })),
    });

    const fetchData = async () => {
        if (!detectorId) return;
        setIsLoading(true);
        try {
            const [detectorRes, configRes, deploymentsRes, groupsRes] = await Promise.all([
                axios.get(`/detectors/${detectorId}`),
                axios.get(`/detectors/${detectorId}/config`),
                axios.get(`/deployments?detector_id=${detectorId}`),
                axios.get('/detectors/groups'),
            ]);
            setDetector(detectorRes.data);
            setDeployments(deploymentsRes.data);
            setGroupSuggestions(groupsRes.data);
            reset({
                ...configRes.data,
                name: detectorRes.data.name,
                description: detectorRes.data.description,
                group_name: detectorRes.data.group_name || '',
            });
        } catch (error) {
            toast.error('Failed to fetch detector data.');
            console.error('Error fetching data:', error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, [detectorId, reset]);

    const handleModelUpload = async (e: React.ChangeEvent<HTMLInputElement>, type: 'primary' | 'oodd') => {
        const file = e.target.files?.[0];
        if (!file || !detectorId) return;

        const formData = new FormData();
        formData.append('file', file);
        formData.append('model_type', type);

        if (type === 'primary') setIsUploadingPrimary(true);
        else setIsUploadingOODD(true);

        try {
            await axios.post(`/detectors/${detectorId}/model?model_type=${type}`, formData);
            toast.success(`${type === 'primary' ? 'Primary' : 'OODD'} model uploaded successfully!`);
            // Refresh detector data to show new path
            const res = await axios.get(`/detectors/${detectorId}`);
            setDetector(res.data);
        } catch (error) {
            toast.error(`Failed to upload ${type} model.`);
        } finally {
            if (type === 'primary') setIsUploadingPrimary(false);
            else setIsUploadingOODD(false);
        }
    };

    const handleRemoveModel = async (modelType: 'primary' | 'oodd') => {
        const modelName = modelType === 'primary' ? 'Primary Model' : 'OODD Model';
        const confirmMessage = modelType === 'oodd'
            ? `Remove OODD model reference from this detector?\n\nDetector will use Primary model only.\n\nNote: The model file remains in storage.`
            : `Remove Primary model reference from this detector?\n\nWARNING: Detector will stop working until you assign a new model!\n\nNote: The model file remains in storage.`;

        if (!window.confirm(confirmMessage)) return;

        try {
            await axios.delete(`/detectors/${detectorId}/model`, {
                params: { model_type: modelType }
            });
            toast.success(`${modelName} unlinked successfully.`);
            const res = await axios.get(`/detectors/${detectorId}`);
            setDetector(res.data);
        } catch (error: any) {
            toast.error(error.response?.data?.detail || `Failed to remove ${modelName}`);
        }
    };

    const handleTestImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            setTestImage(file);
            setTestResult(null); // Clear previous results
        }
    };

    const runTest = async () => {
        if (!testImage || !detectorId) return;

        setIsTestRunning(true);
        try {
            const formData = new FormData();
            formData.append('image', testImage);

            const response = await axios.post(`/detectors/${detectorId}/test`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            setTestResult(response.data);
            toast.success('Test completed successfully!');
        } catch (error) {
            toast.error('Test failed. Check if models are uploaded.');
            console.error('Test error:', error);
        } finally {
            setIsTestRunning(false);
        }
    };

    const onSubmit = async (data: any, shouldDeploy = false) => {
        try {
            const { name, description, group_name, ...configData } = data;

            // 1. Save Detector Info (including group)
            await axios.put(`/detectors/${detectorId}`, { name, description, group_name: group_name || null });

            // 2. Save Detector Config
            await axios.put(`/detectors/${detectorId}/config`, configData);

            toast.success('Configuration saved successfully!');

            // 3. Optional: Trigger Redeployment
            if (shouldDeploy) {
                await axios.post(`/deployments/redeploy?detector_id=${detectorId}`);
                toast.success('Redeployment triggered successfully!');
            }

            navigate('/detectors');
        } catch (error: any) {
            const errorMsg = error.response?.data?.detail || 'Failed to save configuration.';
            toast.error(errorMsg);
            console.error('Error saving data:', error);
        }
    };

    // Handle form validation errors
    const onFormError = (formErrors: any) => {
        console.error('Form validation errors:', formErrors);
        const errorMessages = Object.entries(formErrors)
            .map(([field, error]: [string, any]) => `${field}: ${error.message}`)
            .join(', ');
        toast.error(`Validation failed: ${errorMessages || 'Please check the form fields.'}`);
    };
    
    if (isLoading) {
        return <div className="p-8 text-white">Loading configuration...</div>;
    }

    if (!detector) {
        return <div className="p-8 text-red-500">Detector not found.</div>;
    }

    return (
        <div className="p-8 bg-gray-900 text-gray-300 min-h-screen">
            <ToastContainer position="top-right" autoClose={5000} hideProgressBar={false} />
            <header className="mb-8 flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-white">Detector Configuration</h1>
                    <p className="text-gray-400">ID: <span className="font-mono bg-gray-700 px-2 py-1 rounded text-xs">{detectorId}</span></p>
                </div>
                <div className="flex space-x-4">
                    <button type="button" onClick={() => navigate('/detectors')} className="bg-gray-700 hover:bg-gray-600 text-white font-bold py-2 px-4 rounded transition">
                        Cancel
                    </button>
                    <button type="button" onClick={handleSubmit((data) => onSubmit(data, false), onFormError)} disabled={isSubmitting} className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-4 rounded transition disabled:bg-gray-500">
                        {isSubmitting ? 'Saving...' : 'Save'}
                    </button>
                    <button type="button" onClick={handleSubmit((data) => onSubmit(data, true), onFormError)} disabled={isSubmitting} className="bg-green-600 hover:bg-green-500 text-white font-bold py-2 px-4 rounded transition disabled:bg-gray-500">
                        {isSubmitting ? 'Deploying...' : 'Save & Deploy'}
                    </button>
                </div>
            </header>

            {/* Tabs */}
            <div className="mb-6 border-b border-gray-700">
                <nav className="flex space-x-8">
                    <button
                        onClick={() => setActiveTab('config')}
                        className={`py-4 px-1 border-b-2 font-medium text-sm transition ${
                            activeTab === 'config'
                                ? 'border-blue-500 text-blue-500'
                                : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-300'
                        }`}
                    >
                        Configuration
                    </button>
                    <button
                        onClick={() => setActiveTab('alerts')}
                        className={`py-4 px-1 border-b-2 font-medium text-sm transition ${
                            activeTab === 'alerts'
                                ? 'border-blue-500 text-blue-500'
                                : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-300'
                        }`}
                    >
                        Alerts
                    </button>
                    <button
                        onClick={() => setActiveTab('training')}
                        className={`py-4 px-1 border-b-2 font-medium text-sm transition ${
                            activeTab === 'training'
                                ? 'border-green-500 text-green-400'
                                : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-300'
                        }`}
                    >
                        Model Training
                    </button>
                </nav>
            </div>

            {activeTab === 'config' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Left Column: General Information, Performance Analytics, Model Specifications, Model Management */}
                <div className="space-y-8">
                    <Card title="General Information">
                        <Controller
                            name="name"
                            control={control}
                            render={({ field }) => <Input label="Detector Name" id="name" {...field} error={errors.name?.message} />}
                        />
                        <Controller
                            name="description"
                            control={control}
                            render={({ field }) => (
                                <div>
                                    <label htmlFor="description" className="block text-sm font-medium text-gray-400">Description</label>
                                    <textarea id="description" {...field} className="mt-1 block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm h-24" />
                                </div>
                            )}
                        />
                        <Controller
                            name="group_name"
                            control={control}
                            render={({ field }) => (
                                <div>
                                    <label htmlFor="group_name" className="block text-sm font-medium text-gray-400">Detector Group</label>
                                    <input
                                        id="group_name"
                                        {...field}
                                        list="group-suggestions"
                                        placeholder="e.g., Building A Security, Production Line 1"
                                        className="mt-1 block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                                    />
                                    <datalist id="group-suggestions">
                                        {groupSuggestions.map(g => (
                                            <option key={g} value={g} />
                                        ))}
                                    </datalist>
                                    <p className="text-xs text-gray-500 mt-1">Organize detectors into logical groups for filtering</p>
                                </div>
                            )}
                        />
                    </Card>

                    <Card title="Performance Analytics">
                        <div className="flex justify-end mb-2">
                            <select
                                value={metricsTimeRange}
                                onChange={(e) => setMetricsTimeRange(e.target.value)}
                                className="bg-gray-700 border border-gray-600 text-gray-300 text-[10px] rounded px-2 py-1"
                            >
                                <option value="1d">24h</option>
                                <option value="7d">7d</option>
                                <option value="30d">30d</option>
                                <option value="all">All</option>
                            </select>
                        </div>
                        <DetectorMetrics detectorId={detectorId!} timeRange={metricsTimeRange} />
                    </Card>

                    {/* Model Specifications moved to left column */}
                    <Card title="Model Specifications">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Input Configuration */}
                        <div className="space-y-4">
                          <h3 className="text-sm font-bold text-white uppercase tracking-wider border-b border-gray-600 pb-2">
                            Input Configuration
                          </h3>

                          <div className="grid grid-cols-2 gap-4">
                            <Controller
                              name="model_input_config.width"
                              control={control}
                              render={({ field }) => (
                                <Input
                                  label="Input Width (px)"
                                  type="number"
                                  {...field}
                                  onChange={e => field.onChange(parseInt(e.target.value))}
                                  placeholder="640"
                                />
                              )}
                            />
                            <Controller
                              name="model_input_config.height"
                              control={control}
                              render={({ field }) => (
                                <Input
                                  label="Input Height (px)"
                                  type="number"
                                  {...field}
                                  onChange={e => field.onChange(parseInt(e.target.value))}
                                  placeholder="640"
                                />
                              )}
                            />
                          </div>

                          <Controller
                            name="model_input_config.color_space"
                            control={control}
                            render={({ field }) => (
                              <Select label="Color Space" {...field}>
                                <option value="RGB">RGB</option>
                                <option value="BGR">BGR (OpenCV default)</option>
                                <option value="GRAYSCALE">Grayscale</option>
                              </Select>
                            )}
                          />

                          <Controller
                            name="model_input_config.normalization_mean"
                            control={control}
                            render={({ field }) => (
                              <div>
                                <label className="block text-sm font-medium text-gray-400">Normalization Mean (R,G,B)</label>
                                <input
                                  type="text"
                                  {...field}
                                  placeholder="0.485, 0.456, 0.406"
                                  className="mt-1 block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                                />
                                <p className="text-xs text-gray-500 mt-1">ImageNet defaults shown</p>
                              </div>
                            )}
                          />

                          <Controller
                            name="model_input_config.normalization_std"
                            control={control}
                            render={({ field }) => (
                              <div>
                                <label className="block text-sm font-medium text-gray-400">Normalization Std (R,G,B)</label>
                                <input
                                  type="text"
                                  {...field}
                                  placeholder="0.229, 0.224, 0.225"
                                  className="mt-1 block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                                />
                              </div>
                            )}
                          />
                        </div>

                        {/* Output Configuration */}
                        <div className="space-y-4">
                          <h3 className="text-sm font-bold text-white uppercase tracking-wider border-b border-gray-600 pb-2">
                            Output Configuration
                          </h3>

                          <Controller
                            name="model_output_config.output_format"
                            control={control}
                            render={({ field }) => (
                              <Select label="Output Format" {...field}>
                                <option value="probabilities">Probabilities (0-1)</option>
                                <option value="logits">Logits (raw scores)</option>
                                <option value="bboxes">Bounding Boxes</option>
                                <option value="segmentation">Segmentation Masks</option>
                              </Select>
                            )}
                          />

                          <Controller
                            name="model_output_config.apply_sigmoid"
                            control={control}
                            render={({ field }) => (
                              <Checkbox
                                label="Apply Sigmoid to Outputs"
                                checked={field.value || false}
                                onChange={e => field.onChange(e.target.checked)}
                              />
                            )}
                          />

                          <Controller
                            name="model_output_config.apply_softmax"
                            control={control}
                            render={({ field }) => (
                              <Checkbox
                                label="Apply Softmax to Outputs"
                                checked={field.value || false}
                                onChange={e => field.onChange(e.target.checked)}
                              />
                            )}
                          />

                          {watch("mode") === "BOUNDING_BOX" && (
                            <>
                              <Controller
                                name="model_output_config.bbox_format"
                                control={control}
                                render={({ field }) => (
                                  <Select label="Bounding Box Format" {...field}>
                                    <option value="xyxy">XYXY (x1, y1, x2, y2)</option>
                                    <option value="xywh">XYWH (x, y, width, height)</option>
                                    <option value="cxcywh">CXCYWH (center_x, center_y, width, height)</option>
                                  </Select>
                                )}
                              />

                              <Controller
                                name="model_output_config.bbox_normalized"
                                control={control}
                                render={({ field }) => (
                                  <Checkbox
                                    label="Coordinates Normalized (0-1)"
                                    checked={field.value || false}
                                    onChange={e => field.onChange(e.target.checked)}
                                  />
                                )}
                              />
                            </>
                          )}
                        </div>
                      </div>
                    </Card>

                    {/* Model Management moved to left column */}
                    <Card title="Model Management">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="bg-gray-700 p-4 rounded-lg border border-gray-700">
                                <h3 className="text-sm font-bold text-white mb-2 uppercase tracking-wider">Primary Inference Model</h3>
                                <p className="text-xs text-gray-400 mb-4 truncate" title={detector.primary_model_blob_path}>
                                    {detector.primary_model_blob_path || 'No model uploaded'}
                                </p>
                                <div className="flex gap-2">
                                    <label className="flex-1">
                                        <span className="sr-only">Choose primary model</span>
                                        <input type="file" onChange={(e) => handleModelUpload(e, 'primary')} disabled={isUploadingPrimary}
                                            className="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-500 cursor-pointer disabled:opacity-50" />
                                    </label>
                                    {detector.primary_model_blob_path && (
                                        <button onClick={() => handleRemoveModel('primary')} className="bg-red-600 hover:bg-red-500 text-white text-xs font-bold px-3 py-2 rounded-full transition">Unlink</button>
                                    )}
                                </div>
                                {isUploadingPrimary && <p className="text-xs text-blue-400 mt-2 animate-pulse">Uploading primary model...</p>}
                            </div>

                            <div className="bg-gray-700 p-4 rounded-lg border border-gray-700">
                                <h3 className="text-sm font-bold text-white mb-2 uppercase tracking-wider">OODD Model (Ground Truth)</h3>
                                <p className="text-xs text-gray-400 mb-4 truncate" title={detector.oodd_model_blob_path}>
                                    {detector.oodd_model_blob_path || 'No model uploaded'}
                                </p>
                                <div className="flex gap-2">
                                    <label className="flex-1">
                                        <span className="sr-only">Choose OODD model</span>
                                        <input type="file" onChange={(e) => handleModelUpload(e, 'oodd')} disabled={isUploadingOODD}
                                            className="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-purple-600 file:text-white hover:file:bg-purple-500 cursor-pointer disabled:opacity-50" />
                                    </label>
                                    {detector.oodd_model_blob_path && (
                                        <button onClick={() => handleRemoveModel('oodd')} className="bg-orange-600 hover:bg-orange-500 text-white text-xs font-bold px-3 py-2 rounded-full transition">Unlink</button>
                                    )}
                                </div>
                                {isUploadingOODD && <p className="text-xs text-purple-400 mt-2 animate-pulse">Uploading OODD model...</p>}
                            </div>
                        </div>
                    </Card>
                </div>

                {/* Right Column: Test Detector, Detection Logic, Edge Optimization, Quick Actions, Deployment Status */}
                <div className="space-y-8">
                    <Card title="Test Detector">
                      <div className="space-y-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-400 mb-2">
                            Upload Test Image
                          </label>
                          <input
                            type="file"
                            accept="image/*"
                            onChange={handleTestImageUpload}
                            className="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-purple-600 file:text-white hover:file:bg-purple-500 cursor-pointer"
                          />
                        </div>

                        <button
                          type="button"
                          onClick={runTest}
                          disabled={!testImage || isTestRunning}
                          className="w-full bg-purple-600 hover:bg-purple-500 text-white font-bold py-2 px-4 rounded disabled:bg-gray-600 disabled:cursor-not-allowed transition"
                        >
                          {isTestRunning ? "Running..." : "Run Inference Test"}
                        </button>

                        {testResult && (
                          <div className="mt-4 space-y-3">
                            <div className="bg-gray-700 p-3 rounded-md">
                              <h4 className="text-sm font-bold text-white mb-2">Results</h4>

                              {testResult.detections && testResult.detections.length > 0 ? (
                                <div className="space-y-2">
                                  {testResult.detections.map((det: any, idx: number) => (
                                    <div key={idx} className="flex justify-between items-center bg-gray-800 p-2 rounded">
                                      <span className="text-white font-mono text-sm">{det.class || det.label}</span>
                                      <span className={`font-bold ${det.confidence >= (detector?.config?.confidence_threshold || 0.85) ? 'text-green-400' : 'text-yellow-400'}`}>
                                        {(det.confidence * 100).toFixed(1)}%
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <p className="text-gray-400 text-sm italic">No detections</p>
                              )}
                            </div>

                            <div className="bg-gray-700 p-3 rounded-md">
                              <h4 className="text-sm font-bold text-white mb-2">Performance</h4>
                              <div className="space-y-1 text-sm">
                                <div className="flex justify-between">
                                  <span className="text-gray-400">Inference Time:</span>
                                  <span className="text-white font-mono">{testResult.inference_time_ms}ms</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-gray-400">Status:</span>
                                  <span className={testResult.would_escalate ? "text-yellow-400" : "text-green-400"}>
                                    {testResult.would_escalate ? "Would Escalate" : "Confident"}
                                  </span>
                                </div>
                              </div>
                            </div>

                            {testResult.annotated_image_url && (
                              <div>
                                <h4 className="text-sm font-bold text-white mb-2">Annotated Output</h4>
                                <img
                                  src={testResult.annotated_image_url}
                                  alt="Annotated detection"
                                  className="w-full rounded-md border border-gray-600"
                                />
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </Card>

                    <Card title="Detection Logic">
                            <Controller
                                name="mode"
                                control={control}
                                render={({ field }) => (
                                    <Select label="Operation Mode" id="mode" {...field}>
                                        <option value="OPEN_VOCAB">OPEN_VOCAB (Type what to detect)</option>
                                        <option value="BINARY">BINARY (Pass/Fail)</option>
                                        <option value="MULTICLASS">MULTICLASS (Classification)</option>
                                        <option value="COUNTING">COUNTING (Count objects)</option>
                                        <option value="BOUNDING_BOX">BOUNDING_BOX (Object detection)</option>
                                    </Select>
                                )}
                            />
                            
                            {/* Open-Vocab Prompts Editor */}
                            {watch("mode") === "OPEN_VOCAB" && (
                              <div className="mt-4">
                                <label className="block text-sm font-medium text-gray-400 mb-2">
                                  Detection Prompts
                                  <span className="text-gray-500 ml-2 font-normal">Type what to detect (no training needed)</span>
                                </label>
                                <Controller
                                  name="open_vocab_prompts"
                                  control={control}
                                  render={({ field }) => (
                                    <div className="space-y-2">
                                      {field.value && field.value.map((prompt: string, index: number) => (
                                        <div key={index} className="flex items-center gap-2">
                                          <input
                                            type="text"
                                            value={prompt}
                                            onChange={e => {
                                              const updated = [...(field.value || [])];
                                              updated[index] = e.target.value;
                                              field.onChange(updated);
                                            }}
                                            placeholder="e.g., person, fire, red truck"
                                            className="flex-1 bg-gray-700 text-white rounded px-3 py-1.5 text-sm border border-gray-600"
                                          />
                                          <button
                                            type="button"
                                            onClick={() => {
                                              const updated = (field.value || []).filter((_: string, i: number) => i !== index);
                                              field.onChange(updated);
                                            }}
                                            className="text-red-400 hover:text-red-300 text-sm px-2"
                                          >
                                            X
                                          </button>
                                        </div>
                                      ))}
                                      <button
                                        type="button"
                                        onClick={() => field.onChange([...(field.value || []), ''])}
                                        className="text-blue-400 hover:text-blue-300 text-sm"
                                      >
                                        + Add Prompt
                                      </button>
                                    </div>
                                  )}
                                />
                                <p className="text-xs text-gray-500 mt-2">
                                  Real-time detection runs continuously; use Analyze Scene for complex queries.
                                  No custom model upload needed for this mode.
                                </p>
                              </div>
                            )}

                            {/* Class Names Configuration */}
                            {(watch("mode") === "MULTICLASS" ||
                              watch("mode") === "COUNTING" ||
                              watch("mode") === "BOUNDING_BOX") && (
                              <div className="mt-4">
                                <label className="block text-sm font-medium text-gray-400 mb-2">
                                  Class Names
                                  <span className="text-red-400 ml-1">*</span>
                                </label>

                                <Controller
                                  name="class_names"
                                  control={control}
                                  rules={{
                                    validate: (value) => {
                                      if (!value || value.length === 0) {
                                        return "At least one class name is required for this mode";
                                      }
                                      if (value.length === 1 && watch("mode") === "MULTICLASS") {
                                        return "Multiclass mode requires at least 2 classes";
                                      }
                                      return true;
                                    }
                                  }}
                                  render={({ field }) => (
                                    <div className="space-y-2">
                                      {/* List of class names */}
                                      {field.value && field.value.map((className: string, index: number) => (
                                        <div key={index} className="flex items-center gap-2">
                                          <input
                                            type="text"
                                            value={className}
                                            onChange={(e) => {
                                              const newClassNames = [...field.value];
                                              newClassNames[index] = e.target.value;
                                              field.onChange(newClassNames);
                                            }}
                                            placeholder="Enter class name"
                                            className="flex-1 rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm px-3 py-2"
                                          />
                                          <button
                                            type="button"
                                            onClick={() => {
                                              const newClassNames = field.value.filter((_: string, i: number) => i !== index);
                                              field.onChange(newClassNames);
                                            }}
                                            className="text-red-400 hover:text-red-300 px-3 py-2"
                                            disabled={field.value.length === 1}
                                          >
                                            ✕ Remove
                                          </button>
                                        </div>
                                      ))}

                                      {/* Add class button */}
                                      <button
                                        type="button"
                                        onClick={() => {
                                          field.onChange([...(field.value || []), ""]);
                                        }}
                                        className="w-full bg-gray-700 hover:bg-gray-600 text-white font-medium py-2 px-4 rounded-md border border-gray-600 transition"
                                      >
                                        + Add Class
                                      </button>

                                      {errors.class_names && (
                                        <p className="text-red-400 text-sm mt-1">{errors.class_names.message}</p>
                                      )}
                                    </div>
                                  )}
                                />
                              </div>
                            )}

                            <Controller
                                name="confidence_threshold"
                                control={control}
                                render={({ field }) => (
                                    <div className="space-y-1 mt-4">
                                        <div className="flex justify-between">
                                            <label className="text-sm font-medium text-gray-400">Confidence Threshold</label>
                                            <span className="text-blue-400 font-bold">{Math.round(field.value * 100)}%</span>
                                        </div>
                                        <input 
                                            type="range"
                                            min="0"
                                            max="1"
                                            step="0.01"
                                            className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-600"
                                            {...field}
                                            onChange={e => field.onChange(parseFloat(e.target.value))}
                                        />
                                        <p className="text-xs text-gray-500">Results below this threshold will be escalated to the cloud for human review.</p>
                                    </div>
                                )}
                            />

                            {/* Detection Parameters for BOUNDING_BOX mode */}
                            {watch("mode") === "BOUNDING_BOX" && (
                              <div className="mt-4 p-4 bg-gray-700 rounded-md border border-gray-600">
                                <h3 className="text-sm font-bold text-white mb-3 uppercase tracking-wider">
                                  Object Detection Parameters
                                </h3>

                                <div className="space-y-3">
                                  <Controller
                                    name="detection_params.nms_threshold"
                                    control={control}
                                    render={({ field }) => (
                                      <div>
                                        <div className="flex justify-between items-center mb-1">
                                          <label className="text-sm font-medium text-gray-400">NMS Threshold</label>
                                          <span className="text-blue-400 font-mono text-sm">{field.value?.toFixed(2) || "0.45"}</span>
                                        </div>
                                        <input
                                          type="range"
                                          min="0"
                                          max="1"
                                          step="0.01"
                                          {...field}
                                          value={field.value || 0.45}
                                          onChange={e => field.onChange(parseFloat(e.target.value))}
                                          className="w-full h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer accent-blue-500"
                                        />
                                        <p className="text-xs text-gray-500 mt-1">
                                          Non-Maximum Suppression: Remove overlapping boxes (higher = more boxes kept)
                                        </p>
                                      </div>
                                    )}
                                  />

                                  <Controller
                                    name="detection_params.iou_threshold"
                                    control={control}
                                    render={({ field }) => (
                                      <div>
                                        <div className="flex justify-between items-center mb-1">
                                          <label className="text-sm font-medium text-gray-400">IoU Threshold</label>
                                          <span className="text-blue-400 font-mono text-sm">{field.value?.toFixed(2) || "0.50"}</span>
                                        </div>
                                        <input
                                          type="range"
                                          min="0"
                                          max="1"
                                          step="0.01"
                                          {...field}
                                          value={field.value || 0.50}
                                          onChange={e => field.onChange(parseFloat(e.target.value))}
                                          className="w-full h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer accent-green-500"
                                        />
                                        <p className="text-xs text-gray-500 mt-1">
                                          Intersection over Union: Overlap threshold for considering boxes as duplicates
                                        </p>
                                      </div>
                                    )}
                                  />

                                  <div className="grid grid-cols-2 gap-3">
                                    <Controller
                                      name="detection_params.max_detections"
                                      control={control}
                                      render={({ field }) => (
                                        <Input
                                          label="Max Detections"
                                          type="number"
                                          min="1"
                                          max="1000"
                                          {...field}
                                          value={field.value || 100}
                                          onChange={e => field.onChange(parseInt(e.target.value))}
                                        />
                                      )}
                                    />

                                    <Controller
                                      name="detection_params.min_score"
                                      control={control}
                                      render={({ field }) => (
                                        <Input
                                          label="Min Score"
                                          type="number"
                                          min="0"
                                          max="1"
                                          step="0.01"
                                          {...field}
                                          value={field.value || 0.25}
                                          onChange={e => field.onChange(parseFloat(e.target.value))}
                                        />
                                      )}
                                    />
                                  </div>

                                  <div className="grid grid-cols-2 gap-3">
                                    <Controller
                                      name="detection_params.min_object_size"
                                      control={control}
                                      render={({ field }) => (
                                        <Input
                                          label="Min Object Size (px²)"
                                          type="number"
                                          min="0"
                                          {...field}
                                          value={field.value || 0}
                                          onChange={e => field.onChange(parseInt(e.target.value))}
                                          placeholder="0 (disabled)"
                                        />
                                      )}
                                    />

                                    <Controller
                                      name="detection_params.max_object_size"
                                      control={control}
                                      render={({ field }) => (
                                        <Input
                                          label="Max Object Size (px²)"
                                          type="number"
                                          min="0"
                                          {...field}
                                          value={field.value || 999999}
                                          onChange={e => field.onChange(parseInt(e.target.value))}
                                          placeholder="999999 (disabled)"
                                        />
                                      )}
                                    />
                                  </div>
                                </div>
                              </div>
                            )}
                        </Card>

                        <Card title="Edge Optimization">
                            <Controller
                                name="edge_inference_config.disable_cloud_escalation"
                                control={control}
                                render={({ field }) => (
                                    <div className="bg-gray-700 p-3 rounded-md border border-gray-600">
                                        <Checkbox
                                            label="Enable Offline Mode"
                                            id="disable_cloud_escalation"
                                            checked={field.value}
                                            onChange={e => field.onChange(e.target.checked)}
                                        />
                                        <p className="text-xs text-gray-500 ml-6 mt-1 italic">When enabled, the edge hub will never send images to the cloud, even if confidence is low.</p>
                                    </div>
                                )}
                            />
                            <Controller
                                name="patience_time"
                                control={control}
                                render={({ field }) => (
                                    <Input label="Patience Time (seconds)" id="patience_time" type="number" {...field} onChange={e => field.onChange(parseFloat(e.target.value))} />
                                )}
                            />
                            <Controller
                                name="edge_inference_config.min_time_between_escalations"
                                control={control}
                                render={({ field }) => (
                                     <Input label="Min Escalation Interval (s)" id="min_time_between_escalations" type="number" {...field} onChange={e => field.onChange(parseFloat(e.target.value))} />
                                )}
                            />
                        </Card>

                    <Card title="Deployment Status">
                        {deployments.length === 0 ? (
                            <div className="text-center py-8">
                                <p className="text-gray-500 italic">Not currently deployed to any hubs.</p>
                                <button type="button" onClick={() => navigate('/deployments')} className="mt-4 text-blue-400 hover:underline text-sm font-bold">
                                    Go to Deployment Manager →
                                </button>
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {deployments.map(dep => (
                                    <div key={dep.id} className="bg-gray-700 p-3 rounded-md flex items-center justify-between border-l-4 border-green-500">
                                        <div>
                                            <p className="text-sm font-bold text-white">{dep.hub_name || 'Edge Device'}</p>
                                            <p className="text-xs text-gray-400">{new Date(dep.deployed_at).toLocaleDateString()}</p>
                                        </div>
                                        <span className="text-xs bg-green-900 text-green-300 px-2 py-1 rounded font-mono uppercase">
                                            {dep.status}
                                        </span>
                                    </div>
                                ))}
                                <p className="text-xs text-gray-500 mt-4 text-center">To deploy to new devices, use the Deployment Manager.</p>
                            </div>
                        )}
                    </Card>

                    <Card title="Quick Actions">
                        <div className="space-y-2">
                            <button type="button" onClick={() => navigate('/queries', { state: { detector_id: detectorId } })} className="w-full text-left bg-gray-700 hover:bg-gray-600 p-3 rounded text-sm flex items-center">
                                <span className="mr-3">📊</span> View Query History
                            </button>
                            <button type="button" onClick={() => navigate('/escalations', { state: { detector_id: detectorId } })} className="w-full text-left bg-gray-700 hover:bg-gray-600 p-3 rounded text-sm flex items-center">
                                <span className="mr-3">🚨</span> View Escalation Queue
                            </button>
                        </div>
                    </Card>
                </div>
            </div>
            )}

            {activeTab === 'alerts' && detectorId && (
                <DetectorAlertsConfig detectorId={detectorId} />
            )}

            {activeTab === 'training' && detectorId && (
                <ModelTrainingTab detectorId={detectorId} />
            )}
        </div>
    );
};

// Detector Alerts Configuration Component
const DetectorAlertsConfig = ({ detectorId }: { detectorId: string }) => {
    const [config, setConfig] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [alertHistory, setAlertHistory] = useState<any[]>([]);

    useEffect(() => {
        fetchAlertConfig();
        fetchAlertHistory();
    }, [detectorId]);

    const fetchAlertConfig = async () => {
        try {
            const res = await axios.get(`/detectors/${detectorId}/alert-config`);
            setConfig(res.data);
        } catch (err) {
            console.error('Failed to fetch alert config:', err);
            toast.error('Failed to load alert configuration');
        } finally {
            setLoading(false);
        }
    };

    const fetchAlertHistory = async () => {
        try {
            const res = await axios.get(`/detectors/${detectorId}/alerts?limit=50`);
            setAlertHistory(res.data);
        } catch (err) {
            console.error('Failed to fetch alert history:', err);
        }
    };

    const saveAlertConfig = async () => {
        if (!config) return;
        try {
            setSaving(true);
            await axios.put(`/detectors/${detectorId}/alert-config`, config);
            toast.success('Alert configuration saved successfully');
        } catch (err) {
            console.error('Failed to save alert config:', err);
            toast.error('Failed to save alert configuration');
        } finally {
            setSaving(false);
        }
    };

    const acknowledgeAlert = async (alertId: string) => {
        try {
            await axios.post(`/detectors/alerts/${alertId}/acknowledge`, {});
            toast.success('Alert acknowledged');
            fetchAlertHistory();
        } catch (err) {
            console.error('Failed to acknowledge alert:', err);
            toast.error('Failed to acknowledge alert');
        }
    };

    if (loading) {
        return <div className="text-center text-gray-400 py-8">Loading alert configuration...</div>;
    }

    if (!config) {
        return <div className="text-center text-red-400 py-8">Failed to load alert configuration</div>;
    }

    return (
        <div className="space-y-6">
            {/* Alert Configuration */}
            <Card title="Alert Configuration">
                <div className="space-y-4">
                    <Checkbox
                        label="Enable Alerts"
                        id="enabled"
                        checked={config.enabled}
                        onChange={(e: any) => setConfig({ ...config, enabled: e.target.checked })}
                    />

                    {config.enabled && (
                        <>
                            <Select
                                label="Alert Condition"
                                id="condition_type"
                                value={config.condition_type}
                                onChange={(e: any) => setConfig({ ...config, condition_type: e.target.value })}
                            >
                                <option value="LABEL_MATCH">When label matches value</option>
                                <option value="CONFIDENCE_THRESHOLD">When confidence exceeds threshold</option>
                                <option value="ALWAYS">Always alert (every detection)</option>
                            </Select>

                            <Input
                                label={config.condition_type === 'LABEL_MATCH' ? 'Label Value (e.g., YES, Person)' : 'Confidence Threshold (0-1)'}
                                id="condition_value"
                                value={config.condition_value || ''}
                                onChange={(e: any) => setConfig({ ...config, condition_value: e.target.value })}
                                placeholder={config.condition_type === 'LABEL_MATCH' ? 'YES' : '0.9'}
                            />

                            <div>
                                <label className="block text-sm font-medium text-gray-400 mb-2">Alert Recipients (one email per line)</label>
                                <textarea
                                    value={(config.alert_emails || []).join('\n')}
                                    onChange={(e) => setConfig({ ...config, alert_emails: e.target.value.split('\n').filter((s: string) => s.trim()) })}
                                    className="mt-1 block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm h-24"
                                    placeholder="security@company.com&#10;ops@company.com"
                                />
                            </div>

                            <Select
                                label="Severity"
                                id="severity"
                                value={config.severity}
                                onChange={(e: any) => setConfig({ ...config, severity: e.target.value })}
                            >
                                <option value="info">Info</option>
                                <option value="warning">Warning</option>
                                <option value="critical">Critical</option>
                            </Select>

                            <Input
                                label="Cooldown Period (minutes)"
                                id="cooldown_minutes"
                                type="number"
                                value={config.cooldown_minutes}
                                onChange={(e: any) => setConfig({ ...config, cooldown_minutes: parseInt(e.target.value) })}
                                min={1}
                                max={1440}
                            />
                            <p className="text-xs text-gray-500 -mt-2">Minimum time between alerts to prevent spam</p>

                            <div>
                                <label className="block text-sm font-medium text-gray-400 mb-2">Custom Message Template (optional)</label>
                                <textarea
                                    value={config.custom_message || ''}
                                    onChange={(e) => setConfig({ ...config, custom_message: e.target.value })}
                                    className="mt-1 block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm h-24"
                                    placeholder="Person detected on {camera_name} with {confidence} confidence"
                                />
                                <p className="text-xs text-gray-500 mt-1">
                                    Available placeholders: {'{detector_name}'}, {'{label}'}, {'{confidence}'}, {'{camera_name}'}
                                </p>
                            </div>
                        </>
                    )}

                    <div className="flex space-x-4">
                        <button
                            onClick={saveAlertConfig}
                            disabled={saving}
                            className="bg-green-600 hover:bg-green-500 text-white font-bold py-2 px-6 rounded transition disabled:bg-gray-500"
                        >
                            {saving ? 'Saving...' : 'Save Alert Configuration'}
                        </button>
                        <a
                            href={`/detectors/${detectorId}/alert-config`}
                            className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-6 rounded transition inline-block"
                        >
                            Advanced Alert Settings
                        </a>
                    </div>
                </div>
            </Card>

            {/* Alert History */}
            <Card title="Recent Alerts">
                {alertHistory.length === 0 ? (
                    <div className="text-center text-gray-500 py-8">No alerts yet</div>
                ) : (
                    <div className="space-y-3">
                        {alertHistory.map((alert) => (
                            <div
                                key={alert.id}
                                className={`p-4 rounded-lg border ${
                                    alert.severity === 'critical' ? 'bg-red-900/20 border-red-700' :
                                    alert.severity === 'warning' ? 'bg-yellow-900/20 border-yellow-700' :
                                    'bg-blue-900/20 border-blue-700'
                                } ${alert.acknowledged ? 'opacity-60' : ''}`}
                            >
                                <div className="flex justify-between items-start mb-2">
                                    <div className="flex items-center gap-2">
                                        <span className={`px-2 py-1 rounded text-xs font-bold ${
                                            alert.severity === 'critical' ? 'bg-red-900 text-red-300' :
                                            alert.severity === 'warning' ? 'bg-yellow-900 text-yellow-300' :
                                            'bg-blue-900 text-blue-300'
                                        }`}>
                                            {alert.severity.toUpperCase()}
                                        </span>
                                        {alert.acknowledged && (
                                            <span className="text-xs text-green-400">✓ Acknowledged</span>
                                        )}
                                    </div>
                                    <span className="text-xs text-gray-500">
                                        {new Date(alert.created_at).toLocaleString()}
                                    </span>
                                </div>
                                <p className="text-white mb-2">{alert.message}</p>
                                <div className="flex gap-4 text-xs text-gray-400">
                                    {alert.detection_label && (
                                        <span>Label: <strong>{alert.detection_label}</strong></span>
                                    )}
                                    {alert.detection_confidence && (
                                        <span>Confidence: <strong>{(alert.detection_confidence * 100).toFixed(1)}%</strong></span>
                                    )}
                                    {alert.camera_name && (
                                        <span>Camera: <strong>{alert.camera_name}</strong></span>
                                    )}
                                </div>
                                {!alert.acknowledged && (
                                    <button
                                        onClick={() => acknowledgeAlert(alert.id)}
                                        className="mt-3 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold py-1 px-3 rounded"
                                    >
                                        Acknowledge
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </Card>
        </div>
    );
};

// ── Phase 5: Model Training Tab ───────────────────────────────────────────────

interface TrainingRun {
    id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    started_at: string | null;
    completed_at: string | null;
    dataset_id: string | null;
    candidate_model_path: string | null;
    metrics: { precision?: number; recall?: number; mAP50?: number; mAP50_95?: number } | null;
    triggered_by: string | null;
    error_log: string | null;
    auto_triggered: boolean;
}

interface ModelStatus {
    primary_model_path: string | null;
    candidate_model_path: string | null;
    candidate_model_version: number | null;
    previous_primary_model_path: string | null;
    can_promote: boolean;
    can_rollback: boolean;
    latest_run: TrainingRun | null;
}

interface DatasetExport {
    dataset_id: string;
    sample_count: number;
    train_count: number;
    val_count: number;
    skipped: number;
    label_distribution: Record<string, number>;
    class_names: string[];
    download_url: string;
    created_at: string;
}

interface CanaryDisagreement {
    id: string;
    query_id: string | null;
    created_at: string | null;
    primary_label: string | null;
    primary_confidence: number | null;
    shadow_label: string | null;
    shadow_confidence: number | null;
}

interface CanaryReport {
    total: number;
    agreed: number;
    agreement_rate: number | null;
    primary_label_distribution: Record<string, number>;
    shadow_label_distribution: Record<string, number>;
    recent_disagreements: CanaryDisagreement[];
}

const StatusBadge = ({ status }: { status: string }) => {
    const styles: Record<string, string> = {
        pending:   'bg-yellow-900/60 text-yellow-300',
        running:   'bg-blue-900/60 text-blue-300 animate-pulse',
        completed: 'bg-green-900/60 text-green-300',
        failed:    'bg-red-900/60 text-red-300',
    };
    return (
        <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase font-mono ${styles[status] ?? 'bg-gray-700 text-gray-400'}`}>
            {status}
        </span>
    );
};

const MetricPill = ({ label, value }: { label: string; value: number | undefined }) => {
    if (value === undefined || value === null) return null;
    return (
        <span className="bg-gray-700 px-2 py-0.5 rounded text-xs font-mono">
            <span className="text-gray-400">{label}: </span>
            <span className="text-white font-bold">{(value * 100).toFixed(1)}%</span>
        </span>
    );
};

const ModelTrainingTab = ({ detectorId }: { detectorId: string }) => {
    const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
    const [trainingRuns, setTrainingRuns] = useState<TrainingRun[]>([]);
    const [lastExport, setLastExport] = useState<DatasetExport | null>(null);
    const [loading, setLoading] = useState(true);
    const [isExporting, setIsExporting] = useState(false);
    const [isTriggering, setIsTriggering] = useState(false);
    const [isPromoting, setIsPromoting] = useState(false);
    const [isRollingBack, setIsRollingBack] = useState(false);
    const [epochs, setEpochs] = useState(50);
    const [baseModel, setBaseModel] = useState('yolov8s.pt');
    const [canaryReport, setCanaryReport] = useState<CanaryReport | null>(null);

    const fetchAll = async () => {
        try {
            const [statusRes, runsRes, canaryRes] = await Promise.all([
                axios.get(`/detectors/${detectorId}/model-status`),
                axios.get(`/detectors/${detectorId}/training-runs`),
                axios.get(`/detectors/${detectorId}/canary-report`).catch(() => ({ data: null })),
            ]);
            setModelStatus(statusRes.data);
            setTrainingRuns(runsRes.data);
            if (canaryRes.data && canaryRes.data.total > 0) {
                setCanaryReport(canaryRes.data);
            }
        } catch (err) {
            console.error('Failed to fetch training status:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAll();
    }, [detectorId]);

    // Auto-refresh every 10 s while a run is active
    useEffect(() => {
        const hasActive = trainingRuns.some(r => r.status === 'pending' || r.status === 'running');
        if (!hasActive) return;
        const t = setInterval(fetchAll, 10000);
        return () => clearInterval(t);
    }, [trainingRuns]);

    const handleExport = async () => {
        setIsExporting(true);
        try {
            const res = await axios.get(`/detectors/${detectorId}/export-dataset`);
            setLastExport(res.data);
            toast.success(`Dataset exported — ${res.data.sample_count} labeled samples`);
        } catch (err: any) {
            toast.error(err.response?.data?.detail || 'Dataset export failed');
        } finally {
            setIsExporting(false);
        }
    };

    // Dataset ID to use: from fresh export or from the latest run's dataset
    const availableDatasetId = lastExport?.dataset_id ?? modelStatus?.latest_run?.dataset_id ?? null;

    const handleTriggerTraining = async () => {
        if (!availableDatasetId) {
            toast.warn('Export a dataset first before triggering training');
            return;
        }
        setIsTriggering(true);
        try {
            const res = await axios.post(`/detectors/${detectorId}/trigger-training`, null, {
                params: { dataset_id: availableDatasetId, epochs, base_model: baseModel },
            });
            toast.success(`Training started — run ${res.data.training_run_id.slice(0, 8)}…`);
            await fetchAll();
        } catch (err: any) {
            toast.error(err.response?.data?.detail || 'Failed to start training');
        } finally {
            setIsTriggering(false);
        }
    };

    const handlePromote = async () => {
        if (!window.confirm('Promote candidate model to primary? Edge devices will update on next refresh cycle (≤60 s).')) return;
        setIsPromoting(true);
        try {
            await axios.post(`/detectors/${detectorId}/promote-candidate`);
            toast.success('Candidate promoted — edge devices will update shortly');
            await fetchAll();
        } catch (err: any) {
            toast.error(err.response?.data?.detail || 'Promotion failed');
        } finally {
            setIsPromoting(false);
        }
    };

    const handleRollback = async () => {
        if (!window.confirm('Roll back to previous model? The current primary will be removed.')) return;
        setIsRollingBack(true);
        try {
            await axios.post(`/detectors/${detectorId}/rollback`);
            toast.success('Rolled back to previous model');
            await fetchAll();
        } catch (err: any) {
            toast.error(err.response?.data?.detail || 'Rollback failed');
        } finally {
            setIsRollingBack(false);
        }
    };

    const hasActiveRun = trainingRuns.some(r => r.status === 'pending' || r.status === 'running');

    if (loading) {
        return <div className="text-gray-400 py-12 text-center">Loading training status…</div>;
    }

    return (
        <div className="space-y-6">

            {/* ── Model Status ─────────────────────────────────────────── */}
            <Card title="Live Model">
                <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="bg-gray-700 p-4 rounded-lg border border-gray-600">
                            <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">Primary (Live)</p>
                            <p className="text-sm text-white font-mono break-all">
                                {modelStatus?.primary_model_path
                                    ? modelStatus.primary_model_path.split('/').slice(-3).join('/')
                                    : <span className="text-gray-500 italic">No model deployed</span>}
                            </p>
                        </div>
                        <div className={`p-4 rounded-lg border ${modelStatus?.candidate_model_path ? 'bg-green-900/20 border-green-700' : 'bg-gray-700 border-gray-600'}`}>
                            <p className="text-xs text-gray-400 uppercase tracking-wider mb-1">
                                Candidate {modelStatus?.candidate_model_version ? `(v${modelStatus.candidate_model_version})` : ''}
                            </p>
                            <p className="text-sm font-mono break-all">
                                {modelStatus?.candidate_model_path
                                    ? <span className="text-green-300">{modelStatus.candidate_model_path.split('/').slice(-3).join('/')}</span>
                                    : <span className="text-gray-500 italic">None — train a new model first</span>}
                            </p>
                        </div>
                    </div>

                    {/* Latest run metrics if completed */}
                    {modelStatus?.latest_run?.status === 'completed' && modelStatus.latest_run.metrics && (
                        <div className="flex flex-wrap gap-2 pt-1">
                            <MetricPill label="Precision" value={modelStatus.latest_run.metrics.precision} />
                            <MetricPill label="Recall" value={modelStatus.latest_run.metrics.recall} />
                            <MetricPill label="mAP50" value={modelStatus.latest_run.metrics.mAP50} />
                            <MetricPill label="mAP50-95" value={modelStatus.latest_run.metrics.mAP50_95} />
                        </div>
                    )}

                    <div className="flex gap-3 pt-2">
                        <button
                            onClick={handlePromote}
                            disabled={!modelStatus?.can_promote || isPromoting}
                            className="bg-green-700 hover:bg-green-600 disabled:bg-gray-700 disabled:text-gray-500 text-white font-bold py-2 px-5 rounded transition text-sm"
                        >
                            {isPromoting ? 'Promoting…' : '▲ Promote Candidate'}
                        </button>
                        <button
                            onClick={handleRollback}
                            disabled={!modelStatus?.can_rollback || isRollingBack}
                            className="bg-orange-700 hover:bg-orange-600 disabled:bg-gray-700 disabled:text-gray-500 text-white font-bold py-2 px-5 rounded transition text-sm"
                        >
                            {isRollingBack ? 'Rolling back…' : '↩ Rollback'}
                        </button>
                    </div>
                    {modelStatus?.previous_primary_model_path && (
                        <p className="text-xs text-gray-500">
                            Rollback target: {modelStatus.previous_primary_model_path.split('/').slice(-3).join('/')}
                        </p>
                    )}
                </div>
            </Card>

            {/* ── Dataset & Training ───────────────────────────────────── */}
            <Card title="Dataset & Training">
                <div className="space-y-5">
                    {/* Export section */}
                    <div className="bg-gray-700 p-4 rounded-lg border border-gray-600">
                        <div className="flex items-center justify-between mb-3">
                            <div>
                                <h3 className="text-sm font-bold text-white">Labeled Dataset</h3>
                                <p className="text-xs text-gray-400 mt-0.5">Requires 50+ labeled samples (ground truth or feedback)</p>
                            </div>
                            <button
                                onClick={handleExport}
                                disabled={isExporting}
                                className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 text-white font-bold py-2 px-4 rounded transition text-sm whitespace-nowrap"
                            >
                                {isExporting ? 'Exporting…' : '⬇ Export Dataset'}
                            </button>
                        </div>

                        {lastExport && (
                            <div className="space-y-2 pt-2 border-t border-gray-600">
                                <div className="flex gap-6 text-sm">
                                    <span className="text-gray-400">Total: <span className="text-white font-bold">{lastExport.sample_count}</span></span>
                                    <span className="text-gray-400">Train: <span className="text-white font-bold">{lastExport.train_count}</span></span>
                                    <span className="text-gray-400">Val: <span className="text-white font-bold">{lastExport.val_count}</span></span>
                                    {lastExport.skipped > 0 && <span className="text-yellow-400">Skipped: {lastExport.skipped}</span>}
                                </div>
                                {Object.keys(lastExport.label_distribution).length > 0 && (
                                    <div className="flex flex-wrap gap-2">
                                        {Object.entries(lastExport.label_distribution).map(([lbl, cnt]) => (
                                            <span key={lbl} className="bg-gray-600 text-gray-200 px-2 py-0.5 rounded text-xs font-mono">
                                                {lbl}: {cnt}
                                            </span>
                                        ))}
                                    </div>
                                )}
                                <div className="flex gap-3 pt-1">
                                    <a
                                        href={lastExport.download_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-blue-400 hover:underline text-xs"
                                    >
                                        ↗ Download zip (60 min link)
                                    </a>
                                    <span className="text-gray-600 text-xs">ID: {lastExport.dataset_id.slice(0, 8)}…</span>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Trigger training section */}
                    <div className="bg-gray-700 p-4 rounded-lg border border-gray-600">
                        <h3 className="text-sm font-bold text-white mb-3">Trigger Fine-Tuning</h3>
                        <div className="grid grid-cols-2 gap-4 mb-4">
                            <div>
                                <label className="block text-xs text-gray-400 mb-1">Base Model</label>
                                <select
                                    value={baseModel}
                                    onChange={e => setBaseModel(e.target.value)}
                                    className="w-full bg-gray-800 border border-gray-600 text-white rounded px-3 py-2 text-sm"
                                >
                                    <option value="yolov8n.pt">YOLOv8n (nano — fastest)</option>
                                    <option value="yolov8s.pt">YOLOv8s (small — recommended)</option>
                                    <option value="yolov8m.pt">YOLOv8m (medium)</option>
                                    <option value="yolov8l.pt">YOLOv8l (large)</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-xs text-gray-400 mb-1">Epochs</label>
                                <input
                                    type="number"
                                    min={5}
                                    max={300}
                                    value={epochs}
                                    onChange={e => setEpochs(parseInt(e.target.value) || 50)}
                                    className="w-full bg-gray-800 border border-gray-600 text-white rounded px-3 py-2 text-sm"
                                />
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            <button
                                onClick={handleTriggerTraining}
                                disabled={isTriggering || hasActiveRun || !availableDatasetId}
                                className="bg-green-700 hover:bg-green-600 disabled:bg-gray-600 disabled:text-gray-500 text-white font-bold py-2 px-5 rounded transition text-sm"
                            >
                                {isTriggering ? 'Starting…' : hasActiveRun ? 'Training in progress…' : '▶ Start Training'}
                            </button>
                            {!availableDatasetId && (
                                <span className="text-xs text-yellow-400">Export a dataset first</span>
                            )}
                            {availableDatasetId && !lastExport && (
                                <span className="text-xs text-gray-400">Using dataset from last run</span>
                            )}
                        </div>
                        <p className="text-xs text-gray-500 mt-2">
                            Training runs in the background. Results appear in the Training History below.
                            New ONNX model is uploaded as a candidate — review metrics before promoting.
                        </p>
                    </div>
                </div>
            </Card>

            {/* ── Auto-Training ────────────────────────────────────────── */}
            <Card title="Auto-Training">
                <div className="space-y-3">
                    <p className="text-sm text-gray-300">
                        The backend checks every hour and automatically triggers fine-tuning when a detector
                        accumulates <strong className="text-white">100+ new labeled samples</strong> since
                        the last completed training run.
                    </p>
                    <div className="grid grid-cols-3 gap-3">
                        <div className="bg-gray-700 rounded-lg p-3 border border-gray-600 text-center">
                            <p className="text-xs text-gray-400 mb-1">Threshold</p>
                            <p className="text-lg font-bold text-white font-mono">100</p>
                            <p className="text-xs text-gray-500">samples</p>
                        </div>
                        <div className="bg-gray-700 rounded-lg p-3 border border-gray-600 text-center">
                            <p className="text-xs text-gray-400 mb-1">Check interval</p>
                            <p className="text-lg font-bold text-white font-mono">1 h</p>
                            <p className="text-xs text-gray-500">configurable</p>
                        </div>
                        <div className="bg-gray-700 rounded-lg p-3 border border-gray-600 text-center">
                            <p className="text-xs text-gray-400 mb-1">Auto runs</p>
                            <p className="text-lg font-bold text-purple-300 font-mono">
                                {trainingRuns.filter(r => r.auto_triggered).length}
                            </p>
                            <p className="text-xs text-gray-500">this detector</p>
                        </div>
                    </div>
                    <p className="text-xs text-gray-500">
                        Runs triggered automatically are marked with an <span className="bg-purple-900/60 text-purple-300 px-1.5 py-0.5 rounded text-xs font-bold uppercase font-mono">auto</span> badge in Training History.
                        Email notifications are sent on trigger and completion to <code className="text-gray-300">AUTO_TRAINING_NOTIFY_EMAILS</code>.
                    </p>
                </div>
            </Card>

            {/* ── Canary Report ────────────────────────────────────────── */}
            {canaryReport && canaryReport.total > 0 && (
                <Card title="Canary Report (Shadow Mode)">
                    <div className="space-y-4">
                        {/* Agreement summary */}
                        <div className="flex items-center gap-4">
                            <div className={`text-2xl font-bold font-mono ${
                                (canaryReport.agreement_rate ?? 0) >= 0.90 ? 'text-green-400' :
                                (canaryReport.agreement_rate ?? 0) >= 0.75 ? 'text-yellow-400' : 'text-red-400'
                            }`}>
                                {canaryReport.agreement_rate !== null
                                    ? `${(canaryReport.agreement_rate * 100).toFixed(1)}%`
                                    : '—'}
                            </div>
                            <div className="text-sm text-gray-400">
                                agreement between primary and candidate
                                <br />
                                <span className="text-xs text-gray-500">
                                    {canaryReport.agreed} / {canaryReport.total} frames matched
                                </span>
                            </div>
                            {canaryReport.agreement_rate !== null && canaryReport.agreement_rate >= 0.90 && (
                                <span className="ml-auto bg-green-900/40 border border-green-700 text-green-300 text-xs font-bold px-3 py-1 rounded">
                                    Ready to promote
                                </span>
                            )}
                        </div>

                        {/* Label distribution comparison */}
                        {(Object.keys(canaryReport.primary_label_distribution).length > 0 ||
                          Object.keys(canaryReport.shadow_label_distribution).length > 0) && (
                            <div className="grid grid-cols-2 gap-3">
                                <div className="bg-gray-700 p-3 rounded-lg border border-gray-600">
                                    <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Primary labels</p>
                                    <div className="space-y-1">
                                        {Object.entries(canaryReport.primary_label_distribution).map(([lbl, cnt]) => (
                                            <div key={lbl} className="flex justify-between text-xs">
                                                <span className="text-gray-300 font-mono">{lbl}</span>
                                                <span className="text-white font-bold">{cnt}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                                <div className="bg-gray-700 p-3 rounded-lg border border-green-800/50">
                                    <p className="text-xs text-green-400 uppercase tracking-wider mb-2">Candidate labels</p>
                                    <div className="space-y-1">
                                        {Object.entries(canaryReport.shadow_label_distribution).map(([lbl, cnt]) => {
                                            const primaryCnt = canaryReport.primary_label_distribution[lbl] ?? 0;
                                            const delta = cnt - primaryCnt;
                                            return (
                                                <div key={lbl} className="flex justify-between text-xs">
                                                    <span className="text-gray-300 font-mono">{lbl}</span>
                                                    <span className="text-white font-bold">
                                                        {cnt}
                                                        {delta !== 0 && (
                                                            <span className={`ml-1 ${delta > 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                                ({delta > 0 ? '+' : ''}{delta})
                                                            </span>
                                                        )}
                                                    </span>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Recent disagreements */}
                        {canaryReport.recent_disagreements.length > 0 && (
                            <details>
                                <summary className="text-xs text-yellow-400 cursor-pointer font-bold">
                                    {canaryReport.recent_disagreements.length} disagreements
                                </summary>
                                <div className="mt-2 overflow-x-auto">
                                    <table className="w-full text-xs text-gray-300 border-collapse">
                                        <thead>
                                            <tr className="text-gray-500 border-b border-gray-700">
                                                <th className="py-1 pr-3 text-left">Time</th>
                                                <th className="py-1 pr-3 text-left">Primary</th>
                                                <th className="py-1 pr-3 text-left">Conf</th>
                                                <th className="py-1 pr-3 text-left">Candidate</th>
                                                <th className="py-1 text-left">Conf</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {canaryReport.recent_disagreements.map(d => (
                                                <tr key={d.id} className="border-b border-gray-800 hover:bg-gray-700/40">
                                                    <td className="py-1 pr-3 text-gray-500 whitespace-nowrap">
                                                        {d.created_at ? new Date(d.created_at).toLocaleString() : '—'}
                                                    </td>
                                                    <td className="py-1 pr-3 font-mono">{d.primary_label ?? '—'}</td>
                                                    <td className="py-1 pr-3 text-gray-400">
                                                        {d.primary_confidence !== null ? `${(d.primary_confidence * 100).toFixed(0)}%` : '—'}
                                                    </td>
                                                    <td className="py-1 pr-3 font-mono text-green-300">{d.shadow_label ?? '—'}</td>
                                                    <td className="py-1 text-gray-400">
                                                        {d.shadow_confidence !== null ? `${(d.shadow_confidence * 100).toFixed(0)}%` : '—'}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </details>
                        )}

                        <p className="text-xs text-gray-500">
                            Shadow mode runs the candidate model alongside the primary on every live query.
                            Results are not used for decisions — only for comparison. Promote when you're satisfied with agreement.
                        </p>
                    </div>
                </Card>
            )}

            {/* ── Training History ─────────────────────────────────────── */}
            <Card title="Training History">
                {trainingRuns.length === 0 ? (
                    <div className="text-center text-gray-500 py-8 italic">No training runs yet</div>
                ) : (
                    <div className="space-y-3">
                        {trainingRuns.map(run => (
                            <div
                                key={run.id}
                                className={`p-4 rounded-lg border ${
                                    run.status === 'failed' ? 'bg-red-900/10 border-red-800' :
                                    run.status === 'completed' ? 'bg-green-900/10 border-green-800' :
                                    'bg-gray-700 border-gray-600'
                                }`}
                            >
                                <div className="flex items-start justify-between gap-3">
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <StatusBadge status={run.status} />
                                            {run.auto_triggered && (
                                                <span className="bg-purple-900/60 text-purple-300 px-2 py-0.5 rounded text-xs font-bold uppercase font-mono">auto</span>
                                            )}
                                            <span className="text-xs text-gray-500 font-mono">{run.id.slice(0, 8)}…</span>
                                            {run.triggered_by && !run.auto_triggered && (
                                                <span className="text-xs text-gray-500">by {run.triggered_by}</span>
                                            )}
                                        </div>
                                        <div className="flex gap-4 text-xs text-gray-400 mb-2">
                                            {run.started_at && (
                                                <span>Started: {new Date(run.started_at).toLocaleString()}</span>
                                            )}
                                            {run.completed_at && (
                                                <span>Finished: {new Date(run.completed_at).toLocaleString()}</span>
                                            )}
                                        </div>
                                        {run.metrics && (
                                            <div className="flex flex-wrap gap-2 mb-2">
                                                <MetricPill label="P" value={run.metrics.precision} />
                                                <MetricPill label="R" value={run.metrics.recall} />
                                                <MetricPill label="mAP50" value={run.metrics.mAP50} />
                                                <MetricPill label="mAP50-95" value={run.metrics.mAP50_95} />
                                            </div>
                                        )}
                                        {run.candidate_model_path && (
                                            <p className="text-xs text-gray-400 font-mono truncate" title={run.candidate_model_path}>
                                                Model: {run.candidate_model_path.split('/').slice(-3).join('/')}
                                            </p>
                                        )}
                                        {run.error_log && (
                                            <details className="mt-2">
                                                <summary className="text-xs text-red-400 cursor-pointer">Error details</summary>
                                                <pre className="mt-1 text-xs text-red-300 bg-red-900/20 p-2 rounded overflow-x-auto whitespace-pre-wrap break-all">
                                                    {run.error_log}
                                                </pre>
                                            </details>
                                        )}
                                    </div>
                                    {run.status === 'running' && (
                                        <div className="flex-shrink-0 mt-1">
                                            <div className="w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </Card>
        </div>
    );
};

export default DetectorConfigPage;