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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: '700', margin: '0 0 0.25rem 0', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <Activity size={24} color="#4f46e5" /> Worker Nodes & Health
          </h1>
          <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>Live telemetry, heartbeat updates, and status of registered worker processes</p>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '1.25rem', marginBottom: '1.5rem', backgroundColor: '#ffffff', padding: '1.25rem', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.04)', alignItems: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <label style={{ fontSize: '0.7rem', fontWeight: '700', color: '#64748b', marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Status Filter</label>
          <select 
            value={selectedStatus} 
            onChange={(e) => { setSelectedStatus(e.target.value); setPage(1); }}
            style={{ padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', minWidth: '180px', fontSize: '0.875rem' }}
          >
            <option value="">All Statuses</option>
            {WORKER_STATUSES.map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div style={{ backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.04)', overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b', fontSize: '0.875rem' }}>Loading workers...</div>
        ) : isError ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#e11d48', fontSize: '0.875rem' }}>Error loading workers</div>
        ) : workersData?.items?.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b', fontSize: '0.875rem' }}>No active or historical worker nodes found matching criteria.</div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0, textAlign: 'left' }}>
            <thead>
              <tr style={{ backgroundColor: '#f8fafc' }}>
                <th style={{ padding: '0.75rem 1.25rem' }}>Worker ID</th>
                <th style={{ padding: '0.75rem 1.25rem' }}>Name</th>
                <th style={{ padding: '0.75rem 1.25rem' }}>Status</th>
                <th style={{ padding: '0.75rem 1.25rem' }}>Last Heartbeat</th>
                <th style={{ padding: '0.75rem 1.25rem' }}>Started At</th>
              </tr>
            </thead>
            <tbody>
              {workersData.items.map((worker) => (
                <tr 
                  key={worker.id} 
                  style={{ borderBottom: '1px solid #e2e8f0', transition: 'background-color 0.15s ease' }}
                  onMouseOver={e => e.currentTarget.style.backgroundColor = '#f8fafc'}
                  onMouseOut={e => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  <td style={{ padding: '0.85rem 1.25rem', fontSize: '0.85rem', fontFamily: 'var(--font-mono)', color: '#4f46e5', fontWeight: '500' }}>{worker.id.substring(0, 8)}...</td>
                  <td style={{ padding: '0.85rem 1.25rem', fontSize: '0.875rem', fontWeight: '600', color: '#0f172a' }}>{worker.name}</td>
                  <td style={{ padding: '0.85rem 1.25rem' }}><StatusBadge status={worker.status} /></td>
                  <td style={{ padding: '0.85rem 1.25rem', fontSize: '0.85rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
                    {worker.last_heartbeat_at ? format(new Date(worker.last_heartbeat_at), 'MMM d, HH:mm:ss') : 'Never'}
                  </td>
                  <td style={{ padding: '0.85rem 1.25rem', fontSize: '0.85rem', color: '#64748b' }}>
                    {worker.started_at ? format(new Date(worker.started_at), 'MMM d, HH:mm:ss') : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        
        {/* Pagination */}
        {workersData?.total > 0 && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem 1.25rem', borderTop: '1px solid #e2e8f0', backgroundColor: '#ffffff' }}>
            <div style={{ fontSize: '0.85rem', color: '#64748b' }}>
              Showing <strong style={{ color: '#0f172a' }}>{((page - 1) * pageSize) + 1}</strong> to <strong style={{ color: '#0f172a' }}>{Math.min(page * pageSize, workersData.total)}</strong> of <strong style={{ color: '#0f172a' }}>{workersData.total}</strong> results
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
                disabled={page * pageSize >= workersData.total}
                onClick={() => setPage(p => p + 1)}
                style={{ padding: '0.45rem 0.85rem', border: '1px solid #cbd5e1', borderRadius: '6px', background: '#ffffff', color: '#334155', cursor: page * pageSize >= workersData.total ? 'not-allowed' : 'pointer', opacity: page * pageSize >= workersData.total ? 0.5 : 1, fontSize: '0.85rem', fontWeight: '500' }}
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
