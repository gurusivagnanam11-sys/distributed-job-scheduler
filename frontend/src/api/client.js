const API_BASE_URL = 'http://localhost:8000';

let authToken = null;
let currentProject = null;

export const setAuthToken = (token) => {
  authToken = token;
};

export const getAuthToken = () => {
  return authToken;
};

export const setCurrentProject = (projectId) => {
  currentProject = projectId;
};

export const getCurrentProject = () => {
  return currentProject;
};

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function fetchWithAuth(endpoint, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      // Trigger a custom event to tell the AuthProvider to logout
      window.dispatchEvent(new Event('auth:unauthorized'));
    }
    
    let errorMessage = response.statusText;
    try {
      const errorData = await response.json();
      if (errorData.error && errorData.error.message) {
        errorMessage = errorData.error.message;
      } else if (errorData.detail) {
        errorMessage = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
      }
    } catch (e) {
      // Not JSON
    }
    
    throw new ApiError(response.status, errorMessage);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

// --- Auth API ---

export const login = async (email, password) => {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    let errorMessage = response.statusText;
    try {
      const errorData = await response.json();
      if (errorData.detail) errorMessage = errorData.detail;
    } catch (e) {}
    throw new ApiError(response.status, errorMessage);
  }

  return response.json();
};

// --- Project API ---
export const getProjects = async () => {
  return fetchWithAuth('/projects');
};

export const createProject = async (name, description) => {
  return fetchWithAuth('/projects', {
    method: 'POST',
    body: JSON.stringify({ name, description }),
  });
};

// --- Worker API ---
export const getWorkers = async (page = 1, pageSize = 20, status = null) => {
  let url = `/workers?page=${page}&page_size=${pageSize}`;
  if (status) {
    url += `&status=${status}`;
  }
  return fetchWithAuth(url);
};

// --- Queue API ---

export const getQueues = async (projectId) => {
  return fetchWithAuth(`/projects/${projectId}/queues`);
};

export const createQueue = async (projectId, data) => {
  return fetchWithAuth(`/projects/${projectId}/queues`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
};

export const updateQueue = async (queueId, data) => {
  return fetchWithAuth(`/queues/${queueId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
};

export const deleteQueue = async (queueId) => {
  return fetchWithAuth(`/queues/${queueId}`, {
    method: 'DELETE',
  });
};

export const getRetryPolicy = async (queueId) => {
  return fetchWithAuth(`/queues/${queueId}/retry-policy`);
};

export const createRetryPolicy = async (queueId, data) => {
  return fetchWithAuth(`/queues/${queueId}/retry-policy`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
};

export const updateRetryPolicy = async (queueId, data) => {
  return fetchWithAuth(`/queues/${queueId}/retry-policy`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
};

export const pauseQueue = async (queueId) => {
  return fetchWithAuth(`/queues/${queueId}/pause`, { method: 'POST' });
};

export const resumeQueue = async (queueId) => {
  return fetchWithAuth(`/queues/${queueId}/resume`, { method: 'POST' });
};

export const getQueueMetrics = async (queueId) => {
  return fetchWithAuth(`/queues/${queueId}/metrics`);
};

// --- Job API ---

export const getJobs = async (queueId, page = 1, pageSize = 20, status = null) => {
  let url = `/queues/${queueId}/jobs?page=${page}&page_size=${pageSize}`;
  if (status) {
    url += `&status=${status}`;
  }
  return fetchWithAuth(url);
};

export const getJobTimeline = async (jobId) => {
  return fetchWithAuth(`/jobs/${jobId}/timeline`);
};

export const getJobExecutions = async (jobId, page = 1, pageSize = 10) => {
  return fetchWithAuth(`/jobs/${jobId}/executions?page=${page}&page_size=${pageSize}`);
};

export const retryJob = async (jobId) => {
  return fetchWithAuth(`/jobs/${jobId}/retry`, { method: 'POST' });
};

export const getJob = async (jobId) => {
  return fetchWithAuth(`/jobs/${jobId}`);
};

export const getJobFailureSummary = async (jobId) => {
  return fetchWithAuth(`/jobs/${jobId}/failure-summary`);
};
