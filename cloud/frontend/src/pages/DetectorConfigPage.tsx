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
    const [activeTab, setActiveTab] = useState<'config' | 'alerts'>('config');

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
                                  IO-E detects these objects in real-time. Use IO-VLM for complex queries.
                                  No custom model upload needed for open-vocab mode.
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

export default DetectorConfigPage;