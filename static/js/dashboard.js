/**
 * Brightloop Software - Admin & Staff Finance Dashboard Controller
 * Enforces role-based navigation visibility (ADMIN vs STAFF),
 * loads high-performance financial metrics from /api/dashboard/,
 * manages date/status/customer filters, paginates payments & overdue tables,
 * and renders Chart.js visualizations using real backend data.
 */

(function () {
  'use strict';

  // Defensive DOM helper functions to prevent null pointer exceptions
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

  const dashboard = {
    // Dashboard Controller State
    state: {
      currentUser: null,
      overview: null,
      payments: [],
      overdueInvoices: [],
      subscriptions: [],
      allInvoices: [],
      plans: [],
      products: [],
      customers: [],
      subFilterStatus: 'ALL',
      subSearch: '',
      invSearch: '',
      paymentsPage: 1,
      overduePage: 1,
      subsPage: 1,
      allInvsPage: 1,
      filters: {
        start_date: '',
        end_date: '',
        status: '',
        customer: ''
      },
      charts: {
        revenueChart: null,
        subStatusChart: null,
        paymentMethodChart: null
      }
    },

    // ==========================================
    // 1. INITIALIZATION & ROLE-BASED ACCESS
    // ==========================================

    async init() {
      // 1. Authentication Check
      if (!window.api || !window.api.isAuthenticated()) {
        window.location.href = '/login/?expired=1';
        return;
      }

      this.setupDOMEventListeners();

      try {
        window.api.showLoading('Loading finance dashboard...');

        // 2. Fetch authenticated user identity
        const me = await window.api.get('/api/auth/me/');
        this.state.currentUser = me;

        const role = (me.role || '').toUpperCase();

        // Security boundary: Customer cannot access internal dashboard
        if (role === 'CUSTOMER') {
          window.location.href = '/portal/';
          return;
        }

        // Apply Role-Based Navigation Visibility
        this.applyRoleBasedVisibility(role, me);

        // 3. Load Dashboard Data
        await this.loadDashboardData();

      } catch (err) {
        console.error('Dashboard init error:', err);
        if (err.status === 401 || err.status === 403) {
          window.api.onSessionExpired();
        } else {
          window.api.showToast(err.message || 'Error loading dashboard.', 'error');
        }
      } finally {
        window.api.hideLoading();
      }
    },

    applyRoleBasedVisibility(role, user) {
      const name = [user.first_name, user.last_name].filter(Boolean).join(' ') || (role === 'ADMIN' ? 'Administrator' : 'Staff Member');
      const initials = (user.first_name ? user.first_name[0] : (user.email ? user.email[0] : 'U')).toUpperCase();

      // Topbar user info
      const topName = document.getElementById('dashTopUserName');
      const topEmail = document.getElementById('dashTopUserEmail');
      const topAvatar = document.getElementById('dashTopUserAvatar');
      const topBadge = document.getElementById('dashTopRoleBadge');

      if (topName) topName.textContent = name;
      if (topEmail) topEmail.textContent = user.email;
      if (topAvatar) topAvatar.textContent = initials;
      if (topBadge) {
        topBadge.textContent = role;
        topBadge.className = `badge font-mono small ${role === 'ADMIN' ? 'bg-danger-subtle text-danger border border-danger-subtle' : 'bg-warning-subtle text-warning-emphasis border border-warning-subtle'}`;
      }

      // Sidebar role badge
      const sideBadge = document.getElementById('dashSidebarRoleBadge');
      if (sideBadge) {
        sideBadge.textContent = role;
        sideBadge.className = `badge font-mono ${role === 'ADMIN' ? 'bg-danger text-white' : 'bg-warning text-dark'}`;
      }

      // Role-Based Navigation Visibility:
      // ADMIN: Access all modules.
      // STAFF: Access Dashboard, Subscriptions, Invoices, Payments.
      // Restricted items to hide from STAFF:
      const adminOnlyNavIds = [
        'navProducts',
        'navPlans',
        'navDiscounts',
        'navStaffManagement',
        'sectionAdminHeader'
      ];

      if (role === 'STAFF') {
        adminOnlyNavIds.forEach(id => {
          const el = document.getElementById(id);
          if (el) el.classList.add('d-none');
        });
      } else {
        adminOnlyNavIds.forEach(id => {
          const el = document.getElementById(id);
          if (el) el.classList.remove('d-none');
        });
      }
    },

    setupDOMEventListeners() {
      // Sidebar Collapse / Mobile Toggle
      const sidebarToggle = document.getElementById('dashSidebarToggle');
      const sidebar = document.getElementById('dashSidebar');
      const wrapper = document.getElementById('dashWrapper');
      const backdrop = document.getElementById('dashSidebarBackdrop');

      if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', () => {
          if (window.innerWidth < 992) {
            sidebar.classList.toggle('show');
            if (backdrop) backdrop.classList.toggle('show');
          } else {
            wrapper.classList.toggle('sidebar-collapsed');
          }
        });
      }

      if (backdrop && sidebar) {
        backdrop.addEventListener('click', () => {
          sidebar.classList.remove('show');
          backdrop.classList.remove('show');
        });
      }

      // Filter Form Submit
      const filterForm = document.getElementById('dashFilterForm');
      if (filterForm) {
        filterForm.addEventListener('submit', (e) => {
          e.preventDefault();
          this.applyFilters();
        });
      }

      // Reset Filter Button
      const btnReset = document.getElementById('btnResetFilters');
      if (btnReset) {
        btnReset.addEventListener('click', () => {
          this.resetFilters();
        });
      }

      // Quick Refresh Button
      const btnRefresh = document.getElementById('btnRefreshDashboard');
      if (btnRefresh) {
        btnRefresh.addEventListener('click', async () => {
          window.api.showToast('Refreshing dashboard...', 'info');
          await this.loadDashboardData();
          window.api.showToast('Dashboard data updated.', 'success');
        });
      }

      // Subscriptions Search & Status Filter
      const subStatusFilter = document.getElementById('subStatusFilter');
      if (subStatusFilter) {
        subStatusFilter.addEventListener('change', () => {
          this.state.subFilterStatus = subStatusFilter.value;
          this.state.subsPage = 1;
          this.renderSubscriptionsTable();
        });
      }

      const subSearchInput = document.getElementById('subSearchInput');
      if (subSearchInput) {
        subSearchInput.addEventListener('input', () => {
          this.state.subSearch = subSearchInput.value.trim().toLowerCase();
          this.state.subsPage = 1;
          this.renderSubscriptionsTable();
        });
      }

      // Invoice Search Filter
      const invSearchInput = document.getElementById('invoiceSearchInput');
      if (invSearchInput) {
        invSearchInput.addEventListener('input', () => {
          this.state.invSearch = invSearchInput.value.trim().toLowerCase();
          this.state.allInvsPage = 1;
          this.renderAllInvoicesTable();
        });
      }

      // Create Subscription Form
      const createSubForm = document.getElementById('createSubscriptionForm');
      if (createSubForm) {
        createSubForm.addEventListener('submit', (e) => {
          e.preventDefault();
          this.createSubscription();
        });
      }

      const btnAddSubLine = document.getElementById('btnAddSubLine');
      if (btnAddSubLine) {
        btnAddSubLine.addEventListener('click', () => {
          this.addSubLineRow();
        });
      }

      // Record Payment Form
      const recordPaymentForm = document.getElementById('recordPaymentForm');
      if (recordPaymentForm) {
        recordPaymentForm.addEventListener('submit', (e) => {
          e.preventDefault();
          this.recordPayment();
        });
      }
    },

    // ==========================================
    // 2. DATA LOADING & FILTERING
    // ==========================================

    buildQueryString(includePagination = true, pageType = 'payments') {
      const params = new URLSearchParams();
      const f = this.state.filters;

      if (f.start_date) params.append('start_date', f.start_date);
      if (f.end_date) params.append('end_date', f.end_date);
      if (f.status && f.status !== 'ALL') params.append('status', f.status);
      if (f.customer) params.append('customer', f.customer);

      if (includePagination) {
        if (pageType === 'payments') {
          params.append('page', this.state.paymentsPage);
        } else if (pageType === 'overdue') {
          params.append('page', this.state.overduePage);
        }
      }

      const qs = params.toString();
      return qs ? `?${qs}` : '';
    },

    async loadDashboardData() {
      try {
        const filterQuery = this.buildQueryString(false);
        const paymentsQuery = this.buildQueryString(true, 'payments');
        const overdueQuery = this.buildQueryString(true, 'overdue');

        // Fetch metrics, invoices, subscriptions, plans, products, and payments in parallel
        const [overviewRes, overdueRes, paymentsRes, subsRes, invsRes, plansRes, prodsRes] = await Promise.all([
          window.api.get(`/api/dashboard/${filterQuery}`),
          window.api.get(`/api/dashboard/overdue-invoices/${overdueQuery}`),
          window.api.get(`/api/dashboard/payments/${paymentsQuery}`),
          window.api.get('/api/subscriptions/?limit=100').catch(() => []),
          window.api.get('/api/invoices/?limit=100').catch(() => []),
          window.api.get('/api/plans/?limit=100').catch(() => []),
          window.api.get('/api/products/?limit=100').catch(() => [])
        ]);

        this.state.overview = overviewRes;
        this.state.overdueInvoices = overdueRes;
        this.state.payments = paymentsRes;
        this.state.subscriptions = Array.isArray(subsRes) ? subsRes : (subsRes.results || []);
        this.state.allInvoices = Array.isArray(invsRes) ? invsRes : (invsRes.results || []);
        this.state.plans = Array.isArray(plansRes) ? plansRes : (plansRes.results || []);
        this.state.products = Array.isArray(prodsRes) ? prodsRes : (prodsRes.results || []);

        // Extract unique customers from subscriptions and invoices
        const customerMap = new Map();
        this.state.subscriptions.forEach(s => {
          if (s.customer && s.customer_email) customerMap.set(s.customer, s.customer_email);
        });
        this.state.allInvoices.forEach(i => {
          if (i.customer && i.customer_email) customerMap.set(i.customer, i.customer_email);
        });
        this.state.customers = Array.from(customerMap.entries()).map(([id, email]) => ({ id, email }));

        // 1. Render Statistic Cards
        this.renderStatisticCards(overviewRes);

        // 2. Render Subscriptions Table (MVP 2)
        this.renderSubscriptionsTable();

        // 3. Render All Invoices Table (MVP 3)
        this.renderAllInvoicesTable();

        // 4. Render Overdue Invoices Table
        this.renderOverdueTable(overdueRes);

        // 5. Render Payments Table
        this.renderPaymentsTable(paymentsRes);

        // 6. Update counts in hub
        const countAll = document.getElementById('countAllInvoicesBadge');
        if (countAll) countAll.textContent = this.state.allInvoices.length;
        const countOverdue = document.getElementById('countOverdueBadge');
        if (countOverdue) countOverdue.textContent = (overdueRes.count || (Array.isArray(overdueRes) ? overdueRes.length : 0));
        const countPays = document.getElementById('countPaymentsBadge');
        if (countPays) countPays.textContent = (paymentsRes.count || (Array.isArray(paymentsRes) ? paymentsRes.length : 0));

        // 7. Render Visualizations with Chart.js
        this.renderCharts(overviewRes, paymentsRes, this.state.subscriptions);

      } catch (err) {
        console.error('Failed to load dashboard data:', err);
        window.api.showToast(err.message || 'Error fetching dashboard metrics.', 'error');
      }
    },

    applyFilters() {
      const startDateInput = document.getElementById('filterStartDate');
      const endDateInput = document.getElementById('filterEndDate');
      const statusInput = document.getElementById('filterStatus');
      const customerInput = document.getElementById('filterCustomer');

      this.state.filters = {
        start_date: startDateInput ? startDateInput.value.trim() : '',
        end_date: endDateInput ? endDateInput.value.trim() : '',
        status: statusInput ? statusInput.value : '',
        customer: customerInput ? customerInput.value.trim() : ''
      };

      this.state.paymentsPage = 1;
      this.state.overduePage = 1;

      window.api.showToast('Applying filters...', 'info');
      this.loadDashboardData().then(() => {
        window.api.showToast('Filters applied successfully.', 'success');
      });
    },

    resetFilters() {
      const startDateInput = document.getElementById('filterStartDate');
      const endDateInput = document.getElementById('filterEndDate');
      const statusInput = document.getElementById('filterStatus');
      const customerInput = document.getElementById('filterCustomer');

      if (startDateInput) startDateInput.value = '';
      if (endDateInput) endDateInput.value = '';
      if (statusInput) statusInput.value = 'ALL';
      if (customerInput) customerInput.value = '';

      this.state.filters = {
        start_date: '',
        end_date: '',
        status: '',
        customer: ''
      };

      this.state.paymentsPage = 1;
      this.state.overduePage = 1;

      this.loadDashboardData().then(() => {
        window.api.showToast('Filters reset to default.', 'info');
      });
    },

    // ==========================================
    // 3. STATISTIC CARDS RENDERING
    // ==========================================

    renderStatisticCards(data) {
      if (!data) return;

      const activeCount = data.active_subscription_count !== undefined ? Number(data.active_subscription_count).toLocaleString() : '0';
      const revenue = this.formatCurrency(data.total_revenue || 0);
      const outstanding = this.formatCurrency(data.total_outstanding_amount || 0);
      const overdueCount = data.overdue_invoices_count !== undefined ? Number(data.overdue_invoices_count).toLocaleString() : '0';
      const overdueAmt = this.formatCurrency(data.overdue_amount || 0);

      const elActiveSubs = document.getElementById('statActiveSubs');
      const elRevenue = document.getElementById('statRevenue') || document.getElementById('statTotalRevenue');
      const elOutstanding = document.getElementById('statOutstanding');
      const elOverdueCount = document.getElementById('statOverdueCount');
      const elStatOverdueAmt = document.getElementById('statOverdueAmount');
      const elBadgeOverdue = document.getElementById('badgeOverdueAmount');

      if (elActiveSubs) elActiveSubs.textContent = activeCount;
      if (elRevenue) elRevenue.textContent = revenue;
      if (elOutstanding) elOutstanding.textContent = outstanding;
      if (elOverdueCount) elOverdueCount.textContent = overdueCount;
      if (elStatOverdueAmt) elStatOverdueAmt.textContent = overdueAmt;
      if (elBadgeOverdue) elBadgeOverdue.innerHTML = `<i class="bi bi-shield-exclamation me-1"></i> ${overdueAmt} at risk`;

      // Notification badge
      const notifBadge = document.getElementById('topbarNotifBadge');
      if (notifBadge) {
        if (Number(data.overdue_invoices_count) > 0) {
          notifBadge.classList.remove('d-none');
        } else {
          notifBadge.classList.add('d-none');
        }
      }
    },

    // ==========================================
    // 4. OVERDUE INVOICES TABLE
    // ==========================================

    renderOverdueTable(paginatedData) {
      const tbody = document.getElementById('overdueTableBody');
      const countBadge = document.getElementById('overdueCountBadge');
      const paginationContainer = document.getElementById('overduePaginationContainer');

      if (!tbody) return;

      const items = paginatedData ? (paginatedData.results || paginatedData) : [];
      const totalCount = paginatedData && paginatedData.count !== undefined ? paginatedData.count : items.length;

      if (countBadge) countBadge.textContent = `${totalCount} Overdue`;

      if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4"><i class="bi bi-check-circle text-success me-2"></i>No overdue invoices found.</td></tr>`;
        if (paginationContainer) paginationContainer.classList.add('d-none');
        return;
      }

      tbody.innerHTML = items.map(inv => {
        const days = inv.days_overdue || 0;
        const cust = inv.customer_name || inv.customer_email || `Customer #${inv.customer}`;

        return `
          <tr>
            <td class="fw-semibold text-navy font-mono">${inv.invoice_number}</td>
            <td>
              <div class="fw-medium text-slate-800 text-truncate" style="max-width: 170px;">${cust}</div>
              <div class="text-muted font-mono" style="font-size: 0.725rem;">${inv.customer_email || ''}</div>
            </td>
            <td class="text-slate-600">${this.formatDate(inv.issue_date)}</td>
            <td class="text-danger fw-semibold">${this.formatDate(inv.due_date)}</td>
            <td class="fw-medium">${this.formatCurrency(inv.total_amount)}</td>
            <td class="fw-bold text-danger">${this.formatCurrency(inv.amount_due)}</td>
            <td>
              <span class="badge bg-danger-subtle text-danger border border-danger-subtle font-mono small">
                ${days} day${days === 1 ? '' : 's'}
              </span>
            </td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-primary py-1 px-2" onclick="dashboard.openInvoiceModal(${inv.id})">
                <i class="bi bi-eye me-1"></i> View
              </button>
            </td>
          </tr>
        `;
      }).join('');

      this.renderPagination(
        'overduePaginationContainer',
        this.state.overduePage,
        paginatedData.next,
        paginatedData.previous,
        totalCount,
        items.length,
        (newPage) => {
          this.state.overduePage = newPage;
          this.loadDashboardData();
        }
      );
    },

    // ==========================================
    // 5. PAYMENTS TABLE
    // ==========================================

    renderPaymentsTable(paginatedData) {
      const tbody = document.getElementById('paymentsTableBody');
      const countBadge = document.getElementById('paymentsCountBadge');
      const paginationContainer = document.getElementById('paymentsPaginationContainer');

      if (!tbody) return;

      const items = paginatedData ? (paginatedData.results || paginatedData) : [];
      const totalCount = paginatedData && paginatedData.count !== undefined ? paginatedData.count : items.length;

      if (countBadge) countBadge.textContent = `${totalCount} Payments`;

      if (items.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">No payments recorded.</td></tr>`;
        if (paginationContainer) paginationContainer.classList.add('d-none');
        return;
      }

      tbody.innerHTML = items.map(pay => {
        const cust = pay.customer_name || pay.customer_email || `Customer #${pay.customer_id}`;
        const method = (pay.method || '').toLowerCase().replace(/_/g, ' ');

        return `
          <tr>
            <td class="font-mono text-muted small">#${pay.id}</td>
            <td class="fw-semibold text-navy font-mono">
              <a href="javascript:void(0)" class="auth-link" onclick="dashboard.openInvoiceModal(${pay.invoice})">${pay.invoice_number}</a>
            </td>
            <td>
              <div class="fw-medium text-slate-800 text-truncate" style="max-width: 170px;">${cust}</div>
              <div class="text-muted font-mono" style="font-size: 0.725rem;">${pay.customer_email || ''}</div>
            </td>
            <td>
              <span class="badge bg-light text-slate-700 border text-capitalize font-mono">
                ${method}
              </span>
            </td>
            <td class="fw-bold text-success">${this.formatCurrency(pay.amount)}</td>
            <td class="text-slate-600">${this.formatDateTime(pay.payment_date)}</td>
            <td>
              <span class="badge bg-success-subtle text-success border border-success-subtle font-mono small">
                <i class="bi bi-check2 me-1"></i> Settled
              </span>
            </td>
          </tr>
        `;
      }).join('');

      this.renderPagination(
        'paymentsPaginationContainer',
        this.state.paymentsPage,
        paginatedData.next,
        paginatedData.previous,
        totalCount,
        items.length,
        (newPage) => {
          this.state.paymentsPage = newPage;
          this.loadDashboardData();
        }
      );
    },

    // ==========================================
    // 6. PAGINATION CONTROLLER
    // ==========================================

    renderPagination(containerId, currentPage, hasNext, hasPrev, totalCount, currentCount, onPageChange) {
      const container = document.getElementById(containerId);
      if (!container) return;

      if (!hasNext && !hasPrev && totalCount <= 20) {
        container.classList.add('d-none');
        return;
      }
      container.classList.remove('d-none');

      container.innerHTML = `
        <div class="d-flex flex-column flex-sm-row align-items-center justify-content-between gap-2 py-3 px-3 border-top border-slate-200">
          <div class="text-muted small">
            Page <span class="fw-semibold text-navy">${currentPage}</span> &bull; Total records: <span class="fw-semibold text-navy">${totalCount}</span>
          </div>
          <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-secondary ${!hasPrev ? 'disabled' : ''}" id="${containerId}_prev">
              <i class="bi bi-chevron-left me-1"></i> Previous
            </button>
            <button class="btn btn-outline-secondary ${!hasNext ? 'disabled' : ''}" id="${containerId}_next">
              Next <i class="bi bi-chevron-right ms-1"></i>
            </button>
          </div>
        </div>
      `;

      const prevBtn = document.getElementById(`${containerId}_prev`);
      const nextBtn = document.getElementById(`${containerId}_next`);

      if (prevBtn && hasPrev) {
        prevBtn.onclick = () => onPageChange(currentPage - 1);
      }
      if (nextBtn && hasNext) {
        nextBtn.onclick = () => onPageChange(currentPage + 1);
      }
    },

    // ==========================================
    // 7. CHART.JS VISUALIZATIONS
    // ==========================================

    renderCharts(overviewData, paymentsData, subscriptionsData) {
      if (!window.Chart) {
        console.warn('Chart.js library not loaded');
        return;
      }

      // Chart 1: Revenue Over Time
      this.renderRevenueChart(paymentsData);

      // Chart 2: Subscription Status Distribution
      this.renderSubscriptionStatusChart(overviewData, subscriptionsData);

      // Chart 3: Payment Method Breakdown
      this.renderPaymentMethodChart(paymentsData);
    },

    renderRevenueChart(paymentsData) {
      const ctx = document.getElementById('chartRevenueOverTime');
      if (!ctx) return;

      const items = paymentsData ? (paymentsData.results || paymentsData) : [];
      if (!Array.isArray(items) || items.length === 0) return;

      // Group payments by month
      const monthBuckets = {};
      items.forEach(p => {
        if (!p.payment_date) return;
        const d = new Date(p.payment_date);
        const key = d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
        monthBuckets[key] = (monthBuckets[key] || 0) + parseFloat(p.amount || 0);
      });

      const labels = Object.keys(monthBuckets);
      const data = Object.values(monthBuckets);

      if (this.state.charts.revenueChart) {
        this.state.charts.revenueChart.destroy();
      }

      this.state.charts.revenueChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels.length > 0 ? labels : ['Current Period'],
          datasets: [{
            label: 'Revenue ($)',
            data: data.length > 0 ? data : [0],
            borderColor: '#2563eb',
            backgroundColor: 'rgba(37, 99, 235, 0.08)',
            borderWidth: 2.5,
            fill: true,
            tension: 0.35,
            pointBackgroundColor: '#1d4ed8',
            pointRadius: 4,
            pointHoverRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => ` Revenue: $${Number(ctx.raw).toLocaleString(undefined, {minimumFractionDigits: 2})}`
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              grid: { color: '#f1f5f9' },
              ticks: {
                callback: (val) => `$${val >= 1000 ? (val / 1000) + 'k' : val}`
              }
            },
            x: {
              grid: { display: false }
            }
          }
        }
      });
    },

    renderSubscriptionStatusChart(overviewData, subscriptionsData) {
      const ctx = document.getElementById('chartSubStatus');
      if (!ctx) return;

      const statusCounts = {
        ACTIVE: 0,
        CONFIRMED: 0,
        DRAFT: 0,
        PAUSED: 0,
        CLOSED: 0
      };

      if (Array.isArray(subscriptionsData) && subscriptionsData.length > 0) {
        subscriptionsData.forEach(s => {
          const st = s.status || 'ACTIVE';
          statusCounts[st] = (statusCounts[st] || 0) + 1;
        });
      } else if (overviewData) {
        statusCounts.ACTIVE = overviewData.active_subscription_count || 1;
      }

      if (this.state.charts.subStatusChart) {
        this.state.charts.subStatusChart.destroy();
      }

      this.state.charts.subStatusChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: ['Active', 'Confirmed', 'Draft', 'Paused', 'Closed'],
          datasets: [{
            data: [
              statusCounts.ACTIVE,
              statusCounts.CONFIRMED,
              statusCounts.DRAFT,
              statusCounts.PAUSED,
              statusCounts.CLOSED
            ],
            backgroundColor: [
              '#10b981', // Emerald
              '#3b82f6', // Blue
              '#94a3b8', // Slate
              '#f59e0b', // Amber
              '#64748b'  // Dark slate
            ],
            borderWidth: 2,
            borderColor: '#ffffff'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'bottom',
              labels: { boxWidth: 12, font: { size: 11 } }
            }
          },
          cutout: '68%'
        }
      });
    },

    renderPaymentMethodChart(paymentsData) {
      const ctx = document.getElementById('chartPaymentMethods');
      if (!ctx) return;

      const items = paymentsData ? (paymentsData.results || paymentsData) : [];
      const methodTotals = {
        'Bank Transfer': 0,
        'Credit Card': 0,
        'Cash': 0,
        'Other': 0
      };

      items.forEach(p => {
        const amt = parseFloat(p.amount || 0);
        if (p.method === 'BANK_TRANSFER') methodTotals['Bank Transfer'] += amt;
        else if (p.method === 'CREDIT_CARD') methodTotals['Credit Card'] += amt;
        else if (p.method === 'CASH') methodTotals['Cash'] += amt;
        else methodTotals['Other'] += amt;
      });

      if (this.state.charts.paymentMethodChart) {
        this.state.charts.paymentMethodChart.destroy();
      }

      this.state.charts.paymentMethodChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels: Object.keys(methodTotals),
          datasets: [{
            label: 'Amount ($)',
            data: Object.values(methodTotals),
            backgroundColor: ['#2563eb', '#10b981', '#f59e0b', '#64748b'],
            borderRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => ` Total: $${Number(ctx.raw).toLocaleString(undefined, {minimumFractionDigits: 2})}`
              }
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              grid: { color: '#f1f5f9' },
              ticks: {
                callback: (val) => `$${val >= 1000 ? (val / 1000) + 'k' : val}`
              }
            },
            x: {
              grid: { display: false }
            }
          }
        }
      });
    },

    // ==========================================
    // 8. INVOICE DETAIL MODAL & PDF ACTION
    // ==========================================

    async openInvoiceModal(invId) {
      try {
        window.api.showLoading('Loading invoice statement...');
        const inv = await window.api.get(`/api/invoices/${invId}/`);

        setText('dashModalInvNumber', inv.invoice_number);
        setHtml('dashModalInvStatus', this.formatStatusBadge(inv.status, inv.is_overdue));

        setText('dashModalInvCustName', inv.customer_name || 'Customer');
        setText('dashModalInvCustEmail', inv.customer_email || '');

        setText('dashModalInvIssueDate', this.formatDate(inv.issue_date));
        setText('dashModalInvDueDate', this.formatDate(inv.due_date));
        setText('dashModalInvSubNumber', inv.subscription_number || 'Direct Order');

        // Lines
        const linesTbody = document.getElementById('dashModalInvLinesTbody');
        if (linesTbody) {
          const lines = inv.lines || [];
          linesTbody.innerHTML = lines.map(line => `
            <tr>
              <td>${line.description || line.product_name || 'Item'}</td>
              <td class="text-center">${line.quantity}</td>
              <td>${this.formatCurrency(line.unit_price)}</td>
              <td>${this.formatCurrency(line.subtotal)}</td>
              <td>${parseFloat(line.tax_rate || 0)}%</td>
              <td class="text-end fw-semibold">${this.formatCurrency(line.total)}</td>
            </tr>
          `).join('');
        }

        // Totals
        setText('dashModalInvSubtotal', this.formatCurrency(inv.subtotal));
        setText('dashModalInvTax', this.formatCurrency(inv.tax_amount));
        setText('dashModalInvGrandTotal', this.formatCurrency(inv.total_amount));
        setText('dashModalInvPaid', this.formatCurrency(inv.amount_paid));
        setText('dashModalInvDue', this.formatCurrency(inv.amount_due));

        // Buttons
        const btnPrint = document.getElementById('dashBtnModalPrint');
        const btnDownload = document.getElementById('dashBtnModalDownloadPdf');
        const btnConfirm = document.getElementById('dashBtnModalConfirm');
        const btnPay = document.getElementById('dashBtnModalPay');
        const btnCancel = document.getElementById('dashBtnModalCancel');

        if (btnPrint) btnPrint.onclick = () => window.print();
        if (btnDownload) btnDownload.onclick = () => this.downloadInvoicePdf(inv.id, inv.invoice_number);

        // Status Actions inside Invoice Modal
        const status = (inv.status || '').toUpperCase();
        const due = parseFloat(inv.amount_due || 0);

        if (btnConfirm) {
          if (status === 'DRAFT') {
            btnConfirm.classList.remove('d-none');
            btnConfirm.onclick = () => {
              bootstrap.Modal.getInstance(document.getElementById('dashInvoiceDetailModal')).hide();
              this.confirmInvoice(inv.id);
            };
          } else {
            btnConfirm.classList.add('d-none');
          }
        }

        if (btnPay) {
          if ((status === 'CONFIRMED' || status === 'SENT') && due > 0) {
            btnPay.classList.remove('d-none');
            btnPay.onclick = () => {
              bootstrap.Modal.getInstance(document.getElementById('dashInvoiceDetailModal')).hide();
              this.openRecordPaymentModal(inv.id);
            };
          } else {
            btnPay.classList.add('d-none');
          }
        }

        if (btnCancel) {
          if (status === 'DRAFT' || status === 'CONFIRMED') {
            btnCancel.classList.remove('d-none');
            btnCancel.onclick = () => {
              bootstrap.Modal.getInstance(document.getElementById('dashInvoiceDetailModal')).hide();
              this.cancelInvoice(inv.id);
            };
          } else {
            btnCancel.classList.add('d-none');
          }
        }

        const modalEl = document.getElementById('dashInvoiceDetailModal');
        if (modalEl && window.bootstrap) {
          const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
          modal.show();
        }

      } catch (err) {
        console.error('Invoice modal error:', err);
        window.api.showToast(err.message || 'Error opening invoice.', 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    // ==========================================
    // 8B. SUBSCRIPTIONS MANAGEMENT (MVP 2)
    // ==========================================

    renderSubscriptionsTable() {
      const tbody = document.getElementById('subscriptionsTableBody');
      const badge = document.getElementById('subsCountBadge');
      if (!tbody) return;

      const { subFilterStatus, subSearch, subsPage } = this.state;
      const pageSize = 10;

      let filtered = (this.state.subscriptions || []).filter(sub => {
        const matchesStatus = (subFilterStatus === 'ALL') || (sub.status === subFilterStatus);
        const matchesSearch = !subSearch ||
          (sub.subscription_number && sub.subscription_number.toLowerCase().includes(subSearch)) ||
          (sub.customer_email && sub.customer_email.toLowerCase().includes(subSearch)) ||
          (sub.plan_name && sub.plan_name.toLowerCase().includes(subSearch));
        return matchesStatus && matchesSearch;
      });

      if (badge) badge.textContent = `${filtered.length} Subscriptions`;

      if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No subscriptions matching criteria.</td></tr>`;
        const pag = document.getElementById('subscriptionsPaginationContainer');
        if (pag) pag.innerHTML = '';
        return;
      }

      const totalPages = Math.ceil(filtered.length / pageSize) || 1;
      const currentPage = Math.min(Math.max(1, subsPage), totalPages);
      this.state.subsPage = currentPage;

      const startIndex = (currentPage - 1) * pageSize;
      const pageItems = filtered.slice(startIndex, startIndex + pageSize);

      tbody.innerHTML = pageItems.map(sub => {
        const total = parseFloat(sub.total_amount || 0);
        const statusBadge = this.formatStatusBadge(sub.status);

        return `
          <tr>
            <td>
              <span class="fw-bold font-mono text-navy">${sub.subscription_number}</span>
            </td>
            <td>
              <div class="fw-semibold text-slate-800 small">${sub.customer_email || 'Customer'}</div>
              <small class="text-muted font-mono">ID #${sub.customer}</small>
            </td>
            <td>
              <span class="fw-medium text-navy">${sub.plan_name || 'Standard Plan'}</span>
              <span class="badge bg-light text-muted border font-mono ms-1 small">${sub.plan_billing_period || 'MONTHLY'}</span>
            </td>
            <td class="font-mono fw-bold text-slate-900">${this.formatCurrency(total)}</td>
            <td class="text-slate-600 small">${this.formatDate(sub.start_date)}</td>
            <td class="font-mono small text-primary">${this.formatDate(sub.next_billing_date)}</td>
            <td>${statusBadge}</td>
            <td class="text-end text-nowrap">
              <button class="btn btn-sm btn-outline-primary py-1 px-2" onclick="dashboard.openSubscriptionDetailModal(${sub.id})" title="View Details & Transitions">
                <i class="bi bi-gear-fill me-1"></i> Manage
              </button>
            </td>
          </tr>
        `;
      }).join('');

      this.renderCustomPagination(
        'subscriptionsPaginationContainer',
        currentPage,
        totalPages,
        filtered.length,
        startIndex,
        pageItems.length,
        (newPage) => {
          this.state.subsPage = newPage;
          this.renderSubscriptionsTable();
        }
      );
    },

    openCreateSubscriptionModal() {
      // 1. Populate Customer Dropdown
      const custSelect = document.getElementById('subCustomerSelect');
      if (custSelect) {
        custSelect.innerHTML = '<option value="">-- Choose Customer --</option>' +
          this.state.customers.map(c => `<option value="${c.id}">${c.email} (ID #${c.id})</option>`).join('');
      }

      // 2. Populate Plan Dropdown
      const planSelect = document.getElementById('subPlanSelect');
      if (planSelect) {
        planSelect.innerHTML = '<option value="">-- Choose Billing Plan --</option>' +
          this.state.plans.map(p => `<option value="${p.id}">${p.name} - ${p.billing_period} ($${p.price})</option>`).join('');
      }

      // 3. Set Defaults
      const today = new Date().toISOString().split('T')[0];
      setVal('subStartDate', today);
      setVal('subPaymentTerms', '30');
      setVal('subExpiryDate', '');

      // 4. Reset Line items container with 1 row
      const container = document.getElementById('subLinesContainer');
      if (container) {
        container.innerHTML = '';
        this.addSubLineRow();
      }

      const modalEl = document.getElementById('createSubscriptionModal');
      if (modalEl && window.bootstrap) {
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
      }
    },

    addSubLineRow() {
      const container = document.getElementById('subLinesContainer');
      if (!container) return;

      const rowId = `sub_line_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
      const prods = this.state.products || [];

      const prodOptions = prods.map(p => `<option value="${p.id}" data-price="${p.sales_price}">${p.name} ($${p.sales_price})</option>`).join('');

      const html = `
        <div class="d-flex align-items-center gap-2 p-2 bg-white rounded-2 border mb-2 sub-line-row" id="${rowId}">
          <div style="flex: 4;">
            <select class="form-select form-select-sm line-prod-select" onchange="dashboard.handleLineProductChange('${rowId}')" required>
              <option value="">-- Select Product --</option>
              ${prodOptions}
            </select>
          </div>
          <div style="flex: 4;">
            <select class="form-select form-select-sm line-var-select">
              <option value="">Base / No Variant</option>
            </select>
          </div>
          <div style="flex: 2;">
            <input type="number" min="1" value="1" class="form-control form-control-sm line-qty" placeholder="Qty" required>
          </div>
          <button type="button" class="btn btn-outline-danger btn-sm px-2" onclick="document.getElementById('${rowId}').remove()">
            <i class="bi bi-trash"></i>
          </button>
        </div>
      `;
      container.insertAdjacentHTML('beforeend', html);
    },

    handleLineProductChange(rowId) {
      const row = document.getElementById(rowId);
      if (!row) return;

      const prodId = parseInt(row.querySelector('.line-prod-select').value);
      const varSelect = row.querySelector('.line-var-select');
      varSelect.innerHTML = '<option value="">Base / No Variant</option>';

      if (!prodId) return;
      const product = this.state.products.find(p => p.id === prodId);
      if (product && product.variants && product.variants.length > 0) {
        product.variants.forEach(v => {
          const extra = parseFloat(v.price_extra || 0);
          varSelect.innerHTML += `<option value="${v.id}">${v.attribute_value} (+${dashboard.formatCurrency(extra)})</option>`;
        });
      }
    },

    async createSubscription() {
      const customer = document.getElementById('subCustomerSelect').value;
      const plan = document.getElementById('subPlanSelect').value;
      const start_date = document.getElementById('subStartDate').value;
      const expiry_date = document.getElementById('subExpiryDate').value || null;
      const payment_terms_days = parseInt(document.getElementById('subPaymentTerms').value) || 30;

      if (!customer || !plan) {
        window.api.showToast('Please select both a Customer and a Plan.', 'error');
        return;
      }

      // Collect lines
      const lineRows = document.querySelectorAll('#subLinesContainer .sub-line-row');
      const lines = [];
      for (const row of lineRows) {
        const product = row.querySelector('.line-prod-select').value;
        const variant = row.querySelector('.line-var-select').value || null;
        const quantity = parseInt(row.querySelector('.line-qty').value) || 1;

        if (product) {
          const item = { product: parseInt(product), quantity };
          if (variant) item.variant = parseInt(variant);
          lines.push(item);
        }
      }

      if (lines.length === 0) {
        window.api.showToast('Please add at least one product line item.', 'error');
        return;
      }

      const payload = {
        customer: parseInt(customer),
        plan: parseInt(plan),
        start_date: start_date || new Date().toISOString().split('T')[0],
        payment_terms_days,
        status: 'DRAFT',
        lines
      };
      if (expiry_date) payload.expiry_date = expiry_date;

      try {
        window.api.showLoading('Creating subscription contract...');
        const res = await window.api.post('/api/subscriptions/', payload);
        window.api.showToast(`Subscription ${res.subscription_number} created successfully!`, 'success');

        const modalEl = document.getElementById('createSubscriptionModal');
        if (modalEl && window.bootstrap) {
          bootstrap.Modal.getInstance(modalEl).hide();
        }

        await this.loadDashboardData();
      } catch (err) {
        console.error('Create subscription error:', err);
        window.api.showToast(window.api.formatError(err.data) || err.message, 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    async openSubscriptionDetailModal(subId) {
      try {
        window.api.showLoading('Loading subscription contract...');
        const sub = await window.api.get(`/api/subscriptions/${subId}/`);

        setText('subDetailNumber', sub.subscription_number);
        setHtml('subDetailStatusBadge', this.formatStatusBadge(sub.status));
        setText('subDetailCustomer', sub.customer_email || `ID #${sub.customer}`);
        setText('subDetailPlan', sub.plan_name || 'Standard Plan');
        setText('subDetailCadence', `Cadence: ${sub.plan_billing_period || 'MONTHLY'}`);
        setText('subDetailStart', this.formatDate(sub.start_date));
        setText('subDetailNextBill', this.formatDate(sub.next_billing_date));

        // Lines table
        const tbody = document.getElementById('subDetailLinesTbody');
        if (tbody) {
          const lines = sub.lines || [];
          tbody.innerHTML = lines.map(l => `
            <tr>
              <td>
                <div class="fw-semibold text-navy">${l.product_name || 'Product'}</div>
                ${l.variant_name ? `<small class="text-muted font-mono">${l.variant_name}</small>` : ''}
              </td>
              <td class="text-center">${l.quantity}</td>
              <td class="font-mono">${this.formatCurrency(l.unit_price)}</td>
              <td class="text-end font-mono fw-bold">${this.formatCurrency(l.subtotal)}</td>
            </tr>
          `).join('');
        }

        setText('subDetailTotal', this.formatCurrency(sub.total_amount || 0));

        // Inject Dynamic Lifecycle Transition Buttons
        const actionGroup = document.getElementById('subDetailActionGroup');
        if (actionGroup) {
          const st = (sub.status || '').toUpperCase();
          let buttonsHtml = '';

          if (st === 'DRAFT') {
            buttonsHtml += `
              <button class="btn btn-outline-primary btn-sm" onclick="dashboard.transitionSubscription(${sub.id}, 'QUOTATION')">
                <i class="bi bi-file-earmark-text me-1"></i> Move to Quotation
              </button>
              <button class="btn btn-outline-danger btn-sm" onclick="dashboard.transitionSubscription(${sub.id}, 'CLOSED')">
                <i class="bi bi-x-circle me-1"></i> Close
              </button>
            `;
          } else if (st === 'QUOTATION') {
            buttonsHtml += `
              <button class="btn btn-primary btn-sm" onclick="dashboard.transitionSubscription(${sub.id}, 'CONFIRMED')">
                <i class="bi bi-check-circle me-1"></i> Confirm Subscription
              </button>
              <button class="btn btn-outline-danger btn-sm" onclick="dashboard.transitionSubscription(${sub.id}, 'CLOSED')">
                <i class="bi bi-x-circle me-1"></i> Close
              </button>
            `;
          } else if (st === 'CONFIRMED') {
            buttonsHtml += `
              <button class="btn btn-success btn-sm" onclick="dashboard.transitionSubscription(${sub.id}, 'ACTIVE')">
                <i class="bi bi-play-circle me-1"></i> Activate Subscription
              </button>
              <button class="btn btn-outline-danger btn-sm" onclick="dashboard.transitionSubscription(${sub.id}, 'CLOSED')">
                <i class="bi bi-x-circle me-1"></i> Close
              </button>
            `;
          } else if (st === 'ACTIVE') {
            buttonsHtml += `
              <button class="btn btn-warning btn-sm" onclick="dashboard.transitionSubscription(${sub.id}, 'PAUSED')">
                <i class="bi bi-pause-circle me-1"></i> Pause Subscription
              </button>
              <button class="btn btn-danger btn-sm" onclick="dashboard.transitionSubscription(${sub.id}, 'CLOSED')">
                <i class="bi bi-x-circle me-1"></i> Close Subscription
              </button>
            `;
          } else if (st === 'PAUSED') {
            buttonsHtml += `
              <button class="btn btn-success btn-sm" onclick="dashboard.transitionSubscription(${sub.id}, 'ACTIVE')">
                <i class="bi bi-play-circle me-1"></i> Resume (Activate)
              </button>
              <button class="btn btn-danger btn-sm" onclick="dashboard.transitionSubscription(${sub.id}, 'CLOSED')">
                <i class="bi bi-x-circle me-1"></i> Close Subscription
              </button>
            `;
          }
          actionGroup.innerHTML = buttonsHtml;
        }

        const modalEl = document.getElementById('subscriptionDetailModal');
        if (modalEl && window.bootstrap) {
          bootstrap.Modal.getOrCreateInstance(modalEl).show();
        }

      } catch (err) {
        console.error('Subscription details error:', err);
        window.api.showToast(err.message || 'Error opening subscription.', 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    async transitionSubscription(subId, targetStatus) {
      try {
        window.api.showLoading(`Transitioning subscription to ${targetStatus}...`);
        await window.api.post(`/api/subscriptions/${subId}/transition/`, { status: targetStatus });
        window.api.showToast(`Subscription status updated to ${targetStatus}!`, 'success');

        const modalEl = document.getElementById('subscriptionDetailModal');
        if (modalEl && window.bootstrap) {
          const inst = bootstrap.Modal.getInstance(modalEl);
          if (inst) inst.hide();
        }

        await this.loadDashboardData();
      } catch (err) {
        console.error('Subscription transition error:', err);
        window.api.showToast(window.api.formatError(err.data) || err.message, 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    // ==========================================
    // 8C. ALL INVOICES & PAYMENTS HUB (MVP 3)
    // ==========================================

    renderAllInvoicesTable() {
      const tbody = document.getElementById('allInvoicesTableBody');
      if (!tbody) return;

      const { invSearch, allInvsPage } = this.state;
      const pageSize = 10;

      let filtered = (this.state.allInvoices || []).filter(inv => {
        const matchesSearch = !invSearch ||
          (inv.invoice_number && inv.invoice_number.toLowerCase().includes(invSearch)) ||
          (inv.customer_email && inv.customer_email.toLowerCase().includes(invSearch)) ||
          (inv.status && inv.status.toLowerCase().includes(invSearch));
        return matchesSearch;
      });

      if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-4">No invoices recorded in database.</td></tr>`;
        const pag = document.getElementById('allInvoicesPaginationContainer');
        if (pag) pag.innerHTML = '';
        return;
      }

      const totalPages = Math.ceil(filtered.length / pageSize) || 1;
      const currentPage = Math.min(Math.max(1, allInvsPage), totalPages);
      this.state.allInvsPage = currentPage;

      const startIndex = (currentPage - 1) * pageSize;
      const pageItems = filtered.slice(startIndex, startIndex + pageSize);

      tbody.innerHTML = pageItems.map(inv => {
        const total = parseFloat(inv.total_amount || 0);
        const paid = parseFloat(inv.amount_paid || 0);
        const due = parseFloat(inv.amount_due || 0);
        const statusBadge = this.formatStatusBadge(inv.status, inv.is_overdue);

        const isDraft = inv.status === 'DRAFT';
        const isPayable = (inv.status === 'CONFIRMED' || inv.status === 'SENT') && due > 0;

        return `
          <tr>
            <td>
              <span class="fw-bold font-mono text-navy">${inv.invoice_number}</span>
            </td>
            <td>
              <div class="fw-semibold text-slate-800 small">${inv.customer_email || 'Customer'}</div>
            </td>
            <td class="text-slate-600 small">${this.formatDate(inv.issue_date)}</td>
            <td class="font-mono small ${inv.is_overdue ? 'text-danger fw-bold' : 'text-slate-600'}">${this.formatDate(inv.due_date)}</td>
            <td class="font-mono fw-bold text-slate-900">${this.formatCurrency(total)}</td>
            <td class="font-mono text-success">${this.formatCurrency(paid)}</td>
            <td class="font-mono fw-bold ${due > 0 ? 'text-danger' : 'text-slate-500'}">${this.formatCurrency(due)}</td>
            <td>${statusBadge}</td>
            <td class="text-end text-nowrap">
              <button class="btn btn-sm btn-outline-primary py-1 px-2 me-1" onclick="dashboard.openInvoiceModal(${inv.id})" title="View Details">
                <i class="bi bi-eye"></i>
              </button>
              ${isDraft ? `
                <button class="btn btn-sm btn-outline-success py-1 px-2 me-1" onclick="dashboard.confirmInvoice(${inv.id})" title="Confirm Invoice">
                  <i class="bi bi-check-circle"></i>
                </button>
              ` : ''}
              ${isPayable ? `
                <button class="btn btn-sm btn-success py-1 px-2 me-1" onclick="dashboard.openRecordPaymentModal(${inv.id})" title="Record Payment">
                  <i class="bi bi-cash-stack"></i>
                </button>
              ` : ''}
              <button class="btn btn-sm btn-outline-secondary py-1 px-2" onclick="dashboard.downloadInvoicePdf(${inv.id}, '${inv.invoice_number}')" title="Download PDF">
                <i class="bi bi-download"></i>
              </button>
            </td>
          </tr>
        `;
      }).join('');

      this.renderCustomPagination(
        'allInvoicesPaginationContainer',
        currentPage,
        totalPages,
        filtered.length,
        startIndex,
        pageItems.length,
        (newPage) => {
          this.state.allInvsPage = newPage;
          this.renderAllInvoicesTable();
        }
      );
    },

    async confirmInvoice(invId) {
      try {
        window.api.showLoading('Confirming invoice...');
        await window.api.post(`/api/invoices/${invId}/confirm/`);
        window.api.showToast('Invoice confirmed successfully!', 'success');
        await this.loadDashboardData();
      } catch (err) {
        console.error('Confirm invoice error:', err);
        window.api.showToast(window.api.formatError(err.data) || err.message, 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    async cancelInvoice(invId) {
      if (!confirm('Are you sure you want to cancel this invoice?')) return;
      try {
        window.api.showLoading('Cancelling invoice...');
        await window.api.post(`/api/invoices/${invId}/cancel/`);
        window.api.showToast('Invoice cancelled.', 'success');
        await this.loadDashboardData();
      } catch (err) {
        console.error('Cancel invoice error:', err);
        window.api.showToast(window.api.formatError(err.data) || err.message, 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    openRecordPaymentModal(invId) {
      const inv = this.state.allInvoices.find(i => i.id === invId) ||
                  (this.state.overdueInvoices.results || this.state.overdueInvoices || []).find(i => i.id === invId);
      if (!inv) return;

      setVal('payInvoiceId', inv.id);
      setText('payModalInvNumber', inv.invoice_number);
      setText('payModalCustomer', inv.customer_email || 'Customer');
      setText('payModalAmountDue', this.formatCurrency(inv.amount_due));
      setVal('payAmountInput', inv.amount_due);
      setVal('payNotesInput', '');

      const modalEl = document.getElementById('recordPaymentModal');
      if (modalEl && window.bootstrap) {
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
      }
    },

    async recordPayment() {
      const invId = document.getElementById('payInvoiceId').value;
      const amount = document.getElementById('payAmountInput').value;
      const payment_method = document.getElementById('payMethodSelect').value;
      const notes = document.getElementById('payNotesInput').value.trim();

      if (!amount || parseFloat(amount) <= 0) {
        window.api.showToast('Please enter a valid payment amount.', 'error');
        return;
      }

      try {
        window.api.showLoading('Logging payment settlement...');
        await window.api.post(`/api/invoices/${invId}/pay/`, {
          amount,
          method: payment_method,
          note: notes,
          transaction_reference: notes
        });
        window.api.showToast('Payment settled and recorded successfully!', 'success');

        const modalEl = document.getElementById('recordPaymentModal');
        if (modalEl && window.bootstrap) {
          bootstrap.Modal.getInstance(modalEl).hide();
        }

        await this.loadDashboardData();
      } catch (err) {
        console.error('Payment settlement error:', err);
        window.api.showToast(window.api.formatError(err.data) || err.message, 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    renderCustomPagination(containerId, currentPage, totalPages, totalItems, startIndex, countOnPage, onSelect) {
      const container = document.getElementById(containerId);
      if (!container) return;

      if (totalItems <= 10) {
        container.innerHTML = '';
        return;
      }

      const start = startIndex + 1;
      const end = startIndex + countOnPage;

      container.innerHTML = `
        <div class="d-flex flex-column flex-sm-row align-items-center justify-content-between gap-2 py-3 border-top border-slate-200">
          <div class="text-muted small">
            Showing <span class="fw-semibold text-navy">${start}</span> to <span class="fw-semibold text-navy">${end}</span> of <span class="fw-semibold text-navy">${totalItems}</span> items
          </div>
          <nav>
            <ul class="pagination pagination-sm mb-0">
              <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                <button type="button" class="page-link" ${currentPage === 1 ? 'disabled' : ''} id="${containerId}_prev">Previous</button>
              </li>
              <li class="page-item active">
                <span class="page-link">${currentPage} / ${totalPages}</span>
              </li>
              <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                <button type="button" class="page-link" ${currentPage === totalPages ? 'disabled' : ''} id="${containerId}_next">Next</button>
              </li>
            </ul>
          </nav>
        </div>
      `;

      const prevBtn = document.getElementById(`${containerId}_prev`);
      const nextBtn = document.getElementById(`${containerId}_next`);
      if (prevBtn && currentPage > 1) {
        prevBtn.onclick = () => onSelect(currentPage - 1);
      }
      if (nextBtn && currentPage < totalPages) {
        nextBtn.onclick = () => onSelect(currentPage + 1);
      }
    },

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
        console.error('PDF error:', err);
        window.api.showToast('Could not download PDF invoice.', 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    // ==========================================
    // 9. FORMATTING HELPERS
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

    formatDateTime(dateStr) {
      if (!dateStr) return '-';
      try {
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        return d.toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          year: 'numeric'
        }) + ' ' + d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
      } catch (e) {
        return dateStr;
      }
    },

    formatStatusBadge(statusVal, isOverdue = false) {
      if (!statusVal) return '';
      const s = String(statusVal).toUpperCase();

      if (isOverdue) {
        return `<span class="badge bg-danger-subtle text-danger border border-danger-subtle font-mono small"><i class="bi bi-exclamation-triangle-fill me-1"></i> OVERDUE</span>`;
      }

      const map = {
        ACTIVE: 'bg-success-subtle text-success border border-success-subtle',
        CONFIRMED: 'bg-primary-subtle text-primary border border-primary-subtle',
        PAID: 'bg-success-subtle text-success border border-success-subtle',
        DRAFT: 'bg-light text-slate-700 border',
        QUOTATION: 'bg-info-subtle text-info border border-info-subtle',
        PAUSED: 'bg-warning-subtle text-warning-emphasis border border-warning-subtle',
        CLOSED: 'bg-light text-muted border',
        CANCELLED: 'bg-danger-subtle text-danger border border-danger-subtle'
      };

      return `<span class="badge ${map[s] || 'bg-light text-dark border'} font-mono small">${s}</span>`;
    }
  };

  window.dashboard = dashboard;
  document.addEventListener('DOMContentLoaded', () => dashboard.init());
})();

