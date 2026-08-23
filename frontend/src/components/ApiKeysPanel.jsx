import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getApiKeys, createApiKey, revokeApiKey } from '../api/client';
import { Key, Trash2, Plus, Copy, Check } from 'lucide-react';
import { format } from 'date-fns';

export const ApiKeysPanel = ({ projectId }) => {
  const queryClient = useQueryClient();
  const [newKeyLabel, setNewKeyLabel] = useState('');
  const [newlyCreatedKey, setNewlyCreatedKey] = useState(null);
  const [copied, setCopied] = useState(false);

  const { data: keysData, isLoading } = useQuery({
    queryKey: ['apiKeys', projectId],
    queryFn: () => getApiKeys(projectId),
    enabled: !!projectId,
  });

  const createMutation = useMutation({
    mutationFn: (label) => createApiKey(projectId, { label }),
    onSuccess: (data) => {
      setNewlyCreatedKey(data.raw_key);
      setNewKeyLabel('');
      queryClient.invalidateQueries(['apiKeys', projectId]);
    },
    onError: (err) => alert(err.message)
  });

  const revokeMutation = useMutation({
    mutationFn: (keyId) => revokeApiKey(projectId, keyId),
    onSuccess: () => {
      queryClient.invalidateQueries(['apiKeys', projectId]);
    },
    onError: (err) => alert(err.message)
  });

  const handleCopy = () => {
    if (newlyCreatedKey) {
      navigator.clipboard.writeText(newlyCreatedKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div>
      <h3 style={{ marginTop: 0, marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.1rem', fontWeight: '700', color: '#0f172a' }}>
        <Key size={18} color="#4f46e5" /> Project API Keys
      </h3>
      
      <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '1.25rem', lineHeight: '1.4' }}>
        API keys allow programmatic access to submit jobs to queues in this project. 
        Ensure you include the <code style={{ backgroundColor: '#f1f5f9', padding: '0.15rem 0.4rem', borderRadius: '4px', border: '1px solid #e2e8f0', color: '#4f46e5', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>X-API-Key</code> header in HTTP requests.
      </p>

      {newlyCreatedKey && (
        <div style={{ backgroundColor: '#e0e7ff', border: '1px solid #c7d2fe', padding: '1rem', borderRadius: '10px', marginBottom: '1.25rem' }}>
          <h4 style={{ margin: '0 0 0.4rem 0', color: '#3730a3', fontSize: '0.95rem', fontWeight: '700' }}>Key Generated Successfully</h4>
          <p style={{ margin: '0 0 0.85rem 0', fontSize: '0.825rem', color: '#4338ca' }}>
            Please copy this key now. You will not be able to see it again.
          </p>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input 
              readOnly 
              value={newlyCreatedKey} 
              style={{ flex: 1, padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #a5b4fc', backgroundColor: '#ffffff', fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: '#1e1b4b' }}
            />
            <button 
              onClick={handleCopy}
              style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.55rem 1rem', backgroundColor: '#4f46e5', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '0.85rem', boxShadow: '0 2px 4px rgba(79, 70, 229, 0.25)' }}
            >
              {copied ? <Check size={16} /> : <Copy size={16} />} 
              {copied ? 'Copied' : 'Copy Key'}
            </button>
          </div>
          <button 
            onClick={() => setNewlyCreatedKey(null)}
            style={{ marginTop: '0.85rem', background: 'none', border: 'none', color: '#4338ca', cursor: 'pointer', fontSize: '0.8rem', padding: 0, fontWeight: '600', textDecoration: 'underline' }}
          >
            I have saved it securely
          </button>
        </div>
      )}

      <div style={{ display: 'flex', gap: '0.65rem', marginBottom: '1.25rem' }}>
        <input 
          type="text" 
          placeholder="Key label (e.g. Production Submitter)" 
          value={newKeyLabel}
          onChange={(e) => setNewKeyLabel(e.target.value)}
          style={{ flex: 1, padding: '0.55rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }}
        />
        <button 
          onClick={() => createMutation.mutate(newKeyLabel)}
          disabled={!newKeyLabel || createMutation.isPending}
          style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.55rem 1.15rem', backgroundColor: '#4f46e5', color: 'white', border: 'none', borderRadius: '8px', cursor: (!newKeyLabel || createMutation.isPending) ? 'not-allowed' : 'pointer', opacity: (!newKeyLabel || createMutation.isPending) ? 0.6 : 1, fontWeight: '600', fontSize: '0.875rem', boxShadow: '0 2px 4px rgba(79, 70, 229, 0.25)' }}
        >
          <Plus size={16} /> Create Key
        </button>
      </div>

      <div style={{ border: '1px solid #e2e8f0', borderRadius: '10px', overflow: 'hidden', backgroundColor: '#ffffff' }}>
        <table style={{ width: '100%', borderCollapse: 'separate', borderSpacing: 0, textAlign: 'left', fontSize: '0.875rem' }}>
          <thead>
            <tr style={{ backgroundColor: '#f8fafc' }}>
              <th style={{ padding: '0.65rem 1rem' }}>Label</th>
              <th style={{ padding: '0.65rem 1rem' }}>Prefix</th>
              <th style={{ padding: '0.65rem 1rem' }}>Created</th>
              <th style={{ padding: '0.65rem 1rem', textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={4} style={{ padding: '1.5rem', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>Loading keys...</td></tr>
            ) : keysData?.items?.length === 0 ? (
              <tr><td colSpan={4} style={{ padding: '1.5rem', textAlign: 'center', color: '#64748b', fontSize: '0.85rem' }}>No active or revoked API keys found.</td></tr>
            ) : (
              keysData?.items?.map(key => {
                const isRevoked = !!key.revoked_at;
                return (
                  <tr key={key.id} style={{ borderBottom: '1px solid #e2e8f0', backgroundColor: isRevoked ? '#f8fafc' : 'white', opacity: isRevoked ? 0.6 : 1 }}>
                    <td style={{ padding: '0.85rem 1rem', fontWeight: '600', color: '#0f172a' }}>{key.label || 'Unnamed Key'}</td>
                    <td style={{ padding: '0.85rem 1rem', fontFamily: 'var(--font-mono)', color: '#4f46e5', fontSize: '0.825rem' }}>{key.key_prefix}...</td>
                    <td style={{ padding: '0.85rem 1rem', color: '#64748b', fontSize: '0.825rem' }}>{format(new Date(key.created_at), 'MMM d, yyyy')}</td>
                    <td style={{ padding: '0.85rem 1rem', textAlign: 'right' }}>
                      {isRevoked ? (
                        <span style={{ fontSize: '0.725rem', color: '#9f1239', fontWeight: '600', padding: '0.2rem 0.5rem', backgroundColor: '#ffe4e6', borderRadius: '4px', border: '1px solid #fecdd3', textTransform: 'uppercase' }}>Revoked</span>
                      ) : (
                        <button 
                          onClick={() => { if(window.confirm('Revoke this key? It cannot be undone.')) revokeMutation.mutate(key.id); }}
                          disabled={revokeMutation.isPending}
                          style={{ background: 'none', border: 'none', color: '#9f1239', cursor: 'pointer', padding: '0.35rem', borderRadius: '4px' }}
                          title="Revoke Key"
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
