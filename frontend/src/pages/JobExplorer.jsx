import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../components/AuthProvider';
import { getJobs, getQueues, submitJob } from '../api/client';
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
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(15, 23, 42, 0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
      <div style={{ backgroundColor: 'white', padding: '2rem', borderRadius: '12px', width: '520px', maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.05)', border: '1px solid #e2e8f0' }}>
        <h2 style={{ marginTop: 0, marginBottom: '1.5rem', fontSize: '1.25rem', fontWeight: '700' }}>Submit Job</h2>

        {errorMsg && (
          <div style={{ backgroundColor: '#ffe4e6', color: '#9f1239', border: '1px solid #fecdd3', padding: '0.75rem', borderRadius: '8px', marginBottom: '1.25rem', fontSize: '0.85rem', fontWeight: '500' }}>
            {errorMsg}
          </div>
        )}

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: '600', color: '#334155', marginBottom: '0.4rem' }}>Job Type</label>
          <select value={jobType} onChange={e => setJobType(e.target.value)} style={{ width: '100%', padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }}>
            <option value="immediate">Immediate</option>
            <option value="delayed">Delayed / Scheduled</option>
            <option value="recurring">Recurring</option>
            <option value="batch">Batch</option>
          </select>
        </div>

        {jobType !== 'batch' && (
          <>
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: '600', color: '#334155', marginBottom: '0.4rem' }}>Priority (higher = more urgent)</label>
              <input type="number" value={priority} onChange={e => setPriority(e.target.value)} style={{ width: '100%', padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }} />
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: '600', color: '#334155', marginBottom: '0.4rem' }}>Dedupe Key (Optional)</label>
              <input type="text" value={dedupeKey} onChange={e => setDedupeKey(e.target.value)} style={{ width: '100%', padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }} placeholder="e.g. daily_report_2026_08_21" />
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: '600', color: '#334155', marginBottom: '0.4rem' }}>Depends On Job ID (Optional)</label>
              <input type="text" value={dependsOn} onChange={e => setDependsOn(e.target.value)} style={{ width: '100%', padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }} placeholder="UUID of dependency" />
            </div>
          </>
        )}

        {jobType === 'delayed' && (
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: '600', color: '#334155', marginBottom: '0.4rem' }}>Scheduled At</label>
            <input type="datetime-local" value={scheduledAt} onChange={e => setScheduledAt(e.target.value)} style={{ width: '100%', padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }} />
          </div>
        )}

        {jobType === 'recurring' && (
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: '600', color: '#334155', marginBottom: '0.4rem' }}>Cron Expression</label>
            <input type="text" value={cronExpression} onChange={e => setCronExpression(e.target.value)} style={{ width: '100%', padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }} placeholder="* * * * *" />
          </div>
        )}

        {jobType === 'batch' ? (
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: '600', color: '#334155', marginBottom: '0.4rem' }}>
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
                  style={{ flex: 1, padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', minHeight: '60px', fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }} 
                />
                <button 
                  onClick={() => {
                    const newPayloads = batchPayloads.filter((_, i) => i !== idx);
                    setBatchPayloads(newPayloads);
                  }}
                  disabled={batchPayloads.length === 1}
                  style={{ padding: '0.55rem 0.75rem', backgroundColor: '#ffe4e6', color: '#9f1239', border: '1px solid #fecdd3', borderRadius: '8px', cursor: batchPayloads.length === 1 ? 'not-allowed' : 'pointer', flexShrink: 0, fontSize: '0.825rem', fontWeight: '500' }}
                >
                  Remove
                </button>
              </div>
            ))}
            <button 
              onClick={() => setBatchPayloads([...batchPayloads, '{}'])}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', backgroundColor: '#f1f5f9', color: '#334155', border: '1px solid #cbd5e1', borderRadius: '8px', cursor: 'pointer', fontSize: '0.85rem', fontWeight: '500' }}
            >
              <Plus size={16} /> Add Job to Batch
            </button>
          </div>
        ) : (
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '0.825rem', fontWeight: '600', color: '#334155', marginBottom: '0.4rem' }}>
              Job Payload (JSON Object)
            </label>
            <textarea 
              value={payloadStr} 
              onChange={e => setPayloadStr(e.target.value)} 
              style={{ width: '100%', padding: '0.6rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', minHeight: '120px', fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }} 
            />
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
          <button onClick={onClose} style={{ padding: '0.6rem 1.25rem', backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '8px', cursor: 'pointer', fontWeight: '500', fontSize: '0.875rem' }}>Cancel</button>
          <button onClick={handleSubmit} disabled={submitMutation.isPending} style={{ padding: '0.6rem 1.25rem', backgroundColor: '#4f46e5', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.875rem', boxShadow: '0 2px 4px rgba(79, 70, 229, 0.25)' }}>
            {submitMutation.isPending ? 'Submitting...' : 'Submit Job'}
          </button>
        </div>
      </div>
    </div>
  );
};

export const JobExplorer = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { currentProjectId: projectId } = useAuth();
  
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

  if (!projectId) return <div style={{ color: '#64748b', fontSize: '0.875rem' }}>No project selected.</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: '700', margin: '0 0 0.25rem 0', color: '#0f172a' }}>Job Explorer</h1>
          <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>Monitor, inspect, and submit background jobs across queues</p>
        </div>
        <button 
          onClick={() => setIsSubmitModalOpen(true)}
          disabled={!selectedQueue}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.625rem 1.25rem', backgroundColor: '#4f46e5', color: 'white', border: 'none', borderRadius: '8px', cursor: selectedQueue ? 'pointer' : 'not-allowed', fontWeight: '600', fontSize: '0.875rem', opacity: selectedQueue ? 1 : 0.5, boxShadow: '0 2px 6px rgba(79, 70, 229, 0.3)' }}
        >
          <Plus size={16} /> Submit Job
        </button>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '1.25rem', marginBottom: '1.5rem', backgroundColor: '#ffffff', padding: '1.25rem', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.04)', alignItems: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <label style={{ fontSize: '0.7rem', fontWeight: '700', color: '#64748b', marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Queue</label>
          <select 
            value={selectedQueue} 
            onChange={(e) => { setSelectedQueue(e.target.value); setPage(1); }}
            style={{ padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', minWidth: '220px', fontSize: '0.875rem' }}
          >
            {queuesData?.items?.map(q => (
              <option key={q.id} value={q.id}>{q.name}</option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <label style={{ fontSize: '0.7rem', fontWeight: '700', color: '#64748b', marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Status Filter</label>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <select 
              value={selectedStatus} 
              onChange={(e) => { setSelectedStatus(e.target.value); setPage(1); }}
              style={{ padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', minWidth: '160px', fontSize: '0.875rem' }}
            >
              <option value="">All Statuses</option>
              {JOB_STATUSES.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <button 
              onClick={() => { setSelectedStatus(selectedStatus === 'dead_letter' ? '' : 'dead_letter'); setPage(1); }}
              style={{ padding: '0.55rem 1rem', backgroundColor: selectedStatus === 'dead_letter' ? '#ffe4e6' : '#ffffff', color: selectedStatus === 'dead_letter' ? '#9f1239' : '#475569', border: `1px solid ${selectedStatus === 'dead_letter' ? '#fecdd3' : '#cbd5e1'}`, borderRadius: '8px', cursor: 'pointer', fontSize: '0.85rem', fontWeight: '600', transition: 'all 0.15s ease' }}
            >
              Show Dead Letter
            </button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.04)', overflow: 'hidden' }}>
        {!selectedQueue ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b', fontSize: '0.875rem' }}>Please select or create a queue to view jobs.</div>
        ) : isLoading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b', fontSize: '0.875rem' }}>Loading jobs...</div>
        ) : isError ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#e11d48', fontSize: '0.875rem' }}>Error loading jobs</div>
        ) : !jobsData?.items || jobsData.items.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b', fontSize: '0.875rem' }}>No jobs found matching the selected criteria.</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0, textAlign: 'left' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8fafc' }}>
                <th style={{ padding: '0.75rem 1.25rem' }}>ID</th>
                <th style={{ padding: '0.75rem 1.25rem' }}>Status</th>
                <th style={{ padding: '0.75rem 1.25rem' }}>Priority</th>
                <th style={{ padding: '0.75rem 1.25rem' }}>Attempts</th>
                <th style={{ padding: '0.75rem 1.25rem' }}>Scheduled At</th>
                <th style={{ padding: '0.75rem 1.25rem' }}>Created At</th>
                <th style={{ padding: '0.75rem 1.25rem', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobsData.items.map((job) => (
                <tr 
                  key={job.id} 
                  onClick={() => navigate(`/jobs/${job.id}`)}
                  style={{ borderBottom: '1px solid #e2e8f0', cursor: 'pointer', transition: 'background-color 0.15s ease' }}
                  onMouseOver={e => e.currentTarget.style.backgroundColor = '#f8fafc'}
                  onMouseOut={e => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  <td style={{ padding: '0.85rem 1.25rem', fontSize: '0.85rem', fontFamily: 'var(--font-mono)', color: '#4f46e5', fontWeight: '500' }}>{job.id.substring(0, 8)}...</td>
                  <td style={{ padding: '0.85rem 1.25rem' }}><StatusBadge status={job.status} /></td>
                  <td style={{ padding: '0.85rem 1.25rem', fontSize: '0.875rem', fontWeight: '600', color: '#334155' }}>{job.priority}</td>
                  <td style={{ padding: '0.85rem 1.25rem', fontSize: '0.875rem', color: '#475569' }}>{job.attempt_count}</td>
                  <td style={{ padding: '0.85rem 1.25rem', fontSize: '0.85rem', color: '#64748b' }}>
                    {format(new Date(job.scheduled_at), 'MMM d, HH:mm:ss')}
                  </td>
                  <td style={{ padding: '0.85rem 1.25rem', fontSize: '0.85rem', color: '#64748b' }}>
                    {format(new Date(job.created_at), 'MMM d, HH:mm:ss')}
                  </td>
                  <td style={{ padding: '0.85rem 1.25rem', textAlign: 'right' }} onClick={e => e.stopPropagation()}>
                    {job.status === 'dead_letter' && (
                      <button 
                        onClick={() => retryJobMutation.mutate(job.id)}
                        disabled={retryJobMutation.isPending}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', padding: '0.35rem 0.75rem', backgroundColor: '#e0e7ff', color: '#3730a3', border: '1px solid #c7d2fe', borderRadius: '6px', cursor: 'pointer', fontSize: '0.75rem', fontWeight: '600' }}
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
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem 1.25rem', borderTop: '1px solid #e2e8f0', backgroundColor: '#ffffff' }}>
            <div style={{ fontSize: '0.85rem', color: '#64748b' }}>
              Showing <strong style={{ color: '#0f172a' }}>{((page - 1) * pageSize) + 1}</strong> to <strong style={{ color: '#0f172a' }}>{Math.min(page * pageSize, jobsData.total)}</strong> of <strong style={{ color: '#0f172a' }}>{jobsData.total}</strong> results
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button 
                disabled={page === 1}
                onClick={() => setPage(p => p - 1)}
                style={{ padding: '0.45rem 0.85rem', border: '1px solid #cbd5e1', borderRadius: '6px', background: '#ffffff', color: '#334155', cursor: page === 1 ? 'not-allowed' : 'pointer', opacity: page === 1 ? 0.5 : 1, fontSize: '0.85rem', fontWeight: '500' }}
              >
                Previous
              </button>
              <button 
                disabled={page * pageSize >= jobsData.total}
                onClick={() => setPage(p => p + 1)}
                style={{ padding: '0.45rem 0.85rem', border: '1px solid #cbd5e1', borderRadius: '6px', background: '#ffffff', color: '#334155', cursor: page * pageSize >= jobsData.total ? 'not-allowed' : 'pointer', opacity: page * pageSize >= jobsData.total ? 0.5 : 1, fontSize: '0.85rem', fontWeight: '500' }}
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
