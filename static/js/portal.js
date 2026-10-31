/**
 * Brightloop Software - Customer Portal JavaScript Controller
 * Handles customer authentication validation, tab navigation,
 * KPI calculations, subscription listings, invoice listings, search,
 * status filters, pagination, detail modals, and PDF download.
 */

(function () {
  'use strict';

  // Defensive DOM helper functions
  const setText = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val !== null && val !== undefined ? val : '';
  };

  const setHtml = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = val !== null && val !== undefined ? val : '';
  };

  const setVal = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = val !== null && val !== undefined ? val : '';
  };

  const portal = {
    // Portal Application State
    state: {
      currentUser: null,
      subscriptions: [],
      invoices: [],
      currentTab: 'overview',
      subFilter: {
        search: '',
        status: 'ALL',
        page: 1,
        pageSize: 10
      },
      invFilter: {
        search: '',
        status: 'ALL',
        page: 1,
        pageSize: 10
      }
    },

    // ==========================================
    // 1. INITIALIZATION & ROUTE GUARD
    // ==========================================

    async init() {
      // 1. Verify authentication
      if (!window.api || !window.api.isAuthenticated()) {
        window.location.href = '/login/?expired=1';
        return;
      }

      this.setupDOMEventListeners();

      try {
        window.api.showLoading('Loading customer portal...');

        // 2. Fetch current user identity
        const me = await window.api.get('/api/auth/me/');
        this.state.currentUser = me;

        // Ensure role is CUSTOMER; redirect internal staff to dashboard
        const role = (me.role || '').toUpperCase();
        if (role === 'ADMIN' || role === 'STAFF') {
          window.location.href = '/dashboard/';
          return;
        }

        this.renderUserProfile(me);

        // 3. Load Subscriptions & Invoices concurrently
        await this.loadCustomerData();

        // Check URL hash for direct tab navigation
        this.handleHashChange();

      } catch (err) {
        console.error('Portal initialization error:', err);
        if (err.status === 401 || err.status === 403) {
          window.api.onSessionExpired();
        } else {
          window.api.showToast(err.message || 'Error loading account data.', 'error');
        }
      } finally {
        window.api.hideLoading();
      }
    },

    setupDOMEventListeners() {
      // Sidebar mobile toggle
      const sidebarToggle = document.getElementById('sidebarToggle');
      const sidebar = document.getElementById('portalSidebar');
      const backdrop = document.getElementById('sidebarBackdrop');

      if (sidebarToggle && sidebar && backdrop) {
        sidebarToggle.addEventListener('click', () => {
          sidebar.classList.toggle('show');
          backdrop.classList.toggle('show');
        });

        backdrop.addEventListener('click', () => {
          sidebar.classList.remove('show');
          backdrop.classList.remove('show');
        });
      }

      // Nav Links Tab Switching
      document.querySelectorAll('[data-portal-tab]').forEach(link => {
        link.addEventListener('click', (e) => {
          e.preventDefault();
          const tab = link.getAttribute('data-portal-tab');
          this.switchTab(tab);

          // Close mobile sidebar if open
          if (sidebar && backdrop && sidebar.classList.contains('show')) {
            sidebar.classList.remove('show');
            backdrop.classList.remove('show');
          }
        });
      });

      // Subscriptions Search & Filter
      const subSearch = document.getElementById('subSearchInput');
      const subStatus = document.getElementById('subStatusFilter');
      if (subSearch) {
        subSearch.addEventListener('input', () => {
          this.state.subFilter.search = subSearch.value.trim().toLowerCase();
          this.state.subFilter.page = 1;
          this.renderSubscriptionsTable();
        });
      }
      if (subStatus) {
        subStatus.addEventListener('change', () => {
          this.state.subFilter.status = subStatus.value;
          this.state.subFilter.page = 1;
          this.renderSubscriptionsTable();
        });
      }

      // Invoices Search & Filter
      const invSearch = document.getElementById('invSearchInput');
      const invStatus = document.getElementById('invStatusFilter');
      if (invSearch) {
        invSearch.addEventListener('input', () => {
          this.state.invFilter.search = invSearch.value.trim().toLowerCase();
          this.state.invFilter.page = 1;
          this.renderInvoicesTable();
        });
      }
      if (invStatus) {
        invStatus.addEventListener('change', () => {
          this.state.invFilter.status = invStatus.value;
          this.state.invFilter.page = 1;
          this.renderInvoicesTable();
        });
      }

      // Refresh Button
      const btnRefresh = document.getElementById('btnRefreshData');
      if (btnRefresh) {
        btnRefresh.addEventListener('click', async () => {
          window.api.showToast('Refreshing your data...', 'info');
          await this.loadCustomerData();
          window.api.showToast('Data refreshed successfully.', 'success');
        });
      }

      // Hash change listener
      window.addEventListener('hashchange', () => this.handleHashChange());
    },

    handleHashChange() {
      const hash = window.location.hash.replace('#', '');
      const validTabs = ['overview', 'subscriptions', 'invoices', 'profile'];
      if (validTabs.includes(hash)) {
        this.switchTab(hash);
      }
    },

    switchTab(tabName) {
      this.state.currentTab = tabName;
      window.location.hash = tabName;

      // Update Nav active classes
      document.querySelectorAll('[data-portal-tab]').forEach(link => {
        if (link.getAttribute('data-portal-tab') === tabName) {
          link.classList.add('active');
        } else {
          link.classList.remove('active');
        }
      });

      // Update Panels visibility
      document.querySelectorAll('.portal-panel').forEach(panel => {
        panel.classList.add('d-none');
      });

      const activePanel = document.getElementById(`panel-${tabName}`);
      if (activePanel) {
        activePanel.classList.remove('d-none');
      }

      // Update Breadcrumb
      const breadcrumb = document.getElementById('currentTabBreadcrumb');
      if (breadcrumb) {
        const labels = {
          overview: 'Overview',
          subscriptions: 'My Subscriptions',
          invoices: 'My Invoices',
          profile: 'Customer Profile'
        };
        breadcrumb.textContent = labels[tabName] || 'Overview';
      }
    },

    // ==========================================
    // 2. DATA LOADING & STATE HYDRATION
    // ==========================================

    async loadCustomerData() {
      try {
        const [subsData, invsData] = await Promise.all([
          window.api.get('/api/subscriptions/'),
          window.api.get('/api/invoices/')
        ]);

        this.state.subscriptions = Array.isArray(subsData) ? subsData : (subsData.results || []);
        this.state.invoices = Array.isArray(invsData) ? invsData : (invsData.results || []);

        // Render all UI views
        this.renderOverviewKPIs();
        this.renderOverviewRecent();
        this.renderSubscriptionsTable();
        this.renderInvoicesTable();

      } catch (err) {
        console.error('Failed to load portal data:', err);
        window.api.showToast('Could not load data. ' + (err.message || ''), 'error');
      }
    },

    renderUserProfile(user) {
      const name = [user.first_name, user.last_name].filter(Boolean).join(' ') || 'Customer';
      const initials = (user.first_name ? user.first_name[0] : (user.email ? user.email[0] : 'C')).toUpperCase();

      // Topbar Profile
      const topName = document.getElementById('topbarUserName');
      const topEmail = document.getElementById('topbarUserEmail');
      const topAvatar = document.getElementById('topbarUserAvatar');
      if (topName) topName.textContent = name;
      if (topEmail) topEmail.textContent = user.email;
      if (topAvatar) topAvatar.textContent = initials;

      // Sidebar Profile
      const sideName = document.getElementById('sidebarUserName');
      const sideEmail = document.getElementById('sidebarUserEmail');
      const sideAvatar = document.getElementById('sidebarUserAvatar');
      if (sideName) sideName.textContent = name;
      if (sideEmail) sideEmail.textContent = user.email;
      if (sideAvatar) sideAvatar.textContent = initials;

      // Welcome Banner in Overview
      const welcomeHeading = document.getElementById('welcomeUserHeading');
      if (welcomeHeading) welcomeHeading.textContent = `Welcome back, ${user.first_name || name}!`;

      // Profile Page Fields
      const profId = document.getElementById('profUserId');
      const profEmail = document.getElementById('profEmail');
      const profName = document.getElementById('profFullName');
      const profRole = document.getElementById('profRole');
      if (profId) profId.textContent = `#${user.id}`;
      if (profEmail) profEmail.textContent = user.email;
      if (profName) profName.textContent = name;
      if (profRole) profRole.textContent = user.role;
    },

    // ==========================================
    // 3. OVERVIEW TAB: KPIS & RECENT TABLES
    // ==========================================

    renderOverviewKPIs() {
      const subs = this.state.subscriptions;
      const invs = this.state.invoices;

      const totalSubs = subs.length;
      const activeSubs = subs.filter(s => s.status === 'ACTIVE').length;
      const pendingSubs = subs.filter(s => s.status === 'DRAFT' || s.status === 'QUOTATION').length;

      // Compute total outstanding balance across unpaid invoices
      let outstanding = 0;
      invs.forEach(inv => {
        if (inv.status !== 'CANCELLED') {
          outstanding += parseFloat(inv.amount_due || 0);
        }
      });

      setText('kpiTotalSubs', totalSubs);
      setText('kpiActiveSubs', activeSubs);
      setText('kpiPendingSubs', pendingSubs);
      setText('kpiOutstanding', this.formatCurrency(outstanding));

      // Warning color if outstanding balance > 0
      const outCard = document.getElementById('kpiOutstandingCard');
      if (outCard) {
        if (outstanding > 0) {
          outCard.classList.add('border-warning');
        } else {
          outCard.classList.remove('border-warning');
        }
      }
    },

    renderOverviewRecent() {
      // Recent Invoices (up to 5)
      const recentInvs = [...this.state.invoices].slice(0, 5);
      const invTbody = document.getElementById('recentInvoicesTbody');
      if (invTbody) {
        if (recentInvs.length === 0) {
          invTbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-3">No invoices recorded yet.</td></tr>`;
        } else {
          invTbody.innerHTML = recentInvs.map(inv => `
            <tr>
              <td class="fw-semibold text-navy font-mono">${inv.invoice_number}</td>
              <td class="text-slate-600">${this.formatDate(inv.issue_date)}</td>
              <td class="fw-semibold">${this.formatCurrency(inv.total_amount)}</td>
              <td>${this.formatStatusBadge(inv.status, inv.is_overdue)}</td>
              <td class="text-end">
                <button class="btn btn-sm btn-outline-primary py-0 px-2" onclick="portal.openInvoiceModal(${inv.id})">
                  View
                </button>
              </td>
            </tr>
          `).join('');
        }
      }

      // Recent Subscriptions (up to 5)
      const recentSubs = [...this.state.subscriptions].slice(0, 5);
      const subTbody = document.getElementById('recentSubscriptionsTbody');
      if (subTbody) {
        if (recentSubs.length === 0) {
          subTbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-3">No subscriptions found.</td></tr>`;
        } else {
          subTbody.innerHTML = recentSubs.map(sub => `
            <tr>
              <td class="fw-semibold text-navy font-mono">${sub.subscription_number}</td>
              <td class="fw-medium">${sub.plan_name || 'Custom Plan'}</td>
              <td class="text-slate-500 text-capitalize">${(sub.plan_billing_period || 'Monthly').toLowerCase()}</td>
              <td>${this.formatStatusBadge(sub.status)}</td>
              <td class="text-end">
                <button class="btn btn-sm btn-outline-primary py-0 px-2" onclick="portal.openSubscriptionModal(${sub.id})">
                  Details
                </button>
              </td>
            </tr>
          `).join('');
        }
      }
    },

    // ==========================================
    // 4. MY SUBSCRIPTIONS TAB (TABLE, FILTERS, PAGINATION)
    // ==========================================

    renderSubscriptionsTable() {
      const tbody = document.getElementById('subscriptionsTableBody');
      const emptyState = document.getElementById('subscriptionsEmptyState');
      const tableWrapper = document.getElementById('subscriptionsTableWrapper');
      const countBadge = document.getElementById('subTotalCountBadge');

      if (!tbody) return;

      // Filter by search and status
      const { search, status, page, pageSize } = this.state.subFilter;
      let filtered = this.state.subscriptions.filter(sub => {
        const matchesSearch = !search ||
          (sub.subscription_number && sub.subscription_number.toLowerCase().includes(search)) ||
          (sub.plan_name && sub.plan_name.toLowerCase().includes(search));

        const matchesStatus = (status === 'ALL') || (sub.status === status);
        return matchesSearch && matchesStatus;
      });

      if (countBadge) countBadge.textContent = `${filtered.length} total`;

      if (filtered.length === 0) {
        tableWrapper.classList.add('d-none');
        emptyState.classList.remove('d-none');
        document.getElementById('subPaginationContainer').classList.add('d-none');
        return;
      }

      tableWrapper.classList.remove('d-none');
      emptyState.classList.add('d-none');

      // Pagination
      const totalPages = Math.ceil(filtered.length / pageSize) || 1;
      const currentPage = Math.min(Math.max(1, page), totalPages);
      this.state.subFilter.page = currentPage;

      const startIndex = (currentPage - 1) * pageSize;
      const pageItems = filtered.slice(startIndex, startIndex + pageSize);

      tbody.innerHTML = pageItems.map(sub => {
        // Calculate subscription amount from total_amount or sum of lines
        const amount = sub.total_amount ? parseFloat(sub.total_amount) : (sub.plan_price ? parseFloat(sub.plan_price) : 0);

        return `
          <tr>
            <td class="fw-semibold text-navy font-mono">${sub.subscription_number}</td>
            <td class="fw-semibold text-slate-800">${sub.plan_name || 'Standard Tier'}</td>
            <td>${this.formatDate(sub.start_date)}</td>
            <td>${sub.expiry_date ? this.formatDate(sub.expiry_date) : '<span class="text-muted">Ongoing</span>'}</td>
            <td class="fw-semibold text-slate-900">${this.formatCurrency(amount)}</td>
            <td>
              <span class="badge bg-light text-slate-700 border text-capitalize font-mono">
                ${(sub.plan_billing_period || 'Monthly').toLowerCase()}
              </span>
            </td>
            <td>${this.formatStatusBadge(sub.status)}</td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-primary" onclick="portal.openSubscriptionModal(${sub.id})">
                <i class="bi bi-eye me-1"></i> Details
              </button>
            </td>
          </tr>
        `;
      }).join('');

      this.renderPagination(
        'subPaginationContainer',
        currentPage,
        totalPages,
        filtered.length,
        startIndex,
        pageItems.length,
        (newPage) => {
          this.state.subFilter.page = newPage;
          this.renderSubscriptionsTable();
        }
      );
    },

    // ==========================================
    // 5. MY INVOICES TAB (TABLE, FILTERS, PAGINATION, PDF)
    // ==========================================

    renderInvoicesTable() {
      const tbody = document.getElementById('invoicesTableBody');
      const emptyState = document.getElementById('invoicesEmptyState');
      const tableWrapper = document.getElementById('invoicesTableWrapper');
      const countBadge = document.getElementById('invTotalCountBadge');

      if (!tbody) return;

      const { search, status, page, pageSize } = this.state.invFilter;
      let filtered = this.state.invoices.filter(inv => {
        const matchesSearch = !search ||
          (inv.invoice_number && inv.invoice_number.toLowerCase().includes(search));

        let matchesStatus = true;
        if (status === 'OVERDUE') {
          matchesStatus = !!inv.is_overdue;
        } else if (status !== 'ALL') {
          matchesStatus = (inv.status === status);
        }

        return matchesSearch && matchesStatus;
      });

      if (countBadge) countBadge.textContent = `${filtered.length} total`;

      if (filtered.length === 0) {
        tableWrapper.classList.add('d-none');
        emptyState.classList.remove('d-none');
        document.getElementById('invPaginationContainer').classList.add('d-none');
        return;
      }

      tableWrapper.classList.remove('d-none');
      emptyState.classList.add('d-none');

      // Pagination
      const totalPages = Math.ceil(filtered.length / pageSize) || 1;
      const currentPage = Math.min(Math.max(1, page), totalPages);
      this.state.invFilter.page = currentPage;

      const startIndex = (currentPage - 1) * pageSize;
      const pageItems = filtered.slice(startIndex, startIndex + pageSize);

      tbody.innerHTML = pageItems.map(inv => {
        const amountDue = parseFloat(inv.amount_due || 0);

        return `
          <tr>
            <td class="fw-semibold text-navy font-mono">${inv.invoice_number}</td>
            <td class="text-slate-600">${this.formatDate(inv.issue_date)}</td>
            <td class="${inv.is_overdue ? 'text-danger fw-semibold' : 'text-slate-600'}">
              ${this.formatDate(inv.due_date)}
            </td>
            <td class="fw-semibold text-slate-900">${this.formatCurrency(inv.total_amount)}</td>
            <td class="text-success">${this.formatCurrency(inv.amount_paid)}</td>
            <td class="${amountDue > 0 ? 'fw-bold text-danger' : 'text-muted'}">
              ${this.formatCurrency(amountDue)}
            </td>
            <td>${this.formatStatusBadge(inv.status, inv.is_overdue)}</td>
            <td class="text-end text-nowrap">
              <button class="btn btn-sm btn-outline-primary me-1" onclick="portal.openInvoiceModal(${inv.id})">
                <i class="bi bi-eye me-1"></i> View
              </button>
              <button class="btn btn-sm btn-outline-secondary" onclick="portal.downloadInvoicePdf(${inv.id}, '${inv.invoice_number}')" title="Download PDF">
                <i class="bi bi-file-earmark-pdf"></i>
              </button>
            </td>
          </tr>
        `;
      }).join('');

      this.renderPagination(
        'invPaginationContainer',
        currentPage,
        totalPages,
        filtered.length,
        startIndex,
        pageItems.length,
        (newPage) => {
          this.state.invFilter.page = newPage;
          this.renderInvoicesTable();
        }
      );
    },

    // ==========================================
    // 6. PAGINATION COMPONENT HELPER
    // ==========================================

    renderPagination(containerId, currentPage, totalPages, totalItems, startIndex, countOnPage, onPageSelect) {
      const container = document.getElementById(containerId);
      if (!container) return;

      if (totalItems <= 10) {
        container.classList.add('d-none');
        return;
      }
      container.classList.remove('d-none');

      const start = startIndex + 1;
      const end = startIndex + countOnPage;

      let pageButtons = '';
      for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 1 && i <= currentPage + 1)) {
          pageButtons += `
            <li class="page-item ${i === currentPage ? 'active' : ''}">
              <a class="page-link" href="javascript:void(0)" onclick="portal.handlePageClick('${containerId}', ${i})">${i}</a>
            </li>
          `;
        } else if (i === currentPage - 2 || i === currentPage + 2) {
          pageButtons += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
        }
      }

      container.innerHTML = `
        <div class="d-flex flex-column flex-sm-row align-items-center justify-content-between gap-2 py-3 border-top border-slate-200">
          <div class="text-muted small">
            Showing <span class="fw-semibold text-navy">${start}</span> to <span class="fw-semibold text-navy">${end}</span> of <span class="fw-semibold text-navy">${totalItems}</span> results
          </div>
          <nav aria-label="Table pagination">
            <ul class="pagination pagination-sm mb-0">
              <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                <a class="page-link" href="javascript:void(0)" onclick="portal.handlePageClick('${containerId}', ${currentPage - 1})">Previous</a>
              </li>
              ${pageButtons}
              <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                <a class="page-link" href="javascript:void(0)" onclick="portal.handlePageClick('${containerId}', ${currentPage + 1})">Next</a>
              </li>
            </ul>
          </nav>
        </div>
      `;

      // Store pagination callback
      this[`callback_${containerId}`] = onPageSelect;
    },

    handlePageClick(containerId, newPage) {
      if (this[`callback_${containerId}`]) {
        this[`callback_${containerId}`](newPage);
      }
    },

    // ==========================================
    // 7. SUBSCRIPTION DETAILS MODAL
    // ==========================================

    async openSubscriptionModal(subId) {
      try {
        window.api.showLoading('Loading subscription details...');
        const sub = await window.api.get(`/api/subscriptions/${subId}/`);

        setText('modalSubNumber', sub.subscription_number);
        setHtml('modalSubStatus', this.formatStatusBadge(sub.status));
        setText('modalSubPlan', sub.plan_name || 'Standard Tier');
        setText('modalSubFrequency', (sub.plan_billing_period || 'Monthly'));
        setText('modalSubStartDate', this.formatDate(sub.start_date));
        setText('modalSubExpiryDate', sub.expiry_date ? this.formatDate(sub.expiry_date) : 'Ongoing');
        setText('modalSubNextBilling', sub.next_billing_date ? this.formatDate(sub.next_billing_date) : 'N/A');
        setText('modalSubTerms', `${sub.payment_terms_days || 30} days`);

        // Render Lines
        const linesTbody = document.getElementById('modalSubLinesTbody');
        if (linesTbody) {
          const lines = sub.lines || [];
          if (lines.length === 0) {
            linesTbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-3">No individual items configured.</td></tr>`;
          } else {
            linesTbody.innerHTML = lines.map(line => `
              <tr>
                <td>
                  <div class="fw-semibold text-navy">${line.product_name || 'Product Item'}</div>
                  ${line.variant_name ? `<div class="text-muted small">${line.variant_name}</div>` : ''}
                </td>
                <td class="text-center">${line.quantity}</td>
                <td>${this.formatCurrency(line.unit_price)}</td>
                <td>${line.tax_rate ? `${parseFloat(line.tax_rate)}%` : '0.00%'}</td>
                <td class="text-end fw-semibold">${this.formatCurrency(line.subtotal)}</td>
              </tr>
            `).join('');
          }
        }

        // Total
        const total = sub.total_amount ? parseFloat(sub.total_amount) : (sub.plan_price ? parseFloat(sub.plan_price) : 0);
        setText('modalSubTotal', this.formatCurrency(total));

        // Show Modal
        const modalEl = document.getElementById('subscriptionDetailModal');
        if (modalEl && window.bootstrap) {
          const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
          modal.show();
        }

      } catch (err) {
        console.error('Failed to load subscription:', err);
        window.api.showToast(err.message || 'Error loading subscription details.', 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    // ==========================================
    // 8. INVOICE DETAILS MODAL
    // ==========================================

    async openInvoiceModal(invId) {
      try {
        window.api.showLoading('Loading invoice statement...');
        const inv = await window.api.get(`/api/invoices/${invId}/`);

        setText('modalInvNumber', inv.invoice_number);
        setHtml('modalInvStatus', this.formatStatusBadge(inv.status, inv.is_overdue));

        // Customer details
        setText('modalInvCustName', inv.customer_name || 'Valued Customer');
        setText('modalInvCustEmail', inv.customer_email || '');

        // Dates
        setText('modalInvIssueDate', this.formatDate(inv.issue_date));
        setText('modalInvDueDate', this.formatDate(inv.due_date));
        setText('modalInvPeriod', `${this.formatDate(inv.billing_period_start)} - ${this.formatDate(inv.billing_period_end)}`);
        setText('modalInvSubNumber', inv.subscription_number || 'Direct Order');

        // Overdue Alert Banner
        const overdueAlert = document.getElementById('modalInvOverdueAlert');
        if (overdueAlert) {
          if (inv.is_overdue) {
            overdueAlert.classList.remove('d-none');
          } else {
            overdueAlert.classList.add('d-none');
          }
        }

        // Lines Table
        const linesTbody = document.getElementById('modalInvLinesTbody');
        if (linesTbody) {
          const lines = inv.lines || [];
          if (lines.length === 0) {
            linesTbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-3">No line items recorded.</td></tr>`;
          } else {
            linesTbody.innerHTML = lines.map(line => `
              <tr>
                <td>
                  <div class="fw-semibold text-navy">${line.description || line.product_name || 'Subscription Line'}</div>
                </td>
                <td class="text-center">${line.quantity}</td>
                <td>${this.formatCurrency(line.unit_price)}</td>
                <td>${this.formatCurrency(line.subtotal)}</td>
                <td>${parseFloat(line.tax_rate || 0)}% (${this.formatCurrency(line.tax_amount)})</td>
                <td class="text-end fw-semibold">${this.formatCurrency(line.total)}</td>
              </tr>
            `).join('');
          }
        }

        // Breakdown Summary
        setText('modalInvSubtotal', this.formatCurrency(inv.subtotal));
        setText('modalInvTax', this.formatCurrency(inv.tax_amount));

        const discountRow = document.getElementById('modalInvDiscountRow');
        const discountAmtEl = document.getElementById('modalInvDiscount');
        if (parseFloat(inv.discount_amount || 0) > 0) {
          if (discountRow) discountRow.classList.remove('d-none');
          if (discountAmtEl) discountAmtEl.textContent = `-${this.formatCurrency(inv.discount_amount)}`;
        } else {
          if (discountRow) discountRow.classList.add('d-none');
        }

        setText('modalInvGrandTotal', this.formatCurrency(inv.total_amount));
        setText('modalInvPaid', this.formatCurrency(inv.amount_paid));
        setText('modalInvDue', this.formatCurrency(inv.amount_due));

        // Payments History
        const paymentsSection = document.getElementById('modalInvPaymentsSection');
        const paymentsTbody = document.getElementById('modalInvPaymentsTbody');
        const payments = inv.payments || [];
        if (payments.length > 0 && paymentsTbody) {
          paymentsSection.classList.remove('d-none');
          paymentsTbody.innerHTML = payments.map(p => `
            <tr>
              <td>${this.formatDate(p.payment_date)}</td>
              <td class="text-capitalize">${(p.method || '').toLowerCase().replace(/_/g, ' ')}</td>
              <td class="font-mono small">${p.transaction_reference || '-'}</td>
              <td class="text-end fw-semibold text-success">${this.formatCurrency(p.amount)}</td>
            </tr>
          `).join('');
        } else if (paymentsSection) {
          paymentsSection.classList.add('d-none');
        }

        // Wire Up Modal Action Buttons
        const btnDownloadPdf = document.getElementById('btnModalDownloadPdf');
        const btnPrint = document.getElementById('btnModalPrint');

        if (btnDownloadPdf) {
          btnDownloadPdf.onclick = () => this.downloadInvoicePdf(inv.id, inv.invoice_number);
        }
        if (btnPrint) {
          btnPrint.onclick = () => window.print();
        }

        // Show Modal
        const modalEl = document.getElementById('invoiceDetailModal');
        if (modalEl && window.bootstrap) {
          const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
          modal.show();
        }

      } catch (err) {
        console.error('Failed to load invoice:', err);
        window.api.showToast(err.message || 'Error loading invoice details.', 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    // ==========================================
    // 9. PDF STREAM DOWNLOAD HANDLER
    // ==========================================

    async downloadInvoicePdf(invoiceId, invoiceNumber) {
      try {
        window.api.showLoading(`Downloading invoice ${invoiceNumber}...`);

        const blob = await window.api.get(`/api/invoices/${invoiceId}/pdf/`);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `invoice_${invoiceNumber}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => window.URL.revokeObjectURL(url), 1000);

        window.api.showToast(`Invoice ${invoiceNumber} downloaded.`, 'success');

      } catch (err) {
        console.error('PDF download error:', err);
        window.api.showToast('Could not download PDF invoice.', 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    // ==========================================
    // 10. FORMATTING UTILITIES
    // ==========================================

    formatCurrency(val) {
      const num = parseFloat(val);
      if (isNaN(num)) return '$0.00';
      return '$' + num.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });
    },

    formatDate(dateStr) {
      if (!dateStr) return '-';
      try {
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        return d.toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          year: 'numeric'
        });
      } catch (e) {
        return dateStr;
      }
    },

    formatStatusBadge(statusVal, isOverdue = false) {
      if (!statusVal) return '';
      const s = String(statusVal).toUpperCase();

      if (isOverdue) {
        return `<span class="badge-status badge-status-overdue"><i class="bi bi-exclamation-triangle-fill"></i> OVERDUE</span>`;
      }

      const map = {
        ACTIVE: { class: 'badge-status-active', icon: 'bi-check-circle-fill' },
        CONFIRMED: { class: 'badge-status-confirmed', icon: 'bi-patch-check-fill' },
        PAID: { class: 'badge-status-paid', icon: 'bi-check2-all' },
        DRAFT: { class: 'badge-status-draft', icon: 'bi-pencil-square' },
        QUOTATION: { class: 'badge-status-quotation', icon: 'bi-file-earmark-text' },
        PAUSED: { class: 'badge-status-paused', icon: 'bi-pause-circle-fill' },
        CLOSED: { class: 'badge-status-closed', icon: 'bi-slash-circle' },
        CANCELLED: { class: 'badge-status-cancelled', icon: 'bi-x-circle-fill' }
      };

      const entry = map[s] || { class: 'badge-status-draft', icon: 'bi-circle' };
      return `<span class="badge-status ${entry.class}"><i class="bi ${entry.icon}"></i> ${s}</span>`;
    }
  };

  window.portal = portal;
  document.addEventListener('DOMContentLoaded', () => portal.init());
})();

