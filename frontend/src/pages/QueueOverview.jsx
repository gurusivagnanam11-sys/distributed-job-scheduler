import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getQueues, pauseQueue, resumeQueue, getQueueMetrics, getCurrentProject,
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

  if (isLoading) return <div style={{ padding: '1rem', color: '#6b7280' }}>Loading metrics...</div>;
  if (isError) return <div style={{ padding: '1rem', color: '#ef4444' }}>Failed to load metrics</div>;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginTop: '1rem', borderTop: '1px solid #e5e7eb', paddingTop: '1rem' }}>
      <div>
        <div style={{ fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase' }}>Queued</div>
        <div style={{ fontSize: '1.25rem', fontWeight: '600' }}>{data.counts.queued}</div>
      </div>
      <div>
        <div style={{ fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase' }}>Running</div>
        <div style={{ fontSize: '1.25rem', fontWeight: '600', color: '#1d4ed8' }}>{data.counts.running}</div>
      </div>
      <div>
        <div style={{ fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase' }}>24h Throughput</div>
        <div style={{ fontSize: '1.25rem', fontWeight: '600' }}>{data.throughput_24h}</div>
      </div>
      <div>
        <div style={{ fontSize: '0.75rem', color: '#6b7280', textTransform: 'uppercase' }}>24h Success Rate</div>
        <div style={{ fontSize: '1.25rem', fontWeight: '600', color: data.success_rate_24h >= 0.9 ? '#15803d' : '#b91c1c' }}>
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
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
      <div style={{ backgroundColor: 'white', padding: '2rem', borderRadius: '8px', width: '400px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
        <h2 style={{ marginTop: 0, marginBottom: '1.5rem' }}>Retry Policy</h2>
        
        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>Max Retries</label>
          <input type="number" min="0" value={formData.max_retries} onChange={e => setFormData({...formData, max_retries: parseInt(e.target.value)})} style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db' }} />
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>Backoff Strategy</label>
          <select value={formData.backoff_strategy} onChange={e => setFormData({...formData, backoff_strategy: e.target.value})} style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db' }}>
            <option value="fixed">Fixed</option>
            <option value="linear">Linear</option>
            <option value="exponential">Exponential</option>
          </select>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>Base Seconds</label>
          <input type="number" min="1" value={formData.backoff_base_seconds} onChange={e => setFormData({...formData, backoff_base_seconds: parseInt(e.target.value)})} style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db' }} />
        </div>

        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>Max Seconds</label>
          <input type="number" min="1" value={formData.backoff_max_seconds} onChange={e => setFormData({...formData, backoff_max_seconds: parseInt(e.target.value)})} style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db' }} />
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
          <button onClick={onClose} style={{ padding: '0.5rem 1rem', backgroundColor: 'white', border: '1px solid #d1d5db', borderRadius: '4px', cursor: 'pointer' }}>Cancel</button>
          <button onClick={() => saveMutation.mutate(formData)} disabled={saveMutation.isPending} style={{ padding: '0.5rem 1rem', backgroundColor: '#2563eb', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
            Save
          </button>
        </div>
      </div>
    </div>
  );
};

export const QueueOverview = () => {
  const queryClient = useQueryClient();
  const projectId = getCurrentProject();

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

  if (!projectId) return <div>No project selected or found.</div>;
  if (isLoading) return <div>Loading queues...</div>;
  if (isError) return <div style={{ color: 'red' }}>Error loading queues</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 'bold', margin: 0 }}>Queue Overview</h1>
        <button 
          onClick={() => { setQueueForm({ name: '', concurrency_limit: 10 }); setIsCreateModalOpen(true); }}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', backgroundColor: '#2563eb', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '500' }}
        >
          <Plus size={16} /> Create Queue
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '1.5rem' }}>
        {queuesData?.items?.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', backgroundColor: 'white', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
            No queues found. Create one to get started.
          </div>
        ) : (
          queuesData.items.map(queue => (
            <div key={queue.id} style={{ backgroundColor: 'white', borderRadius: '8px', border: '1px solid #e5e7eb', padding: '1.5rem', boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '0.5rem' }}>
                    <h2 style={{ margin: 0, fontSize: '1.25rem' }}>{queue.name}</h2>
                    <StatusBadge status={queue.status} />
                  </div>
                  <div style={{ color: '#6b7280', fontSize: '0.875rem' }}>
                    Concurrency Limit: <strong>{queue.concurrency_limit}</strong>
                  </div>
                </div>
                
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button 
                    onClick={() => setRetryPolicyQueueId(queue.id)}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem', color: '#4b5563', border: '1px solid #d1d5db', borderRadius: '6px', cursor: 'pointer', background: 'white' }}
                    title="Retry Policy"
                  >
                    <Settings size={16} />
                  </button>
                  <button 
                    onClick={() => handleEdit(queue)}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem', color: '#4b5563', border: '1px solid #d1d5db', borderRadius: '6px', cursor: 'pointer', background: 'white' }}
                    title="Edit Queue"
                  >
                    <Edit2 size={16} />
                  </button>
                  <button 
                    onClick={() => { if(window.confirm('Delete queue?')) deleteMutation.mutate(queue.id); }}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem', color: '#ef4444', border: '1px solid #fca5a5', borderRadius: '6px', cursor: 'pointer', background: '#fef2f2' }}
                    title="Delete Queue"
                  >
                    <Trash2 size={16} />
                  </button>
                  
                  {queue.status === 'active' ? (
                    <button 
                      onClick={() => pauseMutation.mutate(queue.id)}
                      disabled={pauseMutation.isPending}
                      style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', backgroundColor: '#fef08a', color: '#854d0e', border: '1px solid #fde047', borderRadius: '6px', cursor: 'pointer', fontWeight: '500' }}
                    >
                      <Pause size={16} /> Pause
                    </button>
                  ) : (
                    <button 
                      onClick={() => resumeMutation.mutate(queue.id)}
                      disabled={resumeMutation.isPending}
                      style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', backgroundColor: '#dcfce7', color: '#15803d', border: '1px solid #bbf7d0', borderRadius: '6px', cursor: 'pointer', fontWeight: '500' }}
                    >
                      <Play size={16} /> Resume
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
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ backgroundColor: 'white', padding: '2rem', borderRadius: '8px', width: '400px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
            <h2 style={{ marginTop: 0, marginBottom: '1.5rem' }}>{editingQueue ? 'Edit Queue' : 'Create Queue'}</h2>
            
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>Name</label>
              <input 
                type="text" 
                value={queueForm.name} 
                onChange={(e) => setQueueForm({...queueForm, name: e.target.value})} 
                style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db' }}
                disabled={!!editingQueue} // Usually name is immutable or we can allow it
              />
            </div>
            
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>Concurrency Limit</label>
              <input 
                type="number" 
                min="1"
                value={queueForm.concurrency_limit} 
                onChange={(e) => setQueueForm({...queueForm, concurrency_limit: parseInt(e.target.value)})} 
                style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db' }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
              <button 
                onClick={() => { setIsCreateModalOpen(false); setEditingQueue(null); }}
                style={{ padding: '0.5rem 1rem', backgroundColor: 'white', border: '1px solid #d1d5db', borderRadius: '4px', cursor: 'pointer' }}
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
                style={{ padding: '0.5rem 1rem', backgroundColor: '#2563eb', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
              >
                Save
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
