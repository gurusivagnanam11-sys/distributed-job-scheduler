import React, { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from './AuthProvider';
import { LayoutDashboard, ListTree, Activity, LogOut, Plus, Folder, Settings, Clock } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getProjects, createProject } from '../api/client';
import { ApiKeysPanel } from './ApiKeysPanel';

export const Layout = () => {
  const { logout, currentProjectId, selectProject } = useAuth();
  const queryClient = useQueryClient();
  const [isCreateProjectModalOpen, setIsCreateProjectModalOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDescription, setNewProjectDescription] = useState('');
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);

  const { data: projectsData, isLoading: isProjectsLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: getProjects,
  });

  const createProjectMutation = useMutation({
    mutationFn: (data) => createProject(data.name, data.description),
    onSuccess: (newProject) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      selectProject(newProject.id);
      setIsCreateProjectModalOpen(false);
      setNewProjectName('');
      setNewProjectDescription('');
    },
  });

  React.useEffect(() => {
    if (projectsData?.items?.length > 0 && !currentProjectId) {
      selectProject(projectsData.items[0].id);
    }
  }, [projectsData, currentProjectId, selectProject]);

  const handleProjectChange = (e) => {
    const value = e.target.value;
    if (value === 'new') {
      setIsCreateProjectModalOpen(true);
    } else {
      selectProject(value);
      queryClient.invalidateQueries(); // Invalidate all to refresh queue/job data
    }
  };

  const navLinkStyle = ({ isActive }) => ({
    display: 'flex',
    alignItems: 'center',
    padding: '0.65rem 0.85rem',
    textDecoration: 'none',
    color: isActive ? '#6366f1' : '#94a3b8',
    backgroundColor: isActive ? 'rgba(99, 102, 241, 0.12)' : 'transparent',
    borderLeft: isActive ? '3px solid #6366f1' : '3px solid transparent',
    borderRadius: '0 8px 8px 0',
    marginBottom: '0.35rem',
    fontWeight: isActive ? '600' : '500',
    fontSize: '0.875rem',
    transition: 'all 0.15s ease',
  });

  return (
    <div style={{ display: 'flex', height: '100vh', backgroundColor: '#f8fafc' }}>
      {/* Sidebar */}
      <div style={{ width: '260px', backgroundColor: '#0f172a', borderRight: '1px solid #1e293b', display: 'flex', flexDirection: 'column', color: '#f8fafc' }}>
        <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid #1e293b', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 8px rgba(79, 70, 229, 0.4)' }}>
            <Folder size={18} color="white" />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '1rem', fontWeight: '700', color: '#ffffff', letterSpacing: '-0.01em' }}>
              Job Scheduler
            </h1>
            <span style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: '500', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Distributed Platform</span>
          </div>
        </div>
        
        <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid #1e293b' }}>
          <label style={{ fontSize: '0.7rem', fontWeight: '700', color: '#64748b', marginBottom: '0.5rem', display: 'block', letterSpacing: '0.08em' }}>ACTIVE PROJECT</label>
          {isProjectsLoading ? (
            <div style={{ fontSize: '0.85rem', color: '#94a3b8', padding: '0.5rem 0' }}>Loading projects...</div>
          ) : projectsData?.items?.length === 0 ? (
            <button
              onClick={() => setIsCreateProjectModalOpen(true)}
              style={{ width: '100%', padding: '0.55rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', backgroundColor: '#4f46e5', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '500', fontSize: '0.85rem' }}
            >
              <Plus size={16} /> Create Project
            </button>
          ) : (
            <>
              <select 
                value={currentProjectId || ''} 
                onChange={handleProjectChange}
                style={{ width: '100%', padding: '0.5rem 0.75rem', borderRadius: '6px', border: '1px solid #334155', backgroundColor: '#1e293b', color: '#f8fafc', fontSize: '0.85rem' }}
              >
                {projectsData?.items?.map(p => (
                  <option key={p.id} value={p.id} style={{ backgroundColor: '#1e293b', color: '#f8fafc' }}>{p.name}</option>
                ))}
                <option value="new" style={{ backgroundColor: '#1e293b', color: '#818cf8' }}>+ Create New Project</option>
              </select>
            
            {currentProjectId && (
              <div style={{ marginTop: '0.5rem' }}>
                <button 
                  onClick={() => setIsSettingsModalOpen(true)}
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', width: '100%', padding: '0.45rem', backgroundColor: 'transparent', border: '1px solid #334155', borderRadius: '6px', color: '#94a3b8', cursor: 'pointer', fontSize: '0.8rem', fontWeight: '500', transition: 'all 0.15s ease' }}
                  onMouseOver={e => { e.currentTarget.style.borderColor = '#475569'; e.currentTarget.style.color = '#f8fafc'; }}
                  onMouseOut={e => { e.currentTarget.style.borderColor = '#334155'; e.currentTarget.style.color = '#94a3b8'; }}
                >
                  <Settings size={14} /> Project Settings
                </button>
              </div>
            )}
          </>
        )}
      </div>

        <nav style={{ padding: '1rem 0.75rem', flex: 1 }}>
          <NavLink to="/" style={navLinkStyle}>
            <ListTree size={18} style={{ marginRight: '0.75rem' }} />
            Job Explorer
          </NavLink>
          <NavLink to="/queues" style={navLinkStyle}>
            <LayoutDashboard size={18} style={{ marginRight: '0.75rem' }} />
            Queue Overview
          </NavLink>
          <NavLink to="/recurring-jobs" style={navLinkStyle}>
            <Clock size={18} style={{ marginRight: '0.75rem' }} />
            Recurring Jobs
          </NavLink>
          <NavLink to="/workers" style={navLinkStyle}>
            <Activity size={18} style={{ marginRight: '0.75rem' }} />
            Worker Status
          </NavLink>
        </nav>

        <div style={{ padding: '1rem 1.25rem', borderTop: '1px solid #1e293b' }}>
          <button 
            onClick={logout}
            style={{ display: 'flex', alignItems: 'center', width: '100%', padding: '0.65rem 0.85rem', background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', textAlign: 'left', borderRadius: '6px', fontSize: '0.875rem', fontWeight: '500', transition: 'all 0.15s ease' }}
            onMouseOver={e => { e.currentTarget.style.backgroundColor = '#1e293b'; e.currentTarget.style.color = '#f8fafc'; }}
            onMouseOut={e => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = '#94a3b8'; }}
          >
            <LogOut size={18} style={{ marginRight: '0.75rem' }} />
            Logout
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, overflow: 'auto', backgroundColor: '#f8fafc' }}>
        <div style={{ padding: '2rem 2.5rem', maxWidth: '1280px', margin: '0 auto' }}>
          {!currentProjectId && !isProjectsLoading ? (
            <div style={{ padding: '4rem 2rem', textAlign: 'center', backgroundColor: '#ffffff', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', maxWidth: '480px', margin: '4rem auto' }}>
              <div style={{ width: '48px', height: '48px', borderRadius: '12px', backgroundColor: '#e0e7ff', color: '#4f46e5', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.25rem auto' }}>
                <Folder size={24} />
              </div>
              <h2 style={{ marginTop: 0, marginBottom: '0.5rem', fontSize: '1.25rem', fontWeight: '700' }}>No Project Selected</h2>
              <p style={{ color: '#64748b', fontSize: '0.875rem', margin: '0 0 1.5rem 0' }}>Please select or create a project to continue scheduling jobs.</p>
              <button
                onClick={() => setIsCreateProjectModalOpen(true)}
                style={{ padding: '0.625rem 1.25rem', backgroundColor: '#4f46e5', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontWeight: '600', fontSize: '0.875rem', boxShadow: '0 2px 4px rgba(79, 70, 229, 0.25)' }}
              >
                <Plus size={16} /> Create Project
              </button>
            </div>
          ) : (
            <Outlet />
          )}
        </div>
      </div>

      {/* Create Project Modal */}
      {isCreateProjectModalOpen && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(15, 23, 42, 0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ backgroundColor: 'white', padding: '2rem', borderRadius: '12px', width: '420px', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.05)', border: '1px solid #e2e8f0' }}>
            <h2 style={{ marginTop: 0, marginBottom: '1.25rem', fontSize: '1.25rem', fontWeight: '700' }}>Create Project</h2>
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: '600', color: '#334155', marginBottom: '0.4rem' }}>Project Name</label>
              <input 
                type="text" 
                value={newProjectName} 
                onChange={(e) => setNewProjectName(e.target.value)} 
                style={{ width: '100%', padding: '0.6rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '0.875rem' }}
                placeholder="e.g. Production Data Pipelines"
              />
            </div>
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: '600', color: '#334155', marginBottom: '0.4rem' }}>Description</label>
              <textarea 
                value={newProjectDescription} 
                onChange={(e) => setNewProjectDescription(e.target.value)} 
                style={{ width: '100%', padding: '0.6rem 0.85rem', borderRadius: '8px', border: '1px solid #cbd5e1', minHeight: '80px', fontSize: '0.875rem', resize: 'vertical' }}
                placeholder="Optional description"
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
              <button 
                onClick={() => setIsCreateProjectModalOpen(false)}
                style={{ padding: '0.6rem 1.25rem', backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '8px', cursor: 'pointer', fontWeight: '500', fontSize: '0.875rem' }}
              >
                Cancel
              </button>
              <button 
                onClick={() => createProjectMutation.mutate({ name: newProjectName, description: newProjectDescription })}
                disabled={!newProjectName || createProjectMutation.isPending}
                style={{ padding: '0.6rem 1.25rem', backgroundColor: '#4f46e5', color: 'white', border: 'none', borderRadius: '8px', cursor: (!newProjectName || createProjectMutation.isPending) ? 'not-allowed' : 'pointer', opacity: (!newProjectName || createProjectMutation.isPending) ? 0.6 : 1, fontWeight: '600', fontSize: '0.875rem' }}
              >
                {createProjectMutation.isPending ? 'Creating...' : 'Create Project'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Project Settings Modal */}
      {isSettingsModalOpen && currentProjectId && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(15, 23, 42, 0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ backgroundColor: 'white', padding: '2rem', borderRadius: '12px', width: '640px', maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.05)', border: '1px solid #e2e8f0' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '1rem' }}>
              <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: '700' }}>Project Settings</h2>
              <button 
                onClick={() => setIsSettingsModalOpen(false)}
                style={{ background: 'none', border: 'none', fontSize: '1.5rem', cursor: 'pointer', color: '#94a3b8', padding: 0, lineHeight: 1 }}
              >
                &times;
              </button>
            </div>
            
            <ApiKeysPanel projectId={currentProjectId} />
            
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '2rem', borderTop: '1px solid #e2e8f0', paddingTop: '1rem' }}>
              <button 
                onClick={() => setIsSettingsModalOpen(false)}
                style={{ padding: '0.55rem 1.25rem', backgroundColor: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', borderRadius: '8px', cursor: 'pointer', fontWeight: '500', fontSize: '0.875rem' }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
