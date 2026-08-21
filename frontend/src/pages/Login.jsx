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
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', backgroundColor: '#f3f4f6' }}>
      <form onSubmit={handleSubmit} style={{ padding: '2rem', backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)', width: '300px' }}>
        <h2 style={{ marginBottom: '1rem', textAlign: 'center' }}>Job Scheduler</h2>
        
        {/* Demo Credentials Helper Banner */}
        <div style={{ backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', padding: '0.75rem', borderRadius: '6px', marginBottom: '1.25rem' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: '600', color: '#1e40af', marginBottom: '0.25rem' }}>DEMO PRESET AVAILABLE</div>
          <div style={{ fontSize: '0.75rem', color: '#1e3a8a', marginBottom: '0.5rem' }}>
            Pre-loaded with sample queues, jobs, & AI summaries.
          </div>
          <button 
            type="button"
            onClick={() => {
              setEmail('demo@example.com');
              setPassword('Password123!');
            }}
            style={{ width: '100%', padding: '0.375rem', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem', fontWeight: '600' }}
          >
            Auto-fill Demo Account
          </button>
        </div>

        {error && <div style={{ color: 'red', marginBottom: '1rem', fontSize: '0.875rem' }}>{error}</div>}
        
        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem' }}>Email</label>
          <input 
            type="email" 
            value={email} 
            onChange={e => setEmail(e.target.value)} 
            required 
            placeholder="you@example.com"
            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db', boxSizing: 'border-box' }} 
          />
        </div>
        
        <div style={{ marginBottom: '1.5rem' }}>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem' }}>Password</label>
          <input 
            type="password" 
            value={password} 
            onChange={e => setPassword(e.target.value)} 
            required 
            placeholder="Your password"
            style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db', boxSizing: 'border-box' }} 
          />
        </div>
        
        <button 
          type="submit" 
          disabled={loading}
          style={{ width: '100%', padding: '0.75rem', backgroundColor: '#3b82f6', color: 'white', border: 'none', borderRadius: '4px', cursor: loading ? 'not-allowed' : 'pointer' }}
        >
          {loading ? 'Logging in...' : 'Login'}
        </button>

        <div style={{ marginTop: '1rem', textAlign: 'center', fontSize: '0.875rem' }}>
          <span style={{ color: '#6b7280' }}>Don't have an account? </span>
          <Link to="/signup" style={{ color: '#3b82f6', textDecoration: 'none', fontWeight: 600 }}>
            Sign up
          </Link>
        </div>
      </form>
    </div>
  );
};
