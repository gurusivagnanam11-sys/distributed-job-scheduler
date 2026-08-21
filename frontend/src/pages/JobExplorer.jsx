import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getJobs, getQueues, getCurrentProject, submitJob } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { format } from 'date-fns';
import { Plus, RefreshCw } from 'lucide-react';
import { retryJob } from '../api/client';

const JOB_STATUSES = [
  'queued', 'scheduled', 'claimed', 'running', 
  'completed', 'failed', 'retrying', 'dead_letter'
];

const SubmitJobModal = ({ queueId, onClose }) => {
  const queryClient = useQueryClient();
  const [jobType, setJobType] = useState('immediate'); // immediate, delayed, recurring, batch
  const [priority, setPriority] = useState(0);
  const [dedupeKey, setDedupeKey] = useState('');
  const [dependsOn, setDependsOn] = useState('');
  const [scheduledAt, setScheduledAt] = useState('');
  const [cronExpression, setCronExpression] = useState('');
  const [payloadStr, setPayloadStr] = useState('{}');
  const [batchPayloads, setBatchPayloads] = useState(['{}']);
  const [errorMsg, setErrorMsg] = useState('');

  const submitMutation = useMutation({
    mutationFn: (data) => submitJob(queueId, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['jobs', queueId]);
      queryClient.invalidateQueries(['queueMetrics']);
      onClose();
    },
    onError: (err) => {
      setErrorMsg(err.message);
    }
  });

  const handleSubmit = () => {
    setErrorMsg('');
    try {
      let data = {
        priority: parseInt(priority, 10) || 0,
        dedupe_key: dedupeKey || null,
        depends_on_job_id: dependsOn || null,
      };

      if (jobType === 'batch') {
        const batchArr = batchPayloads.map((p, idx) => {
          try {
            return { payload: JSON.parse(p) };
          } catch (err) {
            throw new Error(`Invalid JSON in batch item ${idx + 1}`);
          }
        });
        if (batchArr.length === 0) throw new Error("Batch must contain at least one job");
        data = { batch: batchArr };
      } else {
        data.payload = JSON.parse(payloadStr);
        if (jobType === 'delayed') {
          if (!scheduledAt) throw new Error("Scheduled At is required for delayed jobs");
          data.scheduled_at = new Date(scheduledAt).toISOString();
        } else if (jobType === 'recurring') {
          if (!cronExpression) throw new Error("Cron expression is required for recurring jobs");
          data.cron_expression = cronExpression;
        }
      }

      submitMutation.mutate(data);
    } catch (e) {
      setErrorMsg(e.message);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
      <div style={{ backgroundColor: 'white', padding: '2rem', borderRadius: '8px', width: '500px', maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
        <h2 style={{ marginTop: 0, marginBottom: '1.5rem' }}>Submit Job</h2>

        {errorMsg && (
          <div style={{ backgroundColor: '#fef2f2', color: '#b91c1c', padding: '0.75rem', borderRadius: '4px', marginBottom: '1rem', fontSize: '0.875rem' }}>
            {errorMsg}
          </div>
        )}

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>Job Type</label>
          <select value={jobType} onChange={e => setJobType(e.target.value)} style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db' }}>
            <option value="immediate">Immediate</option>
            <option value="delayed">Delayed / Scheduled</option>
            <option value="recurring">Recurring</option>
            <option value="batch">Batch</option>
          </select>
        </div>

        {jobType !== 'batch' && (
          <>
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>Priority (higher = more urgent)</label>
              <input type="number" value={priority} onChange={e => setPriority(e.target.value)} style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db' }} />
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>Dedupe Key (Optional)</label>
              <input type="text" value={dedupeKey} onChange={e => setDedupeKey(e.target.value)} style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db' }} placeholder="e.g. daily_report_2026_08_21" />
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>Depends On Job ID (Optional)</label>
              <input type="text" value={dependsOn} onChange={e => setDependsOn(e.target.value)} style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db' }} placeholder="UUID of dependency" />
            </div>
          </>
        )}

        {jobType === 'delayed' && (
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>Scheduled At</label>
            <input type="datetime-local" value={scheduledAt} onChange={e => setScheduledAt(e.target.value)} style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db' }} />
          </div>
        )}

        {jobType === 'recurring' && (
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>Cron Expression</label>
            <input type="text" value={cronExpression} onChange={e => setCronExpression(e.target.value)} style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db' }} placeholder="* * * * *" />
          </div>
        )}

        {jobType === 'batch' ? (
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>
              Batch Payloads
            </label>
            {batchPayloads.map((payload, idx) => (
              <div key={idx} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', alignItems: 'flex-start' }}>
                <textarea 
                  value={payload} 
                  onChange={e => {
                    const newPayloads = [...batchPayloads];
                    newPayloads[idx] = e.target.value;
                    setBatchPayloads(newPayloads);
                  }}
                  style={{ flex: 1, padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db', minHeight: '60px', fontFamily: 'monospace', fontSize: '0.875rem' }} 
                />
                <button 
                  onClick={() => {
                    const newPayloads = batchPayloads.filter((_, i) => i !== idx);
                    setBatchPayloads(newPayloads);
                  }}
                  disabled={batchPayloads.length === 1}
                  style={{ padding: '0.5rem', backgroundColor: '#fee2e2', color: '#ef4444', border: '1px solid #fca5a5', borderRadius: '4px', cursor: batchPayloads.length === 1 ? 'not-allowed' : 'pointer', flexShrink: 0 }}
                >
                  Remove
                </button>
              </div>
            ))}
            <button 
              onClick={() => setBatchPayloads([...batchPayloads, '{}'])}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', backgroundColor: '#f3f4f6', color: '#4b5563', border: '1px solid #d1d5db', borderRadius: '4px', cursor: 'pointer', fontSize: '0.875rem' }}
            >
              <Plus size={16} /> Add Job to Batch
            </button>
          </div>
        ) : (
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>
              Job Payload (JSON Object)
            </label>
            <textarea 
              value={payloadStr} 
              onChange={e => setPayloadStr(e.target.value)} 
              style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db', minHeight: '120px', fontFamily: 'monospace', fontSize: '0.875rem' }} 
            />
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
          <button onClick={onClose} style={{ padding: '0.5rem 1rem', backgroundColor: 'white', border: '1px solid #d1d5db', borderRadius: '4px', cursor: 'pointer' }}>Cancel</button>
          <button onClick={handleSubmit} disabled={submitMutation.isPending} style={{ padding: '0.5rem 1rem', backgroundColor: '#2563eb', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
            {submitMutation.isPending ? 'Submitting...' : 'Submit'}
          </button>
        </div>
      </div>
    </div>
  );
};

export const JobExplorer = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const projectId = getCurrentProject();
  
  const [selectedQueue, setSelectedQueue] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const [isSubmitModalOpen, setIsSubmitModalOpen] = useState(false);

  // Fetch queues for the dropdown
  const { data: queuesData } = useQuery({
    queryKey: ['queues', projectId],
    queryFn: () => getQueues(projectId),
    enabled: !!projectId,
  });

  // Automatically select first queue if none selected
  React.useEffect(() => {
    if (queuesData?.items?.length > 0 && !selectedQueue) {
      setSelectedQueue(queuesData.items[0].id);
    }
  }, [queuesData, selectedQueue]);

  const { data: jobsData, isLoading, isError } = useQuery({
    queryKey: ['jobs', selectedQueue, page, selectedStatus],
    queryFn: () => getJobs(selectedQueue, page, pageSize, selectedStatus || null),
    enabled: !!selectedQueue,
    refetchInterval: 5000,
  });

  const retryJobMutation = useMutation({
    mutationFn: retryJob,
    onSuccess: () => queryClient.invalidateQueries(['jobs']),
    onError: (err) => alert(`Retry failed: ${err.message}`)
  });

  if (!projectId) return <div>No project found.</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 'bold', margin: 0 }}>Job Explorer</h1>
        <button 
          onClick={() => setIsSubmitModalOpen(true)}
          disabled={!selectedQueue}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', backgroundColor: '#2563eb', color: 'white', border: 'none', borderRadius: '6px', cursor: selectedQueue ? 'pointer' : 'not-allowed', fontWeight: '500', opacity: selectedQueue ? 1 : 0.5 }}
        >
          <Plus size={16} /> Submit Job
        </button>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', backgroundColor: 'white', padding: '1rem', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <label style={{ fontSize: '0.75rem', fontWeight: '600', color: '#4b5563', marginBottom: '0.25rem' }}>Queue</label>
          <select 
            value={selectedQueue} 
            onChange={(e) => { setSelectedQueue(e.target.value); setPage(1); }}
            style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db', minWidth: '200px' }}
          >
            {queuesData?.items?.map(q => (
              <option key={q.id} value={q.id}>{q.name}</option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <label style={{ fontSize: '0.75rem', fontWeight: '600', color: '#4b5563', marginBottom: '0.25rem' }}>Status</label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <select 
              value={selectedStatus} 
              onChange={(e) => { setSelectedStatus(e.target.value); setPage(1); }}
              style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db', minWidth: '150px' }}
            >
              <option value="">All Statuses</option>
              {JOB_STATUSES.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <button 
              onClick={() => { setSelectedStatus('dead_letter'); setPage(1); }}
              style={{ padding: '0.5rem 1rem', backgroundColor: selectedStatus === 'dead_letter' ? '#fee2e2' : 'white', color: selectedStatus === 'dead_letter' ? '#b91c1c' : '#4b5563', border: `1px solid ${selectedStatus === 'dead_letter' ? '#fca5a5' : '#d1d5db'}`, borderRadius: '4px', cursor: 'pointer', fontSize: '0.875rem' }}
            >
              Show Dead Letter
            </button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div style={{ backgroundColor: 'white', borderRadius: '8px', border: '1px solid #e5e7eb', overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#6b7280' }}>Loading jobs...</div>
        ) : isError ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#ef4444' }}>Error loading jobs</div>
        ) : jobsData?.items?.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#6b7280' }}>No jobs found matching criteria.</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ backgroundColor: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase' }}>ID</th>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase' }}>Status</th>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase' }}>Priority</th>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase' }}>Attempts</th>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase' }}>Scheduled At</th>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase' }}>Created At</th>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobsData.items.map((job) => (
                <tr 
                  key={job.id} 
                  onClick={() => navigate(`/jobs/${job.id}`)}
                  style={{ borderBottom: '1px solid #e5e7eb', cursor: 'pointer' }}
                  onMouseOver={e => e.currentTarget.style.backgroundColor = '#f9fafb'}
                  onMouseOut={e => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  <td style={{ padding: '0.75rem 1rem', fontSize: '0.875rem', fontFamily: 'monospace' }}>{job.id.substring(0, 8)}...</td>
                  <td style={{ padding: '0.75rem 1rem' }}><StatusBadge status={job.status} /></td>
                  <td style={{ padding: '0.75rem 1rem', fontSize: '0.875rem' }}>{job.priority}</td>
                  <td style={{ padding: '0.75rem 1rem', fontSize: '0.875rem' }}>{job.attempt_count}</td>
                  <td style={{ padding: '0.75rem 1rem', fontSize: '0.875rem', color: '#4b5563' }}>
                    {format(new Date(job.scheduled_at), 'MMM d, HH:mm:ss')}
                  </td>
                  <td style={{ padding: '0.75rem 1rem', fontSize: '0.875rem', color: '#4b5563' }}>
                    {format(new Date(job.created_at), 'MMM d, HH:mm:ss')}
                  </td>
                  <td style={{ padding: '0.75rem 1rem', textAlign: 'right' }} onClick={e => e.stopPropagation()}>
                    {job.status === 'dead_letter' && (
                      <button 
                        onClick={() => retryJobMutation.mutate(job.id)}
                        disabled={retryJobMutation.isPending}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem 0.5rem', backgroundColor: '#eff6ff', color: '#2563eb', border: '1px solid #bfdbfe', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem', fontWeight: '500', marginLeft: 'auto' }}
                        title="Retry Job"
                      >
                        <RefreshCw size={12} /> Retry
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        
        {/* Pagination */}
        {jobsData?.total > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', borderTop: '1px solid #e5e7eb' }}>
            <div style={{ fontSize: '0.875rem', color: '#4b5563' }}>
              Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, jobsData.total)} of {jobsData.total} results
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button 
                disabled={page === 1}
                onClick={() => setPage(p => p - 1)}
                style={{ padding: '0.5rem 1rem', border: '1px solid #d1d5db', borderRadius: '4px', background: 'white', cursor: page === 1 ? 'not-allowed' : 'pointer' }}
              >
                Previous
              </button>
              <button 
                disabled={page * pageSize >= jobsData.total}
                onClick={() => setPage(p => p + 1)}
                style={{ padding: '0.5rem 1rem', border: '1px solid #d1d5db', borderRadius: '4px', background: 'white', cursor: page * pageSize >= jobsData.total ? 'not-allowed' : 'pointer' }}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {isSubmitModalOpen && selectedQueue && (
        <SubmitJobModal queueId={selectedQueue} onClose={() => setIsSubmitModalOpen(false)} />
      )}
    </div>
  );
};
