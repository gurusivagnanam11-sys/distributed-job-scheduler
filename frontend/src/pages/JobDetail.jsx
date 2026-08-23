import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getJob, getJobTimeline, getJobExecutions, retryJob, getJobFailureSummary } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { format } from 'date-fns';
import { ArrowLeft, RefreshCw } from 'lucide-react';

export const JobDetail = () => {
  const { id } = useParams();
  const queryClient = useQueryClient();

  const { data: job, isLoading: jobLoading } = useQuery({
    queryKey: ['job', id],
    queryFn: () => getJob(id),
    refetchInterval: 5000,
  });

  const { data: timeline } = useQuery({
    queryKey: ['jobTimeline', id],
    queryFn: () => getJobTimeline(id),
    refetchInterval: 5000,
  });

  const { data: executions } = useQuery({
    queryKey: ['jobExecutions', id],
    queryFn: () => getJobExecutions(id),
    refetchInterval: 5000,
  });

  const hasFailedExecution = executions?.items?.some(e => e.status === 'failed');

  const { data: failureSummary, isLoading: failureSummaryLoading } = useQuery({
    queryKey: ['jobFailureSummary', id],
    queryFn: () => getJobFailureSummary(id),
    enabled: !!hasFailedExecution,
    retry: false,
  });

  const retryMutation = useMutation({
    mutationFn: retryJob,
    onSuccess: () => {
      queryClient.invalidateQueries(['job', id]);
      queryClient.invalidateQueries(['jobTimeline', id]);
      queryClient.invalidateQueries(['jobExecutions', id]);
      alert('Job retry initiated successfully');
    },
    onError: (error) => {
      alert(`Retry failed: ${error.message}`);
    }
  });

  if (jobLoading) return <div style={{ color: '#64748b', fontSize: '0.875rem', padding: '2rem', textAlign: 'center' }}>Loading job details...</div>;
  if (!job) return <div style={{ color: '#e11d48', fontSize: '0.875rem', padding: '2rem', textAlign: 'center' }}>Job not found</div>;

  return (
    <div>
      <div style={{ marginBottom: '1.25rem' }}>
        <Link to="/" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', color: '#64748b', textDecoration: 'none', fontSize: '0.85rem', fontWeight: '500', transition: 'color 0.15s ease' }} onMouseOver={e => e.currentTarget.style.color = '#4f46e5'} onMouseOut={e => e.currentTarget.style.color = '#64748b'}>
          <ArrowLeft size={16} /> Back to Explorer
        </Link>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.75rem', backgroundColor: '#ffffff', padding: '1.5rem', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
        <div>
          <span style={{ fontSize: '0.7rem', fontWeight: '700', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: '0.25rem' }}>JOB ID</span>
          <h1 style={{ fontSize: '1.35rem', fontWeight: '700', margin: '0 0 0.75rem 0', fontFamily: 'var(--font-mono)', color: '#0f172a' }}>{job.id}</h1>
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <StatusBadge status={job.status} />
            <span style={{ fontSize: '0.85rem', color: '#64748b' }}>Queue ID: <span style={{ fontFamily: 'var(--font-mono)', color: '#334155', fontWeight: '500' }}>{job.queue_id}</span></span>
          </div>
        </div>

        {job.status === 'dead_letter' && (
          <button 
            onClick={() => retryMutation.mutate(id)}
            disabled={retryMutation.isPending}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', padding: '0.6rem 1.25rem', backgroundColor: '#4f46e5', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.875rem', boxShadow: '0 2px 4px rgba(79, 70, 229, 0.25)' }}
          >
            <RefreshCw size={16} /> {retryMutation.isPending ? 'Retrying...' : 'Retry Job'}
          </button>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: '1.75rem' }}>
        {/* Payload and Details */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '1.5rem', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <h3 style={{ margin: '0 0 1rem 0', fontSize: '1rem', fontWeight: '700', color: '#0f172a' }}>Payload</h3>
            <pre style={{ backgroundColor: '#f8fafc', border: '1px solid #e2e8f0', padding: '1rem', borderRadius: '8px', overflowX: 'auto', fontSize: '0.825rem', fontFamily: 'var(--font-mono)', color: '#334155', margin: 0, lineHeight: 1.5 }}>
              {job.payload ? JSON.stringify(job.payload, null, 2) : 'No payload'}
            </pre>
          </div>

          <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '1.5rem', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <h3 style={{ margin: '0 0 1rem 0', fontSize: '1rem', fontWeight: '700', color: '#0f172a' }}>Executions</h3>
            <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0, textAlign: 'left' }}>
              <thead>
                <tr style={{ backgroundColor: '#f8fafc' }}>
                  <th style={{ padding: '0.65rem 0.75rem' }}>Attempt</th>
                  <th style={{ padding: '0.65rem 0.75rem' }}>Status</th>
                  <th style={{ padding: '0.65rem 0.75rem' }}>Duration</th>
                  <th style={{ padding: '0.65rem 0.75rem' }}>Worker ID</th>
                </tr>
              </thead>
              <tbody>
                {executions?.items?.length > 0 ? (
                  executions.items.map(exec => (
                    <React.Fragment key={exec.id}>
                      <tr style={{ borderBottom: exec.error ? 'none' : '1px solid #e2e8f0' }}>
                        <td style={{ padding: '0.75rem', fontSize: '0.85rem', fontWeight: '600', color: '#334155' }}>#{exec.attempt_number}</td>
                        <td style={{ padding: '0.75rem' }}><StatusBadge status={exec.status} /></td>
                        <td style={{ padding: '0.75rem', fontSize: '0.85rem', color: '#64748b' }}>
                          {exec.duration_seconds ? `${exec.duration_seconds.toFixed(2)}s` : '-'}
                        </td>
                        <td style={{ padding: '0.75rem', fontSize: '0.825rem', fontFamily: 'var(--font-mono)', color: '#4f46e5' }}>
                          {exec.worker_id ? exec.worker_id.substring(0, 8) : '-'}
                        </td>
                      </tr>
                      {exec.error && (
                        <tr style={{ borderBottom: '1px solid #e2e8f0' }}>
                          <td colSpan={4} style={{ padding: '0 0.75rem 0.75rem 0.75rem' }}>
                            <div style={{ backgroundColor: '#ffe4e6', color: '#9f1239', border: '1px solid #fecdd3', padding: '0.75rem', borderRadius: '8px', fontSize: '0.825rem', fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>
                              {exec.error}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} style={{ padding: '1.5rem', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>No execution history records found</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          
          {hasFailedExecution && (
            <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #fecdd3', padding: '1.5rem', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                <span style={{ padding: '0.2rem 0.5rem', backgroundColor: '#ffe4e6', color: '#9f1239', borderRadius: '6px', fontSize: '0.7rem', fontWeight: '700', letterSpacing: '0.05em' }}>AI ASSISTANT</span>
                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: '700', color: '#9f1239' }}>AI Failure Analysis</h3>
              </div>
              {failureSummaryLoading ? (
                <div style={{ fontSize: '0.85rem', color: '#64748b' }}>Analyzing failure logs with Gemini AI...</div>
              ) : failureSummary ? (
                <div>
                  {failureSummary.summary ? (
                    <div style={{ fontSize: '0.9rem', color: '#334155', lineHeight: '1.5', backgroundColor: '#fff1f2', borderLeft: '4px solid #e11d48', padding: '1rem', borderRadius: '0 8px 8px 0' }}>
                      {failureSummary.summary}
                      {failureSummary.cached && (
                        <span style={{ fontSize: '0.725rem', color: '#94a3b8', marginLeft: '0.5rem', fontStyle: 'italic' }}>(cached)</span>
                      )}
                    </div>
                  ) : (
                    <div style={{ fontSize: '0.85rem', color: '#64748b' }}>
                      {failureSummary.note || 'Summary unavailable.'}
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          )}
        </div>

        {/* Timeline Stepper */}
        <div>
          <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '1.5rem', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <h3 style={{ margin: '0 0 1.5rem 0', fontSize: '1rem', fontWeight: '700', color: '#0f172a' }}>Execution Timeline</h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {timeline?.events?.map((event, idx) => (
                <div key={idx} style={{ display: 'flex', gap: '1rem', position: 'relative' }}>
                  {/* Line connecting steps */}
                  {idx !== timeline.events.length - 1 && (
                    <div style={{ position: 'absolute', left: '10px', top: '20px', bottom: '-8px', width: '2px', backgroundColor: '#e2e8f0' }} />
                  )}
                  
                  {/* Dot */}
                  <div style={{ width: '22px', height: '22px', borderRadius: '50%', backgroundColor: '#e0e7ff', border: '2px solid #4f46e5', flexShrink: 0, zIndex: 1, marginTop: '2px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#4f46e5' }} />
                  </div>
                  
                  {/* Content */}
                  <div style={{ paddingBottom: '1.25rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.2rem' }}>
                      <span style={{ fontWeight: '600', fontSize: '0.875rem', color: '#0f172a', textTransform: 'capitalize' }}>{event.event_type}</span>
                      <span style={{ fontSize: '0.725rem', color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>{format(new Date(event.timestamp), 'MMM d, HH:mm:ss.SSS')}</span>
                    </div>
                    {event.message && (
                      <div style={{ fontSize: '0.85rem', color: '#475569', marginBottom: '0.25rem', lineHeight: '1.4' }}>{event.message}</div>
                    )}
                    {(event.attempt_number || event.worker_id) && (
                      <div style={{ fontSize: '0.75rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
                        {event.attempt_number && `Attempt: #${event.attempt_number}`}
                        {event.attempt_number && event.worker_id && ' | '}
                        {event.worker_id && `Worker: ${event.worker_id.substring(0, 8)}`}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
