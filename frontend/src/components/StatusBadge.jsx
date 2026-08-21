import React from 'react';

const STATUS_COLORS = {
  // Job Statuses
  queued: { bg: '#f3f4f6', text: '#4b5563' }, // gray
  scheduled: { bg: '#e0f2fe', text: '#0369a1' }, // light blue
  claimed: { bg: '#fef08a', text: '#854d0e' }, // yellow
  running: { bg: '#dbeafe', text: '#1d4ed8' }, // blue
  completed: { bg: '#dcfce7', text: '#15803d' }, // green
  failed: { bg: '#fee2e2', text: '#b91c1c' }, // red
  retrying: { bg: '#ffedd5', text: '#c2410c' }, // orange
  dead_letter: { bg: '#7f1d1d', text: '#fef2f2' }, // dark red
  
  // Queue Statuses
  active: { bg: '#dcfce7', text: '#15803d' },
  paused: { bg: '#fef08a', text: '#854d0e' },
};

export const StatusBadge = ({ status }) => {
  if (!status) return null;
  
  const colors = STATUS_COLORS[status] || { bg: '#e5e7eb', text: '#374151' };
  
  return (
    <span style={{ 
      backgroundColor: colors.bg, 
      color: colors.text,
      padding: '0.25rem 0.75rem',
      borderRadius: '9999px',
      fontSize: '0.75rem',
      fontWeight: '600',
      display: 'inline-block',
      textTransform: 'uppercase'
    }}>
      {status.replace('_', ' ')}
    </span>
  );
};
