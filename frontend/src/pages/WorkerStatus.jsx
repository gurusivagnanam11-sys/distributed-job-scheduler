import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getWorkers } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { format } from 'date-fns';
import { Activity } from 'lucide-react';

const WORKER_STATUSES = ['online', 'offline', 'draining'];

export const WorkerStatus = () => {
  const [selectedStatus, setSelectedStatus] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data: workersData, isLoading, isError } = useQuery({
    queryKey: ['workers', page, selectedStatus],
    queryFn: () => getWorkers(page, pageSize, selectedStatus || null),
    refetchInterval: 5000,
  });

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 'bold', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Activity size={24} /> Worker Status
        </h1>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', backgroundColor: 'white', padding: '1rem', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <label style={{ fontSize: '0.75rem', fontWeight: '600', color: '#4b5563', marginBottom: '0.25rem' }}>Status</label>
          <select 
            value={selectedStatus} 
            onChange={(e) => { setSelectedStatus(e.target.value); setPage(1); }}
            style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db', minWidth: '150px' }}
          >
            <option value="">All Statuses</option>
            {WORKER_STATUSES.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div style={{ backgroundColor: 'white', borderRadius: '8px', border: '1px solid #e5e7eb', overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#6b7280' }}>Loading workers...</div>
        ) : isError ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#ef4444' }}>Error loading workers</div>
        ) : workersData?.items?.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#6b7280' }}>No workers found matching criteria.</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ backgroundColor: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase' }}>Worker ID</th>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase' }}>Name</th>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase' }}>Status</th>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase' }}>Last Heartbeat</th>
                <th style={{ padding: '0.75rem 1rem', fontSize: '0.75rem', color: '#4b5563', textTransform: 'uppercase' }}>Started At</th>
              </tr>
            </thead>
            <tbody>
              {workersData.items.map((worker) => (
                <tr 
                  key={worker.id} 
                  style={{ borderBottom: '1px solid #e5e7eb' }}
                  onMouseOver={e => e.currentTarget.style.backgroundColor = '#f9fafb'}
                  onMouseOut={e => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  <td style={{ padding: '0.75rem 1rem', fontSize: '0.875rem', fontFamily: 'monospace' }}>{worker.id.substring(0, 8)}...</td>
                  <td style={{ padding: '0.75rem 1rem', fontSize: '0.875rem', fontWeight: '500' }}>{worker.name}</td>
                  <td style={{ padding: '0.75rem 1rem' }}><StatusBadge status={worker.status} /></td>
                  <td style={{ padding: '0.75rem 1rem', fontSize: '0.875rem', color: '#4b5563' }}>
                    {worker.last_heartbeat_at ? format(new Date(worker.last_heartbeat_at), 'MMM d, HH:mm:ss') : 'Never'}
                  </td>
                  <td style={{ padding: '0.75rem 1rem', fontSize: '0.875rem', color: '#4b5563' }}>
                    {worker.started_at ? format(new Date(worker.started_at), 'MMM d, HH:mm:ss') : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        
        {/* Pagination */}
        {workersData?.total > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem', borderTop: '1px solid #e5e7eb' }}>
            <div style={{ fontSize: '0.875rem', color: '#4b5563' }}>
              Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, workersData.total)} of {workersData.total} results
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
                disabled={page * pageSize >= workersData.total}
                onClick={() => setPage(p => p + 1)}
                style={{ padding: '0.5rem 1rem', border: '1px solid #d1d5db', borderRadius: '4px', background: 'white', cursor: page * pageSize >= workersData.total ? 'not-allowed' : 'pointer' }}
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
