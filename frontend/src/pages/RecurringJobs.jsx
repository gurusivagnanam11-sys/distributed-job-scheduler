import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getQueues, getCurrentProject, getRecurringJobs, updateRecurringJob, deleteRecurringJob } from '../api/client';
import { Play, Pause, Trash2, Clock } from 'lucide-react';
import { format } from 'date-fns';

export const RecurringJobs = () => {
  const queryClient = useQueryClient();
  const projectId = getCurrentProject();
  
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
    mutationFn: (templateId) => updateRecurringJob(selectedQueue, templateId, { is_paused: true }),
    onSuccess: () => queryClient.invalidateQueries(['recurringJobs']),
  });

  const resumeMutation = useMutation({
    mutationFn: (templateId) => updateRecurringJob(selectedQueue, templateId, { is_paused: false }),
    onSuccess: () => queryClient.invalidateQueries(['recurringJobs']),
  });

  const deleteMutation = useMutation({
    mutationFn: (templateId) => deleteRecurringJob(selectedQueue, templateId),
    onSuccess: () => queryClient.invalidateQueries(['recurringJobs']),
  });

  if (!projectId) return <div>No project found.</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 'bold', margin: 0 }}>Recurring Job Templates</h1>
      </div>

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
      </div>

      <div style={{ backgroundColor: 'white', borderRadius: '8px', border: '1px solid #e5e7eb', overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#6b7280' }}>Loading templates...</div>
        ) : isError ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#ef4444' }}>Error loading templates</div>
        ) : templatesData?.items?.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#6b7280' }}>No recurring job templates found in this queue.</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ backgroundColor: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase' }}>ID</th>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase' }}>Cron Expression</th>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase' }}>Status</th>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase' }}>Created</th>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {templatesData.items.map((template) => (
                <tr key={template.id} style={{ borderBottom: '1px solid #e5e7eb' }}>
                  <td style={{ padding: '0.75rem 1rem', fontSize: '0.875rem', fontFamily: 'monospace' }}>
                    {template.id.substring(0, 8)}...
                  </td>
                  <td style={{ padding: '0.75rem 1rem', fontSize: '0.875rem', fontFamily: 'monospace' }}>
                    {template.cron_expression}
                  </td>
                  <td style={{ padding: '0.75rem 1rem' }}>
                    {template.is_paused ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem 0.5rem', backgroundColor: '#fef3c7', color: '#92400e', borderRadius: '4px', fontSize: '0.75rem', fontWeight: '500' }}>
                        <Pause size={12} /> Paused
                      </span>
                    ) : (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem 0.5rem', backgroundColor: '#dcfce7', color: '#166534', borderRadius: '4px', fontSize: '0.75rem', fontWeight: '500' }}>
                        <Play size={12} /> Active
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '0.75rem 1rem', fontSize: '0.875rem', color: '#4b5563' }}>
                    {format(new Date(template.created_at), 'MMM d, HH:mm')}
                  </td>
                  <td style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                      {template.is_paused ? (
                        <button 
                          onClick={() => resumeMutation.mutate(template.id)}
                          disabled={resumeMutation.isPending}
                          style={{ padding: '0.5rem', backgroundColor: 'white', color: '#15803d', border: '1px solid #d1d5db', borderRadius: '4px', cursor: 'pointer' }}
                          title="Resume"
                        >
                          <Play size={16} />
                        </button>
                      ) : (
                        <button 
                          onClick={() => pauseMutation.mutate(template.id)}
                          disabled={pauseMutation.isPending}
                          style={{ padding: '0.5rem', backgroundColor: 'white', color: '#854d0e', border: '1px solid #d1d5db', borderRadius: '4px', cursor: 'pointer' }}
                          title="Pause"
                        >
                          <Pause size={16} />
                        </button>
                      )}
                      <button 
                        onClick={() => { if(window.confirm('Delete this template? Future jobs will not be scheduled.')) deleteMutation.mutate(template.id); }}
                        disabled={deleteMutation.isPending}
                        style={{ padding: '0.5rem', backgroundColor: 'white', color: '#ef4444', border: '1px solid #fca5a5', borderRadius: '4px', cursor: 'pointer' }}
                        title="Delete"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        
        {templatesData?.total > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', borderTop: '1px solid #e5e7eb' }}>
            <div style={{ fontSize: '0.875rem', color: '#4b5563' }}>
              Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, templatesData.total)} of {templatesData.total} results
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
                disabled={page * pageSize >= templatesData.total}
                onClick={() => setPage(p => p + 1)}
                style={{ padding: '0.5rem 1rem', border: '1px solid #d1d5db', borderRadius: '4px', background: 'white', cursor: page * pageSize >= templatesData.total ? 'not-allowed' : 'pointer' }}
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
