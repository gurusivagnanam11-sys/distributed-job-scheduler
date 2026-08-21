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
    mutationFn: (label) => createApiKey(projectId, label),
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
      <h3 style={{ marginTop: 0, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Key size={18} /> API Keys
      </h3>
      
      <p style={{ fontSize: '0.875rem', color: '#6b7280', marginBottom: '1.5rem' }}>
        API keys allow programmatic access to submit jobs to queues in this project. 
        Ensure you include the <code>X-API-Key</code> header in your requests.
      </p>

      {newlyCreatedKey && (
        <div style={{ backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', padding: '1rem', borderRadius: '6px', marginBottom: '1.5rem' }}>
          <h4 style={{ margin: '0 0 0.5rem 0', color: '#1e40af' }}>Key Created Successfully</h4>
          <p style={{ margin: '0 0 1rem 0', fontSize: '0.875rem', color: '#1e3a8a' }}>
            Please copy this key now. You will not be able to see it again.
          </p>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <input 
              readOnly 
              value={newlyCreatedKey} 
              style={{ flex: 1, padding: '0.5rem', borderRadius: '4px', border: '1px solid #93c5fd', backgroundColor: 'white', fontFamily: 'monospace' }}
            />
            <button 
              onClick={handleCopy}
              style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
            >
              {copied ? <Check size={16} /> : <Copy size={16} />} 
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
          <button 
            onClick={() => setNewlyCreatedKey(null)}
            style={{ marginTop: '1rem', background: 'none', border: 'none', color: '#3b82f6', cursor: 'pointer', fontSize: '0.875rem', padding: 0 }}
          >
            I have saved it securely
          </button>
        </div>
      )}

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        <input 
          type="text" 
          placeholder="New key label (e.g., Production Workers)" 
          value={newKeyLabel}
          onChange={(e) => setNewKeyLabel(e.target.value)}
          style={{ flex: 1, padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db' }}
        />
        <button 
          onClick={() => createMutation.mutate(newKeyLabel)}
          disabled={!newKeyLabel || createMutation.isPending}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', backgroundColor: '#2563eb', color: 'white', border: 'none', borderRadius: '4px', cursor: (!newKeyLabel || createMutation.isPending) ? 'not-allowed' : 'pointer' }}
        >
          <Plus size={16} /> Create Key
        </button>
      </div>

      <div style={{ border: '1px solid #e5e7eb', borderRadius: '6px', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
          <thead>
            <tr style={{ backgroundColor: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
              <th style={{ padding: '0.75rem', fontWeight: '500', color: '#4b5563' }}>Label</th>
              <th style={{ padding: '0.75rem', fontWeight: '500', color: '#4b5563' }}>Prefix</th>
              <th style={{ padding: '0.75rem', fontWeight: '500', color: '#4b5563' }}>Created</th>
              <th style={{ padding: '0.75rem', fontWeight: '500', color: '#4b5563', textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={4} style={{ padding: '1rem', textAlign: 'center', color: '#6b7280' }}>Loading keys...</td></tr>
            ) : keysData?.items?.length === 0 ? (
              <tr><td colSpan={4} style={{ padding: '1rem', textAlign: 'center', color: '#6b7280' }}>No API keys found.</td></tr>
            ) : (
              keysData?.items?.map(key => {
                const isRevoked = !!key.revoked_at;
                return (
                  <tr key={key.id} style={{ borderBottom: '1px solid #e5e7eb', backgroundColor: isRevoked ? '#f9fafb' : 'white', opacity: isRevoked ? 0.6 : 1 }}>
                    <td style={{ padding: '0.75rem' }}>{key.label || 'Unnamed Key'}</td>
                    <td style={{ padding: '0.75rem', fontFamily: 'monospace' }}>{key.key_prefix}...</td>
                    <td style={{ padding: '0.75rem', color: '#6b7280' }}>{format(new Date(key.created_at), 'MMM d, yyyy')}</td>
                    <td style={{ padding: '0.75rem', textAlign: 'right' }}>
                      {isRevoked ? (
                        <span style={{ fontSize: '0.75rem', color: '#ef4444', fontWeight: '500' }}>Revoked</span>
                      ) : (
                        <button 
                          onClick={() => { if(window.confirm('Revoke this key? It cannot be undone.')) revokeMutation.mutate(key.id); }}
                          disabled={revokeMutation.isPending}
                          style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '0.25rem' }}
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
