import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { setAuthToken, getAuthToken, login as apiLogin, signup as apiSignup, getProjects, setCurrentProject as cacheCurrentProject, getCurrentProject } from '../api/client';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [currentProjectId, setCurrentProjectId] = useState(getCurrentProject());
  const [loading, setLoading] = useState(true);

  const selectProject = useCallback((projectId) => {
    cacheCurrentProject(projectId);
    setCurrentProjectId(projectId);
    window.dispatchEvent(new Event('project:changed'));
  }, []);

  const logout = useCallback(() => {
    setAuthToken(null);
    selectProject(null);
    setIsAuthenticated(false);
    setUser(null);
  }, [selectProject]);

  useEffect(() => {
    const handleUnauthorized = () => {
      logout();
    };

    window.addEventListener('auth:unauthorized', handleUnauthorized);
    
    // Check if there's a token (there shouldn't be on hard reload since it's in memory)
    if (getAuthToken()) {
      setIsAuthenticated(true);
    }
    setLoading(false);

    return () => {
      window.removeEventListener('auth:unauthorized', handleUnauthorized);
    };
  }, [logout]);

  const login = async (email, password) => {
    const data = await apiLogin(email, password);
    setAuthToken(data.access_token);
    setIsAuthenticated(true);

    // Fetch user's first project to set as current
    try {
      const projectsRes = await getProjects();
      if (projectsRes.items && projectsRes.items.length > 0) {
        selectProject(projectsRes.items[0].id);
      }
    } catch (err) {
      console.error("Failed to load projects after login", err);
    }
  };

  const signup = async (email, password, organization_name) => {
    const data = await apiSignup(email, password, organization_name);
    setAuthToken(data.access_token);
    setIsAuthenticated(true);
    
    // Fetch user's first project to set as current
    try {
      const projectsRes = await getProjects();
      if (projectsRes.items && projectsRes.items.length > 0) {
        selectProject(projectsRes.items[0].id);
      }
    } catch (err) {
      console.error("Failed to load projects after signup", err);
    }
  };

  if (loading) return <div>Loading...</div>;

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, signup, logout, currentProjectId, selectProject }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
