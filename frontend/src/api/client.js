const API_BASE_URL = import.meta.env.VITE_API_URL || (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.hostname}:8001` : 'http://localhost:8001');
const CURRENT_PROJECT_STORAGE_KEY = 'jobscheduler.currentProject';

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
  try {
    if (projectId) {
      window.localStorage.setItem(CURRENT_PROJECT_STORAGE_KEY, projectId);
    } else {
      window.localStorage.removeItem(CURRENT_PROJECT_STORAGE_KEY);
    }
  } catch (error) {
    // Ignore storage failures and keep the in-memory value.
  }
};

export const getCurrentProject = () => {
  if (currentProject) {
    return currentProject;
  }

  try {
    const storedProject = window.localStorage.getItem(CURRENT_PROJECT_STORAGE_KEY);
    if (storedProject) {
      currentProject = storedProject;
      return storedProject;
    }
  } catch (error) {
    // Ignore storage failures.
  }

  return null;
};

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function readErrorMessage(response) {
  let errorMessage = response.statusText;
  try {
    const errorData = await response.json();
    if (errorData?.error?.message) {
      errorMessage = errorData.error.message;
    } else if (errorData?.detail) {
      if (typeof errorData.detail === 'string') {
        errorMessage = errorData.detail;
      } else if (Array.isArray(errorData.detail)) {
        errorMessage = errorData.detail
          .map((item) => {
            const location = Array.isArray(item.loc) ? item.loc.join('.') : '';
            const message = item.msg || 'Validation error';
            return location ? `${location}: ${message}` : message;
          })
          .join('; ');
      } else {
        errorMessage = JSON.stringify(errorData.detail);
      }
    }
  } catch (e) {
    // Not JSON or unreadable body
  }
  return errorMessage;
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

    throw new ApiError(response.status, await readErrorMessage(response));
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
    throw new ApiError(response.status, await readErrorMessage(response));
  }

  return response.json();
};

export const signup = async (email, password, organization_name) => {
  const response = await fetch(`${API_BASE_URL}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, organization_name }),
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response));
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

export const getApiKeys = async (projectId) => {
  return fetchWithAuth(`/projects/${projectId}/api-keys`);
};

export const createApiKey = async (projectId, data) => {
  return fetchWithAuth(`/projects/${projectId}/api-keys`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
};

export const revokeApiKey = async (projectId, keyId) => {
  return fetchWithAuth(`/projects/${projectId}/api-keys/${keyId}`, {
    method: 'DELETE',
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

export const submitJob = async (queueId, data) => {
  return fetchWithAuth(`/queues/${queueId}/jobs`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
};

export const getJobs = async (queueId, page = 1, pageSize = 20, status = null) => {
  let url = `/queues/${queueId}/jobs?page=${page}&page_size=${pageSize}`;
  if (status) {
    url += `&status=${status}`;
  }
  return fetchWithAuth(url);
};

export const getJob = async (jobId) => {
  return fetchWithAuth(`/jobs/${jobId}`);
};

export const getRecurringJobs = async (queueId, page = 1, pageSize = 20) => {
  return fetchWithAuth(`/queues/${queueId}/recurring-jobs?page=${page}&page_size=${pageSize}`);
};

export const updateRecurringJob = async (queueId, templateId, data) => {
  return fetchWithAuth(`/queues/${queueId}/recurring-jobs/${templateId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
};

export const deleteRecurringJob = async (queueId, templateId) => {
  return fetchWithAuth(`/queues/${queueId}/recurring-jobs/${templateId}`, {
    method: 'DELETE',
  });
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


export const getJobFailureSummary = async (jobId) => {
  return fetchWithAuth(`/jobs/${jobId}/failure-summary`);
};
