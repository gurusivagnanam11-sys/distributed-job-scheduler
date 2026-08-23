import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../components/AuthProvider';
import { 
  getQueues, pauseQueue, resumeQueue, getQueueMetrics,
  createQueue, updateQueue, deleteQueue, getRetryPolicy, createRetryPolicy, updateRetryPolicy
} from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { Play, Pause, Trash2, Edit2, Settings, Plus } from 'lucide-react';

const QueueMetricsCard = ({ queueId }) => {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['queueMetrics', queueId],
    queryFn: () => getQueueMetrics(queueId),
    refetchInterval: 5000,
  });

  if (isLoading) return <div style={{ padding: '1rem 0', color: '#64748b', fontSize: '0.85rem' }}>Loading metrics...</div>;
  if (isError) return <div style={{ padding: '1rem 0', color: '#e11d48', fontSize: '0.85rem' }}>Failed to load metrics</div>;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginTop: '1.25rem', borderTop: '1px solid #f1f5f9', paddingTop: '1.25rem' }}>
      <div style={{ backgroundColor: '#f8fafc', padding: '0.85rem', borderRadius: '8px', border: '1px solid #f1f5f9' }}>
        <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: '700', letterSpacing: '0.05em' }}>Queued Jobs</div>
        <div style={{ fontSize: '1.35rem', fontWeight: '700', color: '#0f172a', marginTop: '0.2rem' }}>{data.counts.queued}</div>
      </div>
      <div style={{ backgroundColor: '#f8fafc', padding: '0.85rem', borderRadius: '8px', border: '1px solid #f1f5f9' }}>
        <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: '700', letterSpacing: '0.05em' }}>Running</div>
        <div style={{ fontSize: '1.35rem', fontWeight: '700', color: '#4f46e5', marginTop: '0.2rem' }}>{data.counts.running}</div>
      </div>
      <div style={{ backgroundColor: '#f8fafc', padding: '0.85rem', borderRadius: '8px', border: '1px solid #f1f5f9' }}>
        <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: '700', letterSpacing: '0.05em' }}>24h Throughput</div>
        <div style={{ fontSize: '1.35rem', fontWeight: '700', color: '#0f172a', marginTop: '0.2rem' }}>{data.throughput_24h}</div>
      </div>
      <div style={{ backgroundColor: '#f8fafc', padding: '0.85rem', borderRadius: '8px', border: '1px solid #f1f5f9' }}>
        <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', fontWeight: '700', letterSpacing: '0.05em' }}>24h Success Rate</div>
        <div style={{ fontSize: '1.35rem', fontWeight: '700', color: data.success_rate_24h >= 0.9 ? '#15803d' : '#9f1239', marginTop: '0.2rem' }}>
          {(data.success_rate_24h * 100).toFixed(1)}%
        </div>
      </div>
    </div>
  );
};

const RetryPolicyModal = ({ queueId, onClose }) => {
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    max_retries: 3,
    backoff_strategy: 'exponential',
    backoff_base_seconds: 60,
    backoff_max_seconds: 3600
  });

  const { data: existingPolicy, isLoading } = useQuery({
    queryKey: ['retryPolicy', queueId],
    queryFn: () => getRetryPolicy(queueId),
    retry: false, // Don't retry on 404
  });

  React.useEffect(() => {
    if (existingPolicy) {
      setFormData({
        max_retries: existingPolicy.max_retries,
        backoff_strategy: existingPolicy.backoff_strategy,
        backoff_base_seconds: existingPolicy.backoff_base_seconds,
        backoff_max_seconds: existingPolicy.backoff_max_seconds,
      });
    }
  }, [existingPolicy]);

  const saveMutation = useMutation({
    mutationFn: (data) => existingPolicy ? updateRetryPolicy(queueId, data) : createRetryPolicy(queueId, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['retryPolicy', queueId]);
      onClose();
    },
    onError: (err) => alert(err.message)
  });

  if (isLoading) return null;

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(15, 23, 42, 0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
      <div style={{ backgroundColor: 'white', padding: '2rem', borderRadius: '12px', width: '420px', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.05)', border: '1px solid #e2e8f0' }}>
        <h2 style={{ marginTop: 0, marginBottom: '1.25rem', fontSize: '1.25rem', fontWeight: '700' }}>Retry Policy</h2>
        
        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: '600', color: '#334155', marginBottom: '0.4rem' }}>Max Retries</label>
          <input type="number" min="0" value={formData.max_retries} onChange={e => setFormData({...formData, max_retries: parseInt(e.target.value)})} style={{ width: '100%', padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }} />
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: '600', color: '#334155', marginBottom: '0.4rem' }}>Backoff Strategy</label>
          <select value={formData.backoff_strategy} onChange={e => setFormData({...formData, backoff_strategy: e.target.value})} style={{ width: '100%', padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }}>
            <option value="fixed">Fixed</option>
            <option value="linear">Linear</option>
            <option value="exponential">Exponential</option>
          </select>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: '600', color: '#334155', marginBottom: '0.4rem' }}>Base Seconds</label>
          <input type="number" min="1" value={formData.backoff_base_seconds} onChange={e => setFormData({...formData, backoff_base_seconds: parseInt(e.target.value)})} style={{ width: '100%', padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }} />
        </div>

        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: '600', color: '#334155', marginBottom: '0.4rem' }}>Max Seconds</label>
          <input type="number" min="1" value={formData.backoff_max_seconds} onChange={e => setFormData({...formData, backoff_max_seconds: parseInt(e.target.value)})} style={{ width: '100%', padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }} />
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
          <button onClick={onClose} style={{ padding: '0.6rem 1.25rem', backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '8px', cursor: 'pointer', fontWeight: '500', fontSize: '0.875rem' }}>Cancel</button>
          <button onClick={() => saveMutation.mutate(formData)} disabled={saveMutation.isPending} style={{ padding: '0.6rem 1.25rem', backgroundColor: '#4f46e5', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.875rem', boxShadow: '0 2px 4px rgba(79, 70, 229, 0.25)' }}>
            Save Policy
          </button>
        </div>
      </div>
    </div>
  );
};

export const QueueOverview = () => {
  const queryClient = useQueryClient();
  const { currentProjectId: projectId } = useAuth();

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingQueue, setEditingQueue] = useState(null);
  const [retryPolicyQueueId, setRetryPolicyQueueId] = useState(null);
  
  const [queueForm, setQueueForm] = useState({ name: '', concurrency_limit: 10 });

  const { data: queuesData, isLoading, isError } = useQuery({
    queryKey: ['queues', projectId],
    queryFn: () => getQueues(projectId),
    enabled: !!projectId,
    refetchInterval: 5000,
  });

  const createMutation = useMutation({
    mutationFn: (data) => createQueue(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['queues']);
      setIsCreateModalOpen(false);
      setQueueForm({ name: '', concurrency_limit: 10 });
    },
    onError: (err) => alert(err.message)
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => updateQueue(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['queues']);
      setEditingQueue(null);
    },
    onError: (err) => alert(err.message)
  });

  const deleteMutation = useMutation({
    mutationFn: deleteQueue,
    onSuccess: () => queryClient.invalidateQueries(['queues']),
    onError: (err) => alert(`Failed to delete: ${err.message}`)
  });

  const pauseMutation = useMutation({
    mutationFn: pauseQueue,
    onSuccess: () => queryClient.invalidateQueries(['queues']),
  });

  const resumeMutation = useMutation({
    mutationFn: resumeQueue,
    onSuccess: () => queryClient.invalidateQueries(['queues']),
  });

  const handleEdit = (queue) => {
    setEditingQueue(queue.id);
    setQueueForm({ name: queue.name, concurrency_limit: queue.concurrency_limit });
  };

  if (!projectId) return <div style={{ color: '#64748b', fontSize: '0.875rem' }}>No project selected or found.</div>;
  if (isLoading) return <div style={{ color: '#64748b', fontSize: '0.875rem', padding: '2rem', textAlign: 'center' }}>Loading queues...</div>;
  if (isError) return <div style={{ color: '#e11d48', fontSize: '0.875rem', padding: '2rem', textAlign: 'center' }}>Error loading queues</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: '700', margin: '0 0 0.25rem 0', color: '#0f172a' }}>Queue Overview</h1>
          <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>Manage queue concurrency limits, retry policies, and pause/resume states</p>
        </div>
        <button 
          onClick={() => { setQueueForm({ name: '', concurrency_limit: 10 }); setIsCreateModalOpen(true); }}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.625rem 1.25rem', backgroundColor: '#4f46e5', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.875rem', boxShadow: '0 2px 6px rgba(79, 70, 229, 0.3)' }}
        >
          <Plus size={16} /> Create Queue
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '1.5rem' }}>
        {queuesData?.items?.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center', backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', color: '#64748b', fontSize: '0.875rem' }}>
            No queues found. Create one to get started.
          </div>
        ) : (
          queuesData.items.map(queue => (
            <div key={queue.id} style={{ backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '1.5rem', boxShadow: '0 1px 3px rgba(0, 0, 0, 0.04)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', marginBottom: '0.4rem' }}>
                    <h2 style={{ margin: 0, fontSize: '1.2rem', fontWeight: '700', color: '#0f172a' }}>{queue.name}</h2>
                    <StatusBadge status={queue.status} />
                  </div>
                  <div style={{ color: '#64748b', fontSize: '0.85rem' }}>
                    Concurrency Limit: <strong style={{ color: '#334155' }}>{queue.concurrency_limit}</strong>
                  </div>
                </div>
                
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <button 
                    onClick={() => setRetryPolicyQueueId(queue.id)}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0.75rem', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '8px', cursor: 'pointer', background: '#ffffff', fontSize: '0.825rem', fontWeight: '500' }}
                    title="Retry Policy"
                  >
                    <Settings size={15} /> Policy
                  </button>
                  <button 
                    onClick={() => handleEdit(queue)}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0.75rem', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '8px', cursor: 'pointer', background: '#ffffff', fontSize: '0.825rem', fontWeight: '500' }}
                    title="Edit Queue"
                  >
                    <Edit2 size={15} /> Edit
                  </button>
                  <button 
                    onClick={() => { if(window.confirm('Delete queue?')) deleteMutation.mutate(queue.id); }}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0.75rem', color: '#9f1239', border: '1px solid #fecdd3', borderRadius: '8px', cursor: 'pointer', background: '#ffe4e6', fontSize: '0.825rem', fontWeight: '500' }}
                    title="Delete Queue"
                  >
                    <Trash2 size={15} />
                  </button>
                  
                  {queue.status === 'active' ? (
                    <button 
                      onClick={() => pauseMutation.mutate(queue.id)}
                      disabled={pauseMutation.isPending}
                      style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.5rem 1rem', backgroundColor: '#fef3c7', color: '#92400e', border: '1px solid #fde68a', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.85rem' }}
                    >
                      <Pause size={15} /> Pause
                    </button>
                  ) : (
                    <button 
                      onClick={() => resumeMutation.mutate(queue.id)}
                      disabled={resumeMutation.isPending}
                      style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.5rem 1rem', backgroundColor: '#dcfce7', color: '#15803d', border: '1px solid #bbf7d0', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.85rem' }}
                    >
                      <Play size={15} /> Resume
                    </button>
                  )}
                </div>
              </div>

              <QueueMetricsCard queueId={queue.id} />
            </div>
          ))
        )}
      </div>

      {/* Create/Edit Queue Modal */}
      {(isCreateModalOpen || editingQueue) && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(15, 23, 42, 0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ backgroundColor: 'white', padding: '2rem', borderRadius: '12px', width: '420px', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.05)', border: '1px solid #e2e8f0' }}>
            <h2 style={{ marginTop: 0, marginBottom: '1.25rem', fontSize: '1.25rem', fontWeight: '700' }}>{editingQueue ? 'Edit Queue' : 'Create Queue'}</h2>
            
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: '600', color: '#334155', marginBottom: '0.4rem' }}>Queue Name</label>
              <input 
                type="text" 
                value={queueForm.name} 
                onChange={(e) => setQueueForm({...queueForm, name: e.target.value})} 
                style={{ width: '100%', padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }}
                disabled={!!editingQueue}
              />
            </div>
            
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: '600', color: '#334155', marginBottom: '0.4rem' }}>Concurrency Limit</label>
              <input 
                type="number" 
                min="1"
                value={queueForm.concurrency_limit} 
                onChange={(e) => setQueueForm({...queueForm, concurrency_limit: parseInt(e.target.value)})} 
                style={{ width: '100%', padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button 
                onClick={() => { setIsCreateModalOpen(false); setEditingQueue(null); }}
                style={{ padding: '0.6rem 1.25rem', backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '8px', cursor: 'pointer', fontWeight: '500', fontSize: '0.875rem' }}
              >
                Cancel
              </button>
              <button 
                onClick={() => {
                  if (editingQueue) {
                    updateMutation.mutate({ id: editingQueue, data: { concurrency_limit: queueForm.concurrency_limit }});
                  } else {
                    createMutation.mutate(queueForm);
                  }
                }}
                disabled={!queueForm.name || createMutation.isPending || updateMutation.isPending}
                style={{ padding: '0.6rem 1.25rem', backgroundColor: '#4f46e5', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.875rem', boxShadow: '0 2px 4px rgba(79, 70, 229, 0.25)' }}
              >
                {editingQueue ? 'Save Changes' : 'Create Queue'}
              </button>
            </div>
          </div>
        </div>
      )}

      {retryPolicyQueueId && (
        <RetryPolicyModal queueId={retryPolicyQueueId} onClose={() => setRetryPolicyQueueId(null)} />
      )}
    </div>
  );
};
