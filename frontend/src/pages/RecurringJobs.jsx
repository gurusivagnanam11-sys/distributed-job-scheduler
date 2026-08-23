import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../components/AuthProvider';
import { getQueues, getRecurringJobs, updateRecurringJob, deleteRecurringJob } from '../api/client';
import { Play, Pause, Trash2, Clock } from 'lucide-react';
import { format } from 'date-fns';

export const RecurringJobs = () => {
  const queryClient = useQueryClient();
  const { currentProjectId: projectId } = useAuth();
  
  const [selectedQueue, setSelectedQueue] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

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

  const { data: templatesData, isLoading, isError } = useQuery({
    queryKey: ['recurringJobs', selectedQueue, page],
    queryFn: () => getRecurringJobs(selectedQueue, page, pageSize),
    enabled: !!selectedQueue,
    refetchInterval: 5000,
  });

  const pauseMutation = useMutation({
    mutationFn: (templateId) => updateRecurringJob(selectedQueue, templateId, { is_active: false }),
    onSuccess: () => queryClient.invalidateQueries(['recurringJobs']),
  });

  const resumeMutation = useMutation({
    mutationFn: (templateId) => updateRecurringJob(selectedQueue, templateId, { is_active: true }),
    onSuccess: () => queryClient.invalidateQueries(['recurringJobs']),
  });

  const deleteMutation = useMutation({
    mutationFn: (templateId) => deleteRecurringJob(selectedQueue, templateId),
    onSuccess: () => queryClient.invalidateQueries(['recurringJobs']),
  });

  if (!projectId) return <div style={{ color: '#64748b', fontSize: '0.875rem' }}>No project found.</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: '700', margin: '0 0 0.25rem 0', color: '#0f172a' }}>Recurring Job Templates</h1>
          <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>Automated cron-scheduled job templates running on recurring intervals</p>
        </div>
      </div>

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
      </div>

      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.04)', overflow: 'hidden' }}>
        {!selectedQueue ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b', fontSize: '0.875rem' }}>Please select or create a queue to view recurring templates.</div>
        ) : isLoading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b', fontSize: '0.875rem' }}>Loading templates...</div>
        ) : isError ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#e11d48', fontSize: '0.875rem' }}>Error loading templates</div>
        ) : !templatesData?.items || templatesData.items.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b', fontSize: '0.875rem' }}>No recurring job templates found in this queue.</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0, textAlign: 'left' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8fafc' }}>
                <th style={{ padding: '0.75rem 1.25rem' }}>ID</th>
                <th style={{ padding: '0.75rem 1.25rem' }}>Cron Expression</th>
                <th style={{ padding: '0.75rem 1.25rem' }}>Status</th>
                <th style={{ padding: '0.75rem 1.25rem' }}>Created</th>
                <th style={{ padding: '0.75rem 1.25rem', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {templatesData.items.map((template) => (
                <tr key={template.id} style={{ borderBottom: '1px solid #e2e8f0', transition: 'background-color 0.15s ease' }}>
                  <td style={{ padding: '0.85rem 1.25rem', fontSize: '0.85rem', fontFamily: 'var(--font-mono)', color: '#4f46e5', fontWeight: '500' }}>
                    {template.id.substring(0, 8)}...
                  </td>
                  <td style={{ padding: '0.85rem 1.25rem' }}>
                    <span style={{ fontFamily: 'var(--font-mono)', backgroundColor: '#f1f5f9', color: '#334155', padding: '0.25rem 0.5rem', borderRadius: '6px', fontSize: '0.825rem', border: '1px solid #e2e8f0' }}>
                      {template.cron_expression}
                    </span>
                  </td>
                  <td style={{ padding: '0.85rem 1.25rem' }}>
                    {!template.is_active ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', padding: '0.2rem 0.65rem', backgroundColor: '#fef3c7', color: '#92400e', border: '1px solid #fde68a', borderRadius: '9999px', fontSize: '0.725rem', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                        <Pause size={12} /> Paused
                      </span>
                    ) : (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', padding: '0.2rem 0.65rem', backgroundColor: '#dcfce7', color: '#15803d', border: '1px solid #bbf7d0', borderRadius: '9999px', fontSize: '0.725rem', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
                        <Play size={12} /> Active
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '0.85rem 1.25rem', fontSize: '0.85rem', color: '#64748b' }}>
                    {format(new Date(template.created_at), 'MMM d, HH:mm')}
                  </td>
                  <td style={{ padding: '0.85rem 1.25rem', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', alignItems: 'center' }}>
                      {!template.is_active ? (
                        <button 
                          onClick={() => resumeMutation.mutate(template.id)}
                          disabled={resumeMutation.isPending}
                          style={{ padding: '0.45rem 0.75rem', backgroundColor: '#dcfce7', color: '#15803d', border: '1px solid #bbf7d0', borderRadius: '8px', cursor: 'pointer', fontSize: '0.825rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                          title="Resume"
                        >
                          <Play size={14} /> Resume
                        </button>
                      ) : (
                        <button 
                          onClick={() => pauseMutation.mutate(template.id)}
                          disabled={pauseMutation.isPending}
                          style={{ padding: '0.45rem 0.75rem', backgroundColor: '#fef3c7', color: '#92400e', border: '1px solid #fde68a', borderRadius: '8px', cursor: 'pointer', fontSize: '0.825rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                          title="Pause"
                        >
                          <Pause size={14} /> Pause
                        </button>
                      )}
                      <button 
                        onClick={() => { if(window.confirm('Delete this template? Future jobs will not be scheduled.')) deleteMutation.mutate(template.id); }}
                        disabled={deleteMutation.isPending}
                        style={{ padding: '0.45rem 0.65rem', backgroundColor: '#ffe4e6', color: '#9f1239', border: '1px solid #fecdd3', borderRadius: '8px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                        title="Delete"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        
        {templatesData?.total > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem 1.25rem', borderTop: '1px solid #e2e8f0', backgroundColor: '#ffffff' }}>
            <div style={{ fontSize: '0.85rem', color: '#64748b' }}>
              Showing <strong style={{ color: '#0f172a' }}>{((page - 1) * pageSize) + 1}</strong> to <strong style={{ color: '#0f172a' }}>{Math.min(page * pageSize, templatesData.total)}</strong> of <strong style={{ color: '#0f172a' }}>{templatesData.total}</strong> results
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
                disabled={page * pageSize >= templatesData.total}
                onClick={() => setPage(p => p + 1)}
                style={{ padding: '0.45rem 0.85rem', border: '1px solid #cbd5e1', borderRadius: '6px', background: '#ffffff', color: '#334155', cursor: page * pageSize >= templatesData.total ? 'not-allowed' : 'pointer', opacity: page * pageSize >= templatesData.total ? 0.5 : 1, fontSize: '0.85rem', fontWeight: '500' }}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
