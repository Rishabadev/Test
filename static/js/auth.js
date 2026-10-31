/**
 * Brightloop Software - Authentication Handling (Login & Signup)
 * Manages form submissions, real-time client-side validations,
 * password visibility toggling, JWT storage, role-based redirection,
 * and user logout.
 */

(function () {
  'use strict';

  const auth = {
    // ==========================================
    // 1. INITIALIZATION & ROUTING CHECKS
    // ==========================================

    init() {
      this.setupPasswordToggles();
      this.setupLoginForm();
      this.setupSignupForm();
      this.setupPasswordRequirementsChecklist();
      this.updateHeaderNav();
      this.checkUrlParams();
    },

    checkUrlParams() {
      const params = new URLSearchParams(window.location.search);
      if (params.get('expired') === '1') {
        window.api.showToast('Your session has expired. Please sign in again.', 'warning');
      } else if (params.get('registered') === '1') {
        window.api.showToast('Account created successfully! Please sign in with your credentials.', 'success');
      } else if (params.get('logged_out') === '1') {
        window.api.showToast('You have been logged out safely.', 'info');
      }
    },

    updateHeaderNav() {
      const navContainer = document.getElementById('headerNavAuth');
      if (!navContainer) return;

      if (window.api.isAuthenticated()) {
        navContainer.innerHTML = `
          <button id="logoutBtn" class="btn btn-outline-danger btn-sm px-3 fw-medium d-flex align-items-center gap-1">
            <i class="bi bi-box-arrow-right"></i>
            <span>Sign Out</span>
          </button>
        `;
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
          logoutBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.logout();
          });
        }
      }
    },

    logout() {
      window.api.clearTokens();
      window.api.showToast('You have been signed out.', 'info');
      setTimeout(() => {
        window.location.href = '/login/?logged_out=1';
      }, 400);
    },

    // ==========================================
    // 2. PASSWORD VISIBILITY TOGGLE
    // ==========================================

    setupPasswordToggles() {
      const toggleButtons = document.querySelectorAll('.password-toggle-btn');
      toggleButtons.forEach(btn => {
        btn.addEventListener('click', function () {
          const targetId = this.getAttribute('data-target');
          const input = document.getElementById(targetId);
          if (!input) return;

          const icon = this.querySelector('i');
          if (input.type === 'password') {
            input.type = 'text';
            if (icon) {
              icon.classList.remove('bi-eye');
              icon.classList.add('bi-eye-slash');
            }
          } else {
            input.type = 'password';
            if (icon) {
              icon.classList.remove('bi-eye-slash');
              icon.classList.add('bi-eye');
            }
          }
        });
      });
    },

    // ==========================================
    // 3. LOGIN PAGE HANDLER
    // ==========================================

    setupLoginForm() {
      const form = document.getElementById('loginForm');
      if (!form) return;

      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        e.stopPropagation();

        const emailInput = document.getElementById('loginEmail');
        const passwordInput = document.getElementById('loginPassword');
        const rememberMeInput = document.getElementById('rememberMe');
        const submitBtn = document.getElementById('loginSubmitBtn');
        const alertBox = document.getElementById('loginAlertBox');

        // Reset errors
        emailInput.classList.remove('is-invalid');
        passwordInput.classList.remove('is-invalid');
        if (alertBox) {
          alertBox.classList.add('d-none');
          alertBox.textContent = '';
        }

        const email = emailInput.value.trim();
        const password = passwordInput.value;
        const rememberMe = rememberMeInput ? rememberMeInput.checked : true;

        // Client-side validation
        let hasError = false;
        if (!email || !email.includes('@')) {
          emailInput.classList.add('is-invalid');
          hasError = true;
        }
        if (!password) {
          passwordInput.classList.add('is-invalid');
          hasError = true;
        }
        if (hasError) return;

        // Submit to Backend
        try {
          window.api.showLoading('Signing you in...');
          if (submitBtn) submitBtn.disabled = true;

          // 1. Authenticate with SimpleJWT
          const tokens = await window.api.post('/api/auth/login/', {
            email: email,
            password: password
          });

          // 2. Store tokens
          window.api.setTokens(tokens.access, tokens.refresh, rememberMe);

          // 3. Retrieve user role from /api/auth/me/
          const me = await window.api.get('/api/auth/me/');

          window.api.showToast(`Welcome back, ${me.first_name || me.email}!`, 'success');

          // 4. Role-based Redirection
          setTimeout(() => {
            const role = (me.role || '').toUpperCase();
            if (role === 'ADMIN' || role === 'STAFF') {
              window.location.href = '/dashboard/';
            } else {
              window.location.href = '/portal/';
            }
          }, 600);

        } catch (err) {
          window.api.hideLoading();
          if (submitBtn) submitBtn.disabled = false;

          let errorMsg = 'Invalid email or password. Please verify your credentials.';
          if (err.data) {
            errorMsg = window.api.formatError(err.data);
          } else if (err.message) {
            errorMsg = err.message;
          }

          if (alertBox) {
            alertBox.textContent = errorMsg;
            alertBox.classList.remove('d-none');
          }
          window.api.showToast(errorMsg, 'error');
          passwordInput.classList.add('is-invalid');
        }
      });
    },

    // ==========================================
    // 4. SIGNUP PAGE HANDLER & REAL-TIME CHECKLIST
    // ==========================================

    setupPasswordRequirementsChecklist() {
      const passwordInput = document.getElementById('signupPassword');
      const confirmInput = document.getElementById('signupConfirmPassword');
      if (!passwordInput) return;

      const ruleLength = document.getElementById('ruleLength');
      const ruleUpper = document.getElementById('ruleUpper');
      const ruleLower = document.getElementById('ruleLower');
      const ruleSpecial = document.getElementById('ruleSpecial');
      const ruleMatch = document.getElementById('ruleMatch');

      function validateChecklist() {
        const val = passwordInput.value;
        const confirmVal = confirmInput ? confirmInput.value : '';

        // Requirement 1: More than 8 characters (>= 9 characters)
        const isLengthValid = val.length > 8;
        updateRuleUI(ruleLength, isLengthValid);

        // Requirement 2: At least one uppercase letter (A-Z)
        const isUpperValid = /[A-Z]/.test(val);
        updateRuleUI(ruleUpper, isUpperValid);

        // Requirement 3: At least one lowercase letter (a-z)
        const isLowerValid = /[a-z]/.test(val);
        updateRuleUI(ruleLower, isLowerValid);

        // Requirement 4: At least one special character
        const isSpecialValid = /[^A-Za-z0-9]/.test(val);
        updateRuleUI(ruleSpecial, isSpecialValid);

        // Match Rule (if confirm input exists and has value)
        if (ruleMatch && confirmInput) {
          const isMatchValid = val.length > 0 && confirmVal.length > 0 && val === confirmVal;
          updateRuleUI(ruleMatch, isMatchValid);
        }
      }

      function updateRuleUI(el, isValid) {
        if (!el) return;
        const icon = el.querySelector('i');
        if (isValid) {
          el.classList.remove('invalid');
          el.classList.add('valid');
          if (icon) {
            icon.classList.remove('bi-circle');
            icon.classList.add('bi-check-circle-fill');
          }
        } else {
          el.classList.remove('valid');
          el.classList.add('invalid');
          if (icon) {
            icon.classList.remove('bi-check-circle-fill');
            icon.classList.add('bi-circle');
          }
        }
      }

      passwordInput.addEventListener('input', validateChecklist);
      if (confirmInput) {
        confirmInput.addEventListener('input', validateChecklist);
      }
    },

    setupSignupForm() {
      const form = document.getElementById('signupForm');
      if (!form) return;

      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        e.stopPropagation();

        const emailInput = document.getElementById('signupEmail');
        const firstNameInput = document.getElementById('signupFirstName');
        const lastNameInput = document.getElementById('signupLastName');
        const passwordInput = document.getElementById('signupPassword');
        const confirmInput = document.getElementById('signupConfirmPassword');
        const termsInput = document.getElementById('signupTerms');
        const submitBtn = document.getElementById('signupSubmitBtn');
        const alertBox = document.getElementById('signupAlertBox');

        // Reset previous validation state
        [emailInput, passwordInput, confirmInput, termsInput].forEach(inp => {
          if (inp) inp.classList.remove('is-invalid');
        });
        if (alertBox) {
          alertBox.classList.add('d-none');
          alertBox.textContent = '';
        }

        const email = emailInput.value.trim();
        const firstName = firstNameInput ? firstNameInput.value.trim() : '';
        const lastName = lastNameInput ? lastNameInput.value.trim() : '';
        const password = passwordInput.value;
        const confirmPassword = confirmInput.value;

        // Client-side validation
        let hasError = false;

        if (!email || !email.includes('@')) {
          emailInput.classList.add('is-invalid');
          hasError = true;
        }

        // Validate password rules (strictly > 8 chars, upper, lower, special)
        if (password.length <= 8) {
          passwordInput.classList.add('is-invalid');
          document.getElementById('passwordFeedback').textContent = 'Password must be longer than 8 characters (at least 9).';
          hasError = true;
        } else if (!/[A-Z]/.test(password)) {
          passwordInput.classList.add('is-invalid');
          document.getElementById('passwordFeedback').textContent = 'Password must contain at least one uppercase letter (A-Z).';
          hasError = true;
        } else if (!/[a-z]/.test(password)) {
          passwordInput.classList.add('is-invalid');
          document.getElementById('passwordFeedback').textContent = 'Password must contain at least one lowercase letter (a-z).';
          hasError = true;
        } else if (!/[^A-Za-z0-9]/.test(password)) {
          passwordInput.classList.add('is-invalid');
          document.getElementById('passwordFeedback').textContent = 'Password must contain at least one special character (!, @, #, $, etc.).';
          hasError = true;
        }

        if (password !== confirmPassword) {
          confirmInput.classList.add('is-invalid');
          document.getElementById('confirmPasswordFeedback').textContent = 'Passwords do not match.';
          hasError = true;
        }

        if (termsInput && !termsInput.checked) {
          termsInput.classList.add('is-invalid');
          hasError = true;
        }

        if (hasError) return;

        // Submit to POST /api/auth/signup/
        try {
          window.api.showLoading('Creating your workspace account...');
          if (submitBtn) submitBtn.disabled = true;

          await window.api.post('/api/auth/signup/', {
            email: email,
            password: password,
            first_name: firstName,
            last_name: lastName
          });

          window.api.showToast('Account created successfully! Signing you in...', 'success');

          // Seamless auto-login on signup
          try {
            const tokens = await window.api.post('/api/auth/login/', {
              email: email,
              password: password
            });
            window.api.setTokens(tokens.access, tokens.refresh, true);

            const me = await window.api.get('/api/auth/me/');
            setTimeout(() => {
              window.location.href = '/portal/';
            }, 600);
          } catch (autoLoginErr) {
            // Fallback to login page with prefilled banner
            setTimeout(() => {
              window.location.href = `/login/?registered=1&email=${encodeURIComponent(email)}`;
            }, 800);
          }

        } catch (err) {
          window.api.hideLoading();
          if (submitBtn) submitBtn.disabled = false;

          let errorMsg = 'Failed to create account. Please check the form errors.';

          // Display specific Django validation errors on fields
          if (err.data && typeof err.data === 'object') {
            if (err.data.email) {
              emailInput.classList.add('is-invalid');
              const emailFb = document.getElementById('emailFeedback');
              if (emailFb) emailFb.textContent = Array.isArray(err.data.email) ? err.data.email.join(' ') : err.data.email;
            }
            if (err.data.password) {
              passwordInput.classList.add('is-invalid');
              const passFb = document.getElementById('passwordFeedback');
              if (passFb) passFb.textContent = Array.isArray(err.data.password) ? err.data.password.join(' ') : err.data.password;
            }
            errorMsg = window.api.formatError(err.data);
          } else if (err.message) {
            errorMsg = err.message;
          }

          if (alertBox) {
            alertBox.textContent = errorMsg;
            alertBox.classList.remove('d-none');
          }
          window.api.showToast(errorMsg, 'error');
        }
      });
    }
  };

  window.auth = auth;
  document.addEventListener('DOMContentLoaded', () => auth.init());
})();

