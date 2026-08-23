import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../components/AuthProvider';

export const Login = () => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', backgroundColor: '#f8fafc', padding: '1rem' }}>
      <form onSubmit={handleSubmit} style={{ padding: '2.5rem', backgroundColor: '#ffffff', borderRadius: '16px', boxShadow: '0 20px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04)', width: '380px', border: '1px solid #e2e8f0' }}>
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <div style={{ width: '44px', height: '44px', borderRadius: '12px', background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 0.75rem auto', boxShadow: '0 4px 12px rgba(79, 70, 229, 0.3)' }}>
            <span style={{ color: 'white', fontWeight: '700', fontSize: '1.2rem' }}>JS</span>
          </div>
          <h2 style={{ margin: '0 0 0.25rem 0', fontSize: '1.35rem', fontWeight: '700', color: '#0f172a' }}>Welcome back</h2>
          <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>Log in to access your job scheduler</p>
        </div>
        
        {/* Demo Credentials Helper Banner */}
        <div style={{ backgroundColor: '#e0e7ff', border: '1px solid #c7d2fe', padding: '0.85rem', borderRadius: '10px', marginBottom: '1.5rem' }}>
          <div style={{ fontSize: '0.7rem', fontWeight: '700', color: '#3730a3', marginBottom: '0.25rem', letterSpacing: '0.05em' }}>DEMO PRESET AVAILABLE</div>
          <div style={{ fontSize: '0.775rem', color: '#4338ca', marginBottom: '0.65rem', lineHeight: '1.35' }}>
            Pre-loaded with sample queues, jobs, & AI failure summaries.
          </div>
          <button 
            type="button"
            onClick={() => {
              setEmail('demo@example.com');
              setPassword('Password123!');
            }}
            style={{ width: '100%', padding: '0.45rem', backgroundColor: '#4f46e5', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '0.775rem', fontWeight: '600', boxShadow: '0 1px 3px rgba(79, 70, 229, 0.25)' }}
          >
            Auto-fill Demo Account
          </button>
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
            onChange={e => setEmail(e.target.value)} 
            required 
            placeholder="you@example.com"
            style={{ width: '100%', padding: '0.6rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', boxSizing: 'border-box', fontSize: '0.875rem' }} 
          />
        </div>
        
        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ display: 'block', marginBottom: '0.4rem', fontSize: '0.825rem', fontWeight: '600', color: '#334155' }}>Password</label>
          <input 
            type="password" 
            value={password} 
            onChange={e => setPassword(e.target.value)} 
            required 
            placeholder="Your password"
            style={{ width: '100%', padding: '0.6rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', boxSizing: 'border-box', fontSize: '0.875rem' }} 
          />
        </div>
        
        <button 
          type="submit" 
          disabled={loading}
          style={{ width: '100%', padding: '0.7rem', backgroundColor: '#4f46e5', color: 'white', border: 'none', borderRadius: '8px', cursor: loading ? 'not-allowed' : 'pointer', fontWeight: '600', fontSize: '0.875rem', opacity: loading ? 0.7 : 1, boxShadow: '0 2px 4px rgba(79, 70, 229, 0.25)' }}
        >
          {loading ? 'Logging in...' : 'Sign in'}
        </button>

        <div style={{ marginTop: '1.25rem', textAlign: 'center', fontSize: '0.85rem' }}>
          <span style={{ color: '#64748b' }}>Don't have an account? </span>
          <Link to="/signup" style={{ color: '#4f46e5', textDecoration: 'none', fontWeight: 600 }}>
            Sign up
          </Link>
        </div>
      </form>
    </div>
  );
};
