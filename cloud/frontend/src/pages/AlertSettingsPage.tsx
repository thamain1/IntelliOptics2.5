import React, { useEffect, useState } from 'react';
import { useForm, Controller, useFieldArray } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { toast, ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

// --- Zod Schemas for Form Validation ---

const AlertTriggerConfigSchema = z.object({
  low_confidence: z.boolean().default(false),
  confidence_threshold: z.number().min(0).max(1).default(0.80),
  oodd: z.boolean().default(false),
  oodd_threshold: z.number().min(0).max(1).default(0.50),
  camera_health_critical: z.boolean().default(false),
  edge_device_offline: z.boolean().default(false),
});

const AlertBatchingConfigSchema = z.object({
  strategy: z.string().max(50).default("immediate"),
  count_threshold: z.preprocess((val) => Number(val), z.number().int().min(1).optional().default(10)),
  interval_minutes: z.preprocess((val) => Number(val), z.number().int().min(1).optional().default(15)),
});

const AlertRateLimitingConfigSchema = z.object({
  max_per_hour: z.preprocess((val) => Number(val), z.number().int().min(0).default(100)),
});

const AlertSettingsSchema = z.object({
  sendgrid_api_key: z.string().optional(),
  from_email: z.string().email({ message: "Invalid email address" }).optional().or(z.literal('')),
  recipients: z.array(z.string().email({ message: "Invalid email address" })).default([]),
  triggers: AlertTriggerConfigSchema.default({}),
  batching: AlertBatchingConfigSchema.default({}),
  rate_limiting: AlertRateLimitingConfigSchema.default({}),
});

type AlertSettingsFormData = z.infer<typeof AlertSettingsSchema>;

// --- Reusable Components ---
const Card = ({ title, children }: { title: string, children: React.ReactNode }) => (
    <div className="bg-gray-800 rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-xl font-semibold text-white mb-4">{title}</h2>
        <div className="space-y-4">{children}</div>
    </div>
);
const Input = ({ label, id, error, ...props }: any) => (
    <div>
        <label htmlFor={id} className="block text-sm font-medium text-gray-400">{label}</label>
        <input id={id} {...props} className="mt-1 block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm" />
        {error && <p className="text-red-500 text-xs mt-1">{error.message}</p>}
    </div>
);
const Checkbox = ({ label, id, ...props }: any) => (
    <div className="flex items-center">
        <input id={id} {...props} type="checkbox" className="focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-600 rounded" />
        <label htmlFor={id} className="ml-2 block text-sm text-gray-300">{label}</label>
    </div>
);

// --- Main Page Component ---
const AlertSettingsPage = () => {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(true);
  const [testEmailRecipient, setTestEmailRecipient] = useState('');

  const {
    handleSubmit,
    control,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<AlertSettingsFormData>({
    resolver: zodResolver(AlertSettingsSchema),
    defaultValues: {
      recipients: [],
      triggers: {},
      batching: {},
      rate_limiting: {}
    }
  });

  const { fields, append, remove } = useFieldArray({
    control,
    name: "recipients",
  });

  useEffect(() => {
    const fetchSettings = async () => {
      setIsLoading(true);
      try {
        const response = await axios.get('/settings/alerts');
        reset(AlertSettingsSchema.parse(response.data));
      } catch (error) {
        toast.error('Failed to fetch alert settings.');
      } finally {
        setIsLoading(false);
      }
    };
    fetchSettings();
  }, [reset]);

  const onSubmit = async (data: AlertSettingsFormData) => {
    try {
      await axios.put('/settings/alerts', data);
      toast.success('Alert settings updated successfully!');
    } catch (error) {
      toast.error('Failed to update alert settings.');
    }
  };
  
  const handleTestEmail = async () => {
    if (!testEmailRecipient) {
        toast.error('Please enter a recipient email for the test.');
        return;
    }
    try {
        await axios.post('/settings/alerts/test', {
            recipient_email: testEmailRecipient,
            template_name: 'test_alert',
        });
        toast.success(`Test email sent successfully to ${testEmailRecipient}!`);
    } catch (error: any) {
        const detail = error.response?.data?.detail || 'An unknown error occurred.';
        toast.error(`Failed to send test email: ${detail}`);
    }
  };


  if (isLoading) {
    return <div className="p-8 text-white">Loading Alert Settings...</div>;
  }

  return (
    <div className="p-8 bg-gray-900 text-gray-300 min-h-screen">
      <ToastContainer position="top-right" autoClose={5000} hideProgressBar={false} />
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-white">Alert Settings</h1>
        <p className="text-gray-400">Manage global notification and alert configurations.</p>
      </header>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card title="Email Configuration">
            <Controller
                name="sendgrid_api_key"
                control={control}
                render={({ field }) => <Input {...field} label="SendGrid API Key" id="sendgrid_api_key" type="password" placeholder="SG.xxxxxxxx" />}
            />
            <Controller
                name="from_email"
                control={control}
                render={({ field }) => <Input {...field} label="From Email" id="from_email" type="email" placeholder="alerts@intellioptics.com" error={errors.from_email} />}
            />
          </Card>

          <Card title="Alert Recipients">
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {fields.map((item, index) => (
                <div key={item.id} className="flex items-center">
                  <Controller
                    name={`recipients.${index}`}
                    control={control}
                    render={({ field }) => <Input {...field} type="email" placeholder="recipient@example.com" error={errors.recipients?.[index]} />}
                  />
                  <button type="button" onClick={() => remove(index)} className="ml-2 text-red-500 hover:text-red-700">✕</button>
                </div>
              ))}
            </div>
            <button type="button" onClick={() => append('')} className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-1 px-3 rounded text-sm mt-2">+ Add Recipient</button>
          </Card>
        </div>

        <Card title="Alert Triggers">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <Controller name="triggers.low_confidence" control={control} render={({ field }) => <Checkbox {...field} label="Low Confidence Detection" id="low_confidence" checked={field.value} />} />
              <Controller name="triggers.oodd" control={control} render={({ field }) => <Checkbox {...field} label="Out-of-Domain (OODD) Detection" id="oodd" checked={field.value} />} />
            </div>
            <div className="space-y-4">
               <Controller name="triggers.camera_health_critical" control={control} render={({ field }) => <Checkbox {...field} label="Camera Health Critical" id="camera_health" checked={field.value} />} />
               <Controller name="triggers.edge_device_offline" control={control} render={({ field }) => <Checkbox {...field} label="Edge Device Offline" id="edge_offline" checked={field.value} />} />
            </div>
          </div>
        </Card>
        
        <div className="flex justify-end space-x-4 mt-8">
            <button type="button" onClick={() => navigate('/')} className="bg-gray-600 hover:bg-gray-500 text-white font-bold py-2 px-4 rounded">Cancel</button>
            <button type="submit" disabled={isSubmitting} className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-4 rounded">
              {isSubmitting ? 'Saving...' : 'Save Settings'}
            </button>
        </div>
      </form>
      
      <div className="mt-8 border-t border-gray-700 pt-6">
          <Card title="Test Email Alert">
             <div className="flex items-end space-x-4">
                <div className="flex-grow">
                  <Input 
                    label="Recipient Email"
                    id="test_email"
                    type="email"
                    value={testEmailRecipient}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTestEmailRecipient(e.target.value)}
                    placeholder="test@example.com"
                  />
                </div>
                <button type="button" onClick={handleTestEmail} className="bg-green-600 hover:bg-green-500 text-white font-bold py-2 px-4 rounded">Send Test</button>
             </div>
          </Card>
      </div>

    </div>
  );
};

export default AlertSettingsPage;
