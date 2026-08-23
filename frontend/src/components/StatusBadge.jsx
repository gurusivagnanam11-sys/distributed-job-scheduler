import React from 'react';

const STATUS_COLORS = {
  // Job Statuses
  queued: { bg: '#f1f5f9', text: '#475569', border: '#cbd5e1', dot: '#94a3b8' },
  scheduled: { bg: '#e0f2fe', text: '#0369a1', border: '#bae6fd', dot: '#0284c7' },
  claimed: { bg: '#fef3c7', text: '#92400e', border: '#fde68a', dot: '#d97706' },
  running: { bg: '#e0e7ff', text: '#3730a3', border: '#c7d2fe', dot: '#4f46e5' },
  completed: { bg: '#dcfce7', text: '#15803d', border: '#bbf7d0', dot: '#16a34a' },
  failed: { bg: '#ffe4e6', text: '#9f1239', border: '#fecdd3', dot: '#e11d48' },
  retrying: { bg: '#ffedd5', text: '#c2410c', border: '#fed7aa', dot: '#ea580c' },
  dead_letter: { bg: '#881337', text: '#ffe4e6', border: '#9f1239', dot: '#f43f5e' },
  
  // Queue & Worker Statuses
  active: { bg: '#dcfce7', text: '#15803d', border: '#bbf7d0', dot: '#16a34a' },
  paused: { bg: '#fef3c7', text: '#92400e', border: '#fde68a', dot: '#d97706' },
  online: { bg: '#dcfce7', text: '#15803d', border: '#bbf7d0', dot: '#16a34a' },
  offline: { bg: '#ffe4e6', text: '#9f1239', border: '#fecdd3', dot: '#e11d48' },
};

export const StatusBadge = ({ status }) => {
  if (!status) return null;
  
  const colors = STATUS_COLORS[status.toLowerCase()] || { bg: '#f1f5f9', text: '#475569', border: '#e2e8f0', dot: '#64748b' };
  
  return (
    <span style={{ 
      backgroundColor: colors.bg, 
      color: colors.text,
      border: `1px solid ${colors.border}`,
      padding: '0.2rem 0.65rem',
      borderRadius: '9999px',
      fontSize: '0.725rem',
      fontWeight: '600',
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.375rem',
      letterSpacing: '0.03em',
      textTransform: 'uppercase',
      boxShadow: '0 1px 2px rgba(0,0,0,0.03)'
    }}>
      <span style={{
        width: '6px',
        height: '6px',
        borderRadius: '50%',
        backgroundColor: colors.dot,
        display: 'inline-block'
      }} />
      {status.replace('_', ' ')}
    </span>
  );
};
