/**
 * Brightloop Software - Core Reusable API Module
 * Provides standardized Fetch API methods (GET, POST, PUT, PATCH, DELETE),
 * automatic JWT Authorization headers, silent token refresh on 401,
 * and friendly DRF error formatting.
 */

(function () {
  'use strict';

  // Storage keys for JWT tokens
  const ACCESS_TOKEN_KEY = 'brightloop_access_token';
  const REFRESH_TOKEN_KEY = 'brightloop_refresh_token';

  // In-flight refresh promise to prevent duplicate refresh requests
  let isRefreshing = false;
  let refreshSubscribers = [];

  function onRefreshed(token) {
    refreshSubscribers.map(cb => cb(token));
    refreshSubscribers = [];
  }

  function addRefreshSubscriber(cb) {
    refreshSubscribers.push(cb);
  }

  const api = {
    // ==========================================
    // 1. TOKEN STORAGE MANAGEMENT
    // ==========================================

    getAccessToken() {
      return localStorage.getItem(ACCESS_TOKEN_KEY) || sessionStorage.getItem(ACCESS_TOKEN_KEY) || null;
    },

    getRefreshToken() {
      return localStorage.getItem(REFRESH_TOKEN_KEY) || sessionStorage.getItem(REFRESH_TOKEN_KEY) || null;
    },

    setTokens(access, refresh, rememberMe = true) {
      if (rememberMe) {
        if (access) localStorage.setItem(ACCESS_TOKEN_KEY, access);
        if (refresh) localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
        sessionStorage.removeItem(ACCESS_TOKEN_KEY);
        sessionStorage.removeItem(REFRESH_TOKEN_KEY);
      } else {
        if (access) sessionStorage.setItem(ACCESS_TOKEN_KEY, access);
        if (refresh) sessionStorage.setItem(REFRESH_TOKEN_KEY, refresh);
        localStorage.removeItem(ACCESS_TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
      }
    },

    clearTokens() {
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      sessionStorage.removeItem(ACCESS_TOKEN_KEY);
      sessionStorage.removeItem(REFRESH_TOKEN_KEY);
    },

    isAuthenticated() {
      return !!this.getAccessToken();
    },

    onSessionExpired() {
      this.clearTokens();
      this.showToast('Your session has expired. Please sign in again.', 'warning');
      setTimeout(() => {
        if (window.location.pathname !== '/login/' && window.location.pathname !== '/signup/') {
          window.location.href = '/login/?expired=1';
        }
      }, 1200);
    },

    // ==========================================
    // 2. TOKEN REFRESH LOGIC
    // ==========================================

    async refreshToken() {
      const refresh = this.getRefreshToken();
      if (!refresh) {
        throw new Error('No refresh token available');
      }

      const response = await fetch('/api/auth/token/refresh/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ refresh })
      });

      if (!response.ok) {
        this.clearTokens();
        throw new Error('Refresh token invalid or expired');
      }

      const data = await response.json();
      const newAccess = data.access;
      const newRefresh = data.refresh || refresh;

      // Persist in the same storage where refresh was located
      const isLocalStorage = !!localStorage.getItem(REFRESH_TOKEN_KEY);
      this.setTokens(newAccess, newRefresh, isLocalStorage);

      return newAccess;
    },

    // ==========================================
    // 3. CORE REQUEST WRAPPER
    // ==========================================

    async request(url, options = {}) {
      const config = {
        method: options.method || 'GET',
        headers: {
          'Accept': 'application/json',
          ...(options.headers || {})
        },
        ...options
      };

      // Add Content-Type header if sending JSON
      if (config.body && !(config.body instanceof FormData) && typeof config.body === 'object') {
        config.headers['Content-Type'] = 'application/json';
        config.body = JSON.stringify(config.body);
      }

      // Attach JWT Authorization header if available
      const token = this.getAccessToken();
      if (token && !config.headers['Authorization']) {
        config.headers['Authorization'] = `Bearer ${token}`;
      }

      try {
        let response = await fetch(url, config);

        // Handle 401 Unauthorized with Automatic Token Refresh
        if (response.status === 401 && !url.includes('/api/auth/login/') && !url.includes('/api/auth/token/refresh/')) {
          if (!this.getRefreshToken()) {
            this.onSessionExpired();
            const err = new Error('Authentication required');
            err.status = 401;
            throw err;
          }

          if (!isRefreshing) {
            isRefreshing = true;
            try {
              const newAccessToken = await this.refreshToken();
              isRefreshing = false;
              onRefreshed(newAccessToken);
            } catch (refreshErr) {
              isRefreshing = false;
              this.onSessionExpired();
              throw refreshErr;
            }
          }

          // Wait for token refresh completion
          const retryPromise = new Promise((resolve, reject) => {
            addRefreshSubscriber(newToken => {
              config.headers['Authorization'] = `Bearer ${newToken}`;
              fetch(url, config).then(resolve).catch(reject);
            });
          });

          response = await retryPromise;
        }

        // Parse Response Data
        let data = null;
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
          data = await response.json();
        } else if (contentType.includes('application/pdf')) {
          data = await response.blob();
        } else {
          data = await response.text();
        }

        if (!response.ok) {
          const formattedMsg = this.formatError(data);
          const error = new Error(formattedMsg);
          error.status = response.status;
          error.data = data;
          throw error;
        }

        return data;

      } catch (err) {
        // Normalize network or parsing errors
        if (!err.status) {
          err.status = 0;
          err.message = err.message || 'Network error: could not connect to server.';
        }
        throw err;
      }
    },

    // HTTP Method Shortcuts
    get(url, options = {}) {
      return this.request(url, { ...options, method: 'GET' });
    },

    post(url, body, options = {}) {
      return this.request(url, { ...options, method: 'POST', body });
    },

    put(url, body, options = {}) {
      return this.request(url, { ...options, method: 'PUT', body });
    },

    patch(url, body, options = {}) {
      return this.request(url, { ...options, method: 'PATCH', body });
    },

    delete(url, options = {}) {
      return this.request(url, { ...options, method: 'DELETE' });
    },

    // ==========================================
    // 4. FRIENDLY ERROR FORMATTER
    // ==========================================

    formatError(errorData) {
      if (!errorData) {
        return 'An unexpected error occurred. Please try again.';
      }

      if (typeof errorData === 'string') {
        return errorData;
      }

      if (errorData.detail) {
        return errorData.detail;
      }

      if (errorData.non_field_errors && Array.isArray(errorData.non_field_errors)) {
        return errorData.non_field_errors.join(' ');
      }

      if (typeof errorData === 'object') {
        const errorMessages = [];
        for (const [field, messages] of Object.entries(errorData)) {
          const fieldTitle = field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
          if (Array.isArray(messages)) {
            errorMessages.push(`${fieldTitle}: ${messages.join(' ')}`);
          } else if (typeof messages === 'string') {
            errorMessages.push(`${fieldTitle}: ${messages}`);
          }
        }
        if (errorMessages.length > 0) {
          return errorMessages.join(' | ');
        }
      }

      return 'An error occurred while processing your request.';
    },

    // ==========================================
    // 5. TOAST & LOADING UI UTILITIES
    // ==========================================

    showToast(message, type = 'info', title = null) {
      const container = document.getElementById('toastContainer');
      if (!container) return;

      const toastId = `toast-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
      const icons = {
        success: 'bi-check-circle-fill text-success',
        error: 'bi-exclamation-triangle-fill text-danger',
        warning: 'bi-exclamation-circle-fill text-warning',
        info: 'bi-info-circle-fill text-primary'
      };

      const defaultTitles = {
        success: 'Success',
        error: 'Error',
        warning: 'Attention',
        info: 'Information'
      };

      const toastHtml = `
        <div id="${toastId}" class="toast toast-${type} bg-white shadow-card mb-2" role="alert" aria-live="assertive" aria-atomic="true">
          <div class="toast-header border-bottom-0 pb-1">
            <i class="bi ${icons[type] || icons.info} me-2 fs-6"></i>
            <strong class="me-auto text-slate-800">${title || defaultTitles[type] || 'Notification'}</strong>
            <small class="text-muted">just now</small>
            <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
          </div>
          <div class="toast-body pt-0 text-slate-600 small">
            ${message}
          </div>
        </div>
      `;

      container.insertAdjacentHTML('beforeend', toastHtml);
      const toastEl = document.getElementById(toastId);
      if (toastEl && window.bootstrap && window.bootstrap.Toast) {
        const toast = new bootstrap.Toast(toastEl, { delay: 4500 });
        toast.show();
        toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
      }
    },

    showLoading(text = 'Processing...') {
      const overlay = document.getElementById('globalLoadingOverlay');
      const textEl = document.getElementById('loadingText');
      if (overlay) {
        if (textEl) textEl.textContent = text;
        overlay.classList.remove('d-none');
      }
    },

    hideLoading() {
      const overlay = document.getElementById('globalLoadingOverlay');
      if (overlay) {
        overlay.classList.add('d-none');
      }
    }
  };

  window.api = api;
})();

