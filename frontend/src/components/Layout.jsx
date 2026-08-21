import React, { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from './AuthProvider';
import { LayoutDashboard, ListTree, Activity, LogOut, Plus, Folder, Settings, Clock } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getProjects, createProject, getCurrentProject, setCurrentProject } from '../api/client';
import { ApiKeysPanel } from './ApiKeysPanel';

export const Layout = () => {
  const { logout } = useAuth();
  const queryClient = useQueryClient();
  const [isCreateProjectModalOpen, setIsCreateProjectModalOpen] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [newProjectDescription, setNewProjectDescription] = useState('');
  const [currentProjectId, setCurrentProjectIdState] = useState(getCurrentProject());
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);

  React.useEffect(() => {
    const handleProjectChanged = () => {
      setCurrentProjectIdState(getCurrentProject());
    };
    window.addEventListener('project:changed', handleProjectChanged);
    return () => window.removeEventListener('project:changed', handleProjectChanged);
  }, []);

  const { data: projectsData, isLoading: isProjectsLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: getProjects,
  });

  const createProjectMutation = useMutation({
    mutationFn: (data) => createProject(data.name, data.description),
    onSuccess: (newProject) => {
      queryClient.invalidateQueries(['projects']);
      setCurrentProject(newProject.id);
      setCurrentProjectIdState(newProject.id);
      setIsCreateProjectModalOpen(false);
      setNewProjectName('');
      setNewProjectDescription('');
      window.dispatchEvent(new Event('project:changed'));
    },
  });

  const handleProjectChange = (e) => {
    const value = e.target.value;
    if (value === 'new') {
      setIsCreateProjectModalOpen(true);
    } else {
      setCurrentProject(value);
      window.dispatchEvent(new Event('project:changed'));
      queryClient.invalidateQueries(); // Invalidate all to refresh queue/job data
    }
  };

  const navLinkStyle = ({ isActive }) => ({
    display: 'flex',
    alignItems: 'center',
    padding: '0.75rem 1rem',
    textDecoration: 'none',
    color: isActive ? '#2563eb' : '#4b5563',
    backgroundColor: isActive ? '#eff6ff' : 'transparent',
    borderRadius: '6px',
    marginBottom: '0.5rem',
    fontWeight: isActive ? '500' : 'normal',
  });

  return (
    <div style={{ display: 'flex', height: '100vh', backgroundColor: '#f9fafb' }}>
      {/* Sidebar */}
      <div style={{ width: '250px', backgroundColor: 'white', borderRight: '1px solid #e5e7eb', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '1.5rem', borderBottom: '1px solid #e5e7eb' }}>
          <h1 style={{ margin: 0, fontSize: '1.25rem', color: '#111827', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Folder size={20} />
            Job Scheduler
          </h1>
        </div>
        
        <div style={{ padding: '1rem', borderBottom: '1px solid #e5e7eb' }}>
          <label style={{ fontSize: '0.75rem', fontWeight: '600', color: '#4b5563', marginBottom: '0.5rem', display: 'block' }}>PROJECT</label>
          {isProjectsLoading ? (
            <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>Loading projects...</div>
          ) : projectsData?.items?.length === 0 ? (
            <button
              onClick={() => setIsCreateProjectModalOpen(true)}
              style={{ width: '100%', padding: '0.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', backgroundColor: '#2563eb', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
            >
              <Plus size={16} /> Create Project
            </button>
          ) : (
            <>
              <select 
                value={currentProjectId || ''} 
                onChange={handleProjectChange}
                style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db', fontSize: '0.875rem' }}
              >
                {projectsData?.items?.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
                <option value="new">-- Create New Project --</option>
              </select>
            
            {currentProjectId && (
              <div style={{ marginTop: '0.5rem' }}>
                <button 
                  onClick={() => setIsSettingsModalOpen(true)}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', width: '100%', padding: '0.5rem', backgroundColor: 'transparent', border: '1px solid #e5e7eb', borderRadius: '4px', color: '#4b5563', cursor: 'pointer', fontSize: '0.875rem' }}
                >
                  <Settings size={14} /> Project Settings
                </button>
              </div>
            )}
          </>
        )}
      </div>

        <nav style={{ padding: '1rem', flex: 1 }}>
          <NavLink to="/" style={navLinkStyle}>
            <ListTree size={20} style={{ marginRight: '0.75rem' }} />
            Job Explorer
          </NavLink>
          <NavLink to="/queues" style={navLinkStyle}>
            <LayoutDashboard size={20} style={{ marginRight: '0.75rem' }} />
            Queue Overview
          </NavLink>
          <NavLink to="/recurring-jobs" style={navLinkStyle}>
            <Clock size={20} style={{ marginRight: '0.75rem' }} />
            Recurring Jobs
          </NavLink>
          <NavLink to="/workers" style={navLinkStyle}>
            <Activity size={20} style={{ marginRight: '0.75rem' }} />
            Worker Status
          </NavLink>
        </nav>

        <div style={{ padding: '1rem', borderTop: '1px solid #e5e7eb' }}>
          <button 
            onClick={logout}
            style={{ display: 'flex', alignItems: 'center', width: '100%', padding: '0.75rem 1rem', background: 'none', border: 'none', color: '#4b5563', cursor: 'pointer', textAlign: 'left', borderRadius: '6px' }}
            onMouseOver={e => e.currentTarget.style.backgroundColor = '#f3f4f6'}
            onMouseOut={e => e.currentTarget.style.backgroundColor = 'transparent'}
          >
            <LogOut size={20} style={{ marginRight: '0.75rem' }} />
            Logout
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
          {!currentProjectId && !isProjectsLoading ? (
            <div style={{ padding: '3rem', textAlign: 'center', backgroundColor: 'white', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
              <h2 style={{ marginTop: 0 }}>No Project Selected</h2>
              <p style={{ color: '#6b7280' }}>Please select or create a project to continue.</p>
              <button
                onClick={() => setIsCreateProjectModalOpen(true)}
                style={{ padding: '0.5rem 1rem', backgroundColor: '#2563eb', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.5rem', marginTop: '1rem' }}
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
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ backgroundColor: 'white', padding: '2rem', borderRadius: '8px', width: '400px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
            <h2 style={{ marginTop: 0, marginBottom: '1.5rem' }}>Create Project</h2>
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>Project Name</label>
              <input 
                type="text" 
                value={newProjectName} 
                onChange={(e) => setNewProjectName(e.target.value)} 
                style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db' }}
                placeholder="e.g. Production Data Pipelines"
              />
            </div>
            <div style={{ marginBottom: '1.5rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', marginBottom: '0.5rem' }}>Description</label>
              <textarea 
                value={newProjectDescription} 
                onChange={(e) => setNewProjectDescription(e.target.value)} 
                style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #d1d5db', minHeight: '80px' }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
              <button 
                onClick={() => setIsCreateProjectModalOpen(false)}
                style={{ padding: '0.5rem 1rem', backgroundColor: 'white', border: '1px solid #d1d5db', borderRadius: '4px', cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button 
                onClick={() => createProjectMutation.mutate({ name: newProjectName, description: newProjectDescription })}
                disabled={!newProjectName || createProjectMutation.isPending}
                style={{ padding: '0.5rem 1rem', backgroundColor: '#2563eb', color: 'white', border: 'none', borderRadius: '4px', cursor: (!newProjectName || createProjectMutation.isPending) ? 'not-allowed' : 'pointer' }}
              >
                {createProjectMutation.isPending ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Project Settings Modal */}
      {isSettingsModalOpen && currentProjectId && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ backgroundColor: 'white', padding: '2rem', borderRadius: '8px', width: '600px', boxShadow: '0 4px 6px rgba(0,0,0,0.1)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h2 style={{ margin: 0 }}>Project Settings</h2>
              <button 
                onClick={() => setIsSettingsModalOpen(false)}
                style={{ background: 'none', border: 'none', fontSize: '1.25rem', cursor: 'pointer', color: '#6b7280' }}
              >
                &times;
              </button>
            </div>
            
            {/* We could have tabs here in the future, but for now just API Keys */}
            <ApiKeysPanel projectId={currentProjectId} />
            
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '2rem', borderTop: '1px solid #e5e7eb', paddingTop: '1rem' }}>
              <button 
                onClick={() => setIsSettingsModalOpen(false)}
                style={{ padding: '0.5rem 1rem', backgroundColor: '#f3f4f6', color: '#4b5563', border: '1px solid #d1d5db', borderRadius: '4px', cursor: 'pointer' }}
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
