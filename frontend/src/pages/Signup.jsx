import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../components/AuthProvider';

export const Signup = () => {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [organizationName, setOrganizationName] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await signup(email, password, organizationName);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.message || 'Signup failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', backgroundColor: '#f8fafc', padding: '1rem' }}>
      <form onSubmit={handleSubmit} style={{ padding: '2.5rem', backgroundColor: '#ffffff', borderRadius: '16px', boxShadow: '0 20px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04)', width: '380px', border: '1px solid #e2e8f0' }}>
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <div style={{ width: '44px', height: '44px', borderRadius: '12px', background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 0.75rem auto', boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)' }}>
            <span style={{ color: 'white', fontWeight: '700', fontSize: '1.2rem' }}>JS</span>
          </div>
          <h2 style={{ margin: '0 0 0.25rem 0', fontSize: '1.35rem', fontWeight: '700', color: '#0f172a' }}>Create an account</h2>
          <p style={{ margin: 0, fontSize: '0.85rem', color: '#64748b' }}>
            Set up your organization and workspace account.
          </p>
        </div>

        {error && (
          <div style={{ color: '#9f1239', backgroundColor: '#ffe4e6', border: '1px solid #fecdd3', padding: '0.75rem', borderRadius: '8px', marginBottom: '1.25rem', fontSize: '0.85rem', fontWeight: '500' }}>
            {error}
          </div>
        )}

        <div style={{ marginBottom: '1.15rem' }}>
          <label style={{ display: 'block', marginBottom: '0.4rem', fontSize: '0.825rem', fontWeight: '600', color: '#334155' }}>Email address</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="you@example.com"
            style={{ width: '100%', padding: '0.6rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', boxSizing: 'border-box', fontSize: '0.875rem' }}
          />
        </div>

        <div style={{ marginBottom: '1.15rem' }}>
          <label style={{ display: 'block', marginBottom: '0.4rem', fontSize: '0.825rem', fontWeight: '600', color: '#334155' }}>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            placeholder="At least 8 characters"
            style={{ width: '100%', padding: '0.6rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', boxSizing: 'border-box', fontSize: '0.875rem' }}
          />
        </div>

        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ display: 'block', marginBottom: '0.4rem', fontSize: '0.825rem', fontWeight: '600', color: '#334155' }}>Organization name</label>
          <input
            type="text"
            value={organizationName}
            onChange={(e) => setOrganizationName(e.target.value)}
            required
            placeholder="Acme Inc."
            style={{ width: '100%', padding: '0.6rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', boxSizing: 'border-box', fontSize: '0.875rem' }}
          />
          <div style={{ marginTop: '0.4rem', color: '#64748b', fontSize: '0.75rem' }}>
            This creates the primary workspace for your account.
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          style={{ width: '100%', padding: '0.7rem', backgroundColor: '#10b981', color: 'white', border: 'none', borderRadius: '8px', cursor: loading ? 'not-allowed' : 'pointer', fontWeight: '600', fontSize: '0.875rem', opacity: loading ? 0.7 : 1, boxShadow: '0 2px 4px rgba(16, 185, 129, 0.25)' }}
        >
          {loading ? 'Creating account...' : 'Complete Sign Up'}
        </button>

        <div style={{ marginTop: '1.25rem', textAlign: 'center', fontSize: '0.85rem' }}>
          <span style={{ color: '#64748b' }}>Already have an account? </span>
          <Link to="/login" style={{ color: '#4f46e5', textDecoration: 'none', fontWeight: 600 }}>
            Log in
          </Link>
        </div>
      </form>
    </div>
  );
};
