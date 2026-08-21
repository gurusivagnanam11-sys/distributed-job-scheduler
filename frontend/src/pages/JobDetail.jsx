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

  if (jobLoading) return <div>Loading...</div>;
  if (!job) return <div>Job not found</div>;

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#4b5563', textDecoration: 'none', fontSize: '0.875rem' }}>
          <ArrowLeft size={16} /> Back to Explorer
        </Link>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 'bold', margin: '0 0 0.5rem 0', fontFamily: 'monospace' }}>{job.id}</h1>
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <StatusBadge status={job.status} />
            <span style={{ fontSize: '0.875rem', color: '#6b7280' }}>Queue ID: <span style={{ fontFamily: 'monospace' }}>{job.queue_id}</span></span>
          </div>
        </div>

        {job.status === 'dead_letter' && (
          <button 
            onClick={() => retryMutation.mutate(id)}
            disabled={retryMutation.isPending}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '500' }}
          >
            <RefreshCw size={16} /> {retryMutation.isPending ? 'Retrying...' : 'Retry Job'}
          </button>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
        {/* Payload and Details */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ backgroundColor: 'white', borderRadius: '8px', border: '1px solid #e5e7eb', padding: '1.5rem' }}>
            <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.125rem' }}>Payload</h3>
            <pre style={{ backgroundColor: '#f9fafb', padding: '1rem', borderRadius: '4px', overflowX: 'auto', fontSize: '0.875rem', margin: 0 }}>
              {job.payload ? JSON.stringify(job.payload, null, 2) : 'No payload'}
            </pre>
          </div>

          <div style={{ backgroundColor: 'white', borderRadius: '8px', border: '1px solid #e5e7eb', padding: '1.5rem' }}>
            <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.125rem' }}>Executions</h3>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
                  <th style={{ padding: '0.5rem 0', fontSize: '0.75rem', color: '#4b5563' }}>Attempt</th>
                  <th style={{ padding: '0.5rem 0', fontSize: '0.75rem', color: '#4b5563' }}>Status</th>
                  <th style={{ padding: '0.5rem 0', fontSize: '0.75rem', color: '#4b5563' }}>Duration</th>
                  <th style={{ padding: '0.5rem 0', fontSize: '0.75rem', color: '#4b5563' }}>Worker ID</th>
                </tr>
              </thead>
              <tbody>
                {executions?.items?.length > 0 ? (
                  executions.items.map(exec => (
                    <React.Fragment key={exec.id}>
                      <tr style={{ borderBottom: exec.error ? 'none' : '1px solid #e5e7eb' }}>
                        <td style={{ padding: '0.75rem 0', fontSize: '0.875rem' }}>{exec.attempt_number}</td>
                        <td style={{ padding: '0.75rem 0' }}><StatusBadge status={exec.status} /></td>
                        <td style={{ padding: '0.75rem 0', fontSize: '0.875rem' }}>
                          {exec.duration_seconds ? `${exec.duration_seconds.toFixed(2)}s` : '-'}
                        </td>
                        <td style={{ padding: '0.75rem 0', fontSize: '0.875rem', fontFamily: 'monospace' }}>
                          {exec.worker_id ? exec.worker_id.substring(0, 8) : '-'}
                        </td>
                      </tr>
                      {exec.error && (
                        <tr style={{ borderBottom: '1px solid #e5e7eb' }}>
                          <td colSpan={4} style={{ padding: '0 0 0.75rem 0' }}>
                            <div style={{ backgroundColor: '#fef2f2', color: '#b91c1c', padding: '0.75rem', borderRadius: '4px', fontSize: '0.875rem' }}>
                              {exec.error}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))
                ) : (
                  <tr>
                    <td colSpan={4} style={{ padding: '1rem 0', textAlign: 'center', color: '#6b7280', fontSize: '0.875rem' }}>No executions found</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          
          {hasFailedExecution && (
            <div style={{ backgroundColor: 'white', borderRadius: '8px', border: '1px solid #e5e7eb', padding: '1.5rem' }}>
              <h3 style={{ margin: '0 0 1rem 0', fontSize: '1.125rem', color: '#b91c1c' }}>AI Failure Summary</h3>
              {failureSummaryLoading ? (
                <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>Generating summary...</div>
              ) : failureSummary ? (
                <div>
                  {failureSummary.summary ? (
                    <div style={{ fontSize: '0.95rem', color: '#1f2937', lineHeight: '1.5' }}>
                      {failureSummary.summary}
                      {failureSummary.cached && (
                        <span style={{ fontSize: '0.75rem', color: '#6b7280', marginLeft: '0.5rem', fontStyle: 'italic' }}>(cached)</span>
                      )}
                    </div>
                  ) : (
                    <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>
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
          <div style={{ backgroundColor: 'white', borderRadius: '8px', border: '1px solid #e5e7eb', padding: '1.5rem' }}>
            <h3 style={{ margin: '0 0 1.5rem 0', fontSize: '1.125rem' }}>Timeline</h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {timeline?.events?.map((event, idx) => (
                <div key={idx} style={{ display: 'flex', gap: '1rem', position: 'relative' }}>
                  {/* Line connecting steps */}
                  {idx !== timeline.events.length - 1 && (
                    <div style={{ position: 'absolute', left: '11px', top: '24px', bottom: '-16px', width: '2px', backgroundColor: '#e5e7eb' }} />
                  )}
                  
                  {/* Dot */}
                  <div style={{ width: '24px', height: '24px', borderRadius: '50%', backgroundColor: '#e0f2fe', border: '2px solid #3b82f6', flexShrink: 0, zIndex: 1 }} />
                  
                  {/* Content */}
                  <div style={{ paddingBottom: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
                      <span style={{ fontWeight: '600', textTransform: 'capitalize' }}>{event.event_type}</span>
                      <span style={{ fontSize: '0.75rem', color: '#6b7280' }}>{format(new Date(event.timestamp), 'MMM d, HH:mm:ss.SSS')}</span>
                    </div>
                    {event.message && (
                      <div style={{ fontSize: '0.875rem', color: '#4b5563', marginBottom: '0.25rem' }}>{event.message}</div>
                    )}
                    {(event.attempt_number || event.worker_id) && (
                      <div style={{ fontSize: '0.75rem', color: '#9ca3af', fontFamily: 'monospace' }}>
                        {event.attempt_number && `Attempt: ${event.attempt_number}`}
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
