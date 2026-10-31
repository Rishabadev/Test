/**
 * Brightloop Software - Products & Variant Management Controller (Admin Only)
 * Handles full Product CRUD, nested and standalone Variant CRUD,
 * Tax Rules configuration, live search, filtering, and pagination.
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

  const products = {
    state: {
      currentUser: null,
      products: [],
      plans: [],
      discounts: [],
      taxRules: [],
      activeProduct: null,
      editingVariantId: null,
      editingTaxRuleId: null,
      editingPlanId: null,
      filters: {
        search: '',
        product_type: 'ALL',
        status: 'ALL',
        page: 1,
        pageSize: 10
      }
    },

    // ==========================================
    // 1. INITIALIZATION & STRICT ADMIN GUARD
    // ==========================================

    async init() {
      // 1. Check Authentication
      if (!window.api || !window.api.isAuthenticated()) {
        window.location.href = '/login/?expired=1';
        return;
      }

      this.setupDOMEventListeners();

      try {
        window.api.showLoading('Loading product catalog...');

        // 2. Fetch authenticated user profile
        const me = await window.api.get('/api/auth/me/');
        this.state.currentUser = me;

        const role = (me.role || '').toUpperCase();

        // STRICT SECURITY GUARD: Access is strictly ADMIN ONLY
        if (role !== 'ADMIN') {
          window.api.showToast('Access restricted: Product management requires administrator privileges.', 'error');
          setTimeout(() => {
            if (role === 'STAFF') {
              window.location.href = '/dashboard/';
            } else {
              window.location.href = '/portal/';
            }
          }, 800);
          return;
        }

        // Render user identity in topbar & sidebar
        this.renderAdminProfile(me);

        // 3. Load Products and Tax Rules
        await this.loadCatalogData();

      } catch (err) {
        console.error('Products init error:', err);
        if (err.status === 401 || err.status === 403) {
          window.api.onSessionExpired();
        } else {
          window.api.showToast(err.message || 'Error loading catalog data.', 'error');
        }
      } finally {
        window.api.hideLoading();
      }
    },

    renderAdminProfile(user) {
      const name = [user.first_name, user.last_name].filter(Boolean).join(' ') || 'Administrator';
      const initials = (user.first_name ? user.first_name[0] : (user.email ? user.email[0] : 'A')).toUpperCase();

      const topName = document.getElementById('prodTopUserName');
      const topEmail = document.getElementById('prodTopUserEmail');
      const topAvatar = document.getElementById('prodTopUserAvatar');
      const sideAvatar = document.getElementById('prodSidebarAvatar');

      if (topName) topName.textContent = name;
      if (topEmail) topEmail.textContent = user.email;
      if (topAvatar) topAvatar.textContent = initials;
      if (sideAvatar) sideAvatar.textContent = initials;
    },

    setupDOMEventListeners() {
      // Mobile sidebar toggle
      const sidebarToggle = document.getElementById('prodSidebarToggle');
      const sidebar = document.getElementById('dashSidebar');
      const backdrop = document.getElementById('prodSidebarBackdrop');

      if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', () => {
          sidebar.classList.toggle('show');
          if (backdrop) backdrop.classList.toggle('show');
        });
      }
      if (backdrop && sidebar) {
        backdrop.addEventListener('click', () => {
          sidebar.classList.remove('show');
          backdrop.classList.remove('show');
        });
      }

      // Search & Filter Inputs
      const searchInput = document.getElementById('prodSearchInput');
      const typeFilter = document.getElementById('prodTypeFilter');
      const statusFilter = document.getElementById('prodStatusFilter');
      const btnReset = document.getElementById('btnResetProdFilters');

      if (searchInput) {
        searchInput.addEventListener('input', () => {
          this.state.filters.search = searchInput.value.trim().toLowerCase();
          this.state.filters.page = 1;
          this.renderProductsTable();
        });
      }
      if (typeFilter) {
        typeFilter.addEventListener('change', () => {
          this.state.filters.product_type = typeFilter.value;
          this.state.filters.page = 1;
          this.renderProductsTable();
        });
      }
      if (statusFilter) {
        statusFilter.addEventListener('change', () => {
          this.state.filters.status = statusFilter.value;
          this.state.filters.page = 1;
          this.renderProductsTable();
        });
      }
      if (btnReset) {
        btnReset.addEventListener('click', () => {
          if (searchInput) searchInput.value = '';
          if (typeFilter) typeFilter.value = 'ALL';
          if (statusFilter) statusFilter.value = 'ALL';
          this.state.filters = { search: '', product_type: 'ALL', status: 'ALL', page: 1, pageSize: 10 };
          this.renderProductsTable();
        });
      }

      // Product Form Submission (Add/Edit)
      const productForm = document.getElementById('productForm');
      if (productForm) {
        productForm.addEventListener('submit', (e) => {
          e.preventDefault();
          this.saveProduct();
        });
      }

      // Add Inline Variant Row Button in Product Form
      const btnAddInlineVariant = document.getElementById('btnAddInlineVariant');
      if (btnAddInlineVariant) {
        btnAddInlineVariant.addEventListener('click', () => {
          this.addInlineVariantRow();
        });
      }

      // Variant Form Submission (Dedicated Variant Modal)
      const variantForm = document.getElementById('variantForm');
      if (variantForm) {
        variantForm.addEventListener('submit', (e) => {
          e.preventDefault();
          this.saveDedicatedVariant();
        });
      }

      // Tax Rule Form Submission
      const taxRuleForm = document.getElementById('taxRuleForm');
      if (taxRuleForm) {
        taxRuleForm.addEventListener('submit', (e) => {
          e.preventDefault();
          this.saveTaxRule();
        });
      }

      // Plan Form Submission
      const planForm = document.getElementById('planForm');
      if (planForm) {
        planForm.addEventListener('submit', (e) => {
          e.preventDefault();
          this.savePlan();
        });
      }

      // Discount Form Submission
      const discountForm = document.getElementById('discountForm');
      if (discountForm) {
        discountForm.addEventListener('submit', (e) => {
          e.preventDefault();
          this.saveDiscount();
        });
      }
    },

    switchTab(tabName) {
      const btn = document.getElementById(`tab-${tabName}-btn`);
      if (btn && window.bootstrap) {
        const tab = new bootstrap.Tab(btn);
        tab.show();
      }
    },

    // ==========================================
    // 2. DATA LOADING & SUMMARY METRICS
    // ==========================================

    async loadCatalogData() {
      try {
        const [productsRes, taxesRes, plansRes, discountsRes] = await Promise.all([
          window.api.get('/api/products/'),
          window.api.get('/api/tax-rules/'),
          window.api.get('/api/plans/').catch(() => []),
          window.api.get('/api/discounts/').catch(() => [])
        ]);

        this.state.products = Array.isArray(productsRes) ? productsRes : (productsRes.results || []);
        this.state.taxRules = Array.isArray(taxesRes) ? taxesRes : (taxesRes.results || []);
        this.state.plans = Array.isArray(plansRes) ? plansRes : (plansRes.results || []);
        this.state.discounts = Array.isArray(discountsRes) ? discountsRes : (discountsRes.results || []);

        this.renderCatalogSummary();
        this.renderProductsTable();
        this.renderPlansTable();
        this.renderDiscountsTable();
        this.renderTaxRulesTable();

      } catch (err) {
        console.error('Catalog load error:', err);
        window.api.showToast(err.message || 'Error loading products catalog.', 'error');
      }
    },

    renderCatalogSummary() {
      const prods = this.state.products;
      const taxes = this.state.taxRules;
      const plans = this.state.plans;

      const totalProds = prods.length;
      const activeProds = prods.filter(p => p.is_active).length;

      let totalVariants = 0;
      prods.forEach(p => {
        if (p.variants && Array.isArray(p.variants)) {
          totalVariants += p.variants.length;
        }
      });

      const activeTaxes = taxes.filter(t => t.is_active).length;

      const elTotal = document.getElementById('statTotalProducts');
      const elActive = document.getElementById('statActiveProducts');
      const elVariants = document.getElementById('statTotalVariants');
      const elTaxes = document.getElementById('statTotalTaxRules');
      const elPlans = document.getElementById('statTotalPlans');

      if (elTotal) elTotal.textContent = totalProds;
      if (elActive) elActive.textContent = activeProds;
      if (elVariants) elVariants.textContent = totalVariants;
      if (elTaxes) elTaxes.textContent = activeTaxes;
      if (elPlans) elPlans.textContent = plans.length;
    },

    // ==========================================
    // 3. PRODUCT TABLE RENDERING & FILTERING
    // ==========================================

    renderProductsTable() {
      const tbody = document.getElementById('productsTableBody');
      const emptyState = document.getElementById('productsEmptyState');
      const tableWrapper = document.getElementById('productsTableWrapper');
      const countBadge = document.getElementById('productsCountBadge');

      if (!tbody) return;

      const { search, product_type, status, page, pageSize } = this.state.filters;

      let filtered = this.state.products.filter(p => {
        const matchesSearch = !search ||
          (p.name && p.name.toLowerCase().includes(search)) ||
          (p.notes && p.notes.toLowerCase().includes(search));

        const matchesType = (product_type === 'ALL') || (p.product_type === product_type);

        let matchesStatus = true;
        if (status === 'ACTIVE') matchesStatus = !!p.is_active;
        else if (status === 'INACTIVE') matchesStatus = !p.is_active;

        return matchesSearch && matchesType && matchesStatus;
      });

      if (countBadge) countBadge.textContent = `${filtered.length} products`;

      if (filtered.length === 0) {
        if (tableWrapper) tableWrapper.classList.add('d-none');
        if (emptyState) emptyState.classList.remove('d-none');
        document.getElementById('productsPaginationContainer').classList.add('d-none');
        return;
      }

      if (tableWrapper) tableWrapper.classList.remove('d-none');
      if (emptyState) emptyState.classList.add('d-none');

      // Pagination
      const totalPages = Math.ceil(filtered.length / pageSize) || 1;
      const currentPage = Math.min(Math.max(1, page), totalPages);
      this.state.filters.page = currentPage;

      const startIndex = (currentPage - 1) * pageSize;
      const pageItems = filtered.slice(startIndex, startIndex + pageSize);

      tbody.innerHTML = pageItems.map(prod => {
        const variants = prod.variants || [];
        const variantHtml = variants.length === 0
          ? '<span class="text-muted small">No variants</span>'
          : variants.map(v => {
              const extra = parseFloat(v.price_extra || 0);
              const extraLabel = extra > 0 ? `+${this.formatCurrency(extra)}` : 'Base';
              return `<span class="variant-pill"><span>${v.attribute_value}</span><span class="badge-extra">(${extraLabel})</span></span>`;
            }).join('');

        const typeBadge = this.formatTypeBadge(prod.product_type);
        const statusBadge = prod.is_active
          ? '<span class="badge bg-success-subtle text-success border border-success-subtle font-mono small"><i class="bi bi-check-circle me-1"></i> Active</span>'
          : '<span class="badge bg-light text-muted border font-mono small"><i class="bi bi-pause-circle me-1"></i> Inactive</span>';

        return `
          <tr>
            <td>
              <div class="fw-bold text-navy">${prod.name}</div>
              ${prod.notes ? `<div class="text-muted small text-truncate" style="max-width: 240px;">${prod.notes}</div>` : ''}
            </td>
            <td>${typeBadge}</td>
            <td class="fw-bold text-slate-900">${this.formatCurrency(prod.sales_price)}</td>
            <td class="text-muted">${this.formatCurrency(prod.cost_price || 0)}</td>
            <td>
              <div style="max-width: 250px;">
                ${variantHtml}
              </div>
            </td>
            <td>${statusBadge}</td>
            <td class="text-end text-nowrap">
              <button class="btn btn-sm btn-outline-primary py-1 px-2 me-1" onclick="products.openProductDetailModal(${prod.id})" title="View Details">
                <i class="bi bi-eye"></i>
              </button>
              <button class="btn btn-sm btn-outline-info py-1 px-2 me-1" onclick="products.openVariantManagerModal(${prod.id})" title="Manage Variants">
                <i class="bi bi-sliders"></i>
              </button>
              <button class="btn btn-sm btn-outline-secondary py-1 px-2 me-1" onclick="products.openEditProductModal(${prod.id})" title="Edit Product">
                <i class="bi bi-pencil"></i>
              </button>
              <button class="btn btn-sm btn-outline-danger py-1 px-2" onclick="products.openDeleteConfirmModal(${prod.id})" title="Delete Product">
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>
        `;
      }).join('');

      this.renderPagination(
        'productsPaginationContainer',
        currentPage,
        totalPages,
        filtered.length,
        startIndex,
        pageItems.length,
        (newPage) => {
          this.state.filters.page = newPage;
          this.renderProductsTable();
        }
      );
    },

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
              <a class="page-link" href="javascript:void(0)" onclick="products.handlePageClick(${i})">${i}</a>
            </li>
          `;
        } else if (i === currentPage - 2 || i === currentPage + 2) {
          pageButtons += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
        }
      }

      container.innerHTML = `
        <div class="d-flex flex-column flex-sm-row align-items-center justify-content-between gap-2 py-3 border-top border-slate-200">
          <div class="text-muted small">
            Showing <span class="fw-semibold text-navy">${start}</span> to <span class="fw-semibold text-navy">${end}</span> of <span class="fw-semibold text-navy">${totalItems}</span> products
          </div>
          <nav aria-label="Table pagination">
            <ul class="pagination pagination-sm mb-0">
              <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
                <a class="page-link" href="javascript:void(0)" onclick="products.handlePageClick(${currentPage - 1})">Previous</a>
              </li>
              ${pageButtons}
              <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
                <a class="page-link" href="javascript:void(0)" onclick="products.handlePageClick(${currentPage + 1})">Next</a>
              </li>
            </ul>
          </nav>
        </div>
      `;

      this.paginationCallback = onPageSelect;
    },

    handlePageClick(newPage) {
      if (this.paginationCallback) {
        this.paginationCallback(newPage);
      }
    },

    // ==========================================
    // 4. PRODUCT ADD & EDIT MODAL
    // ==========================================

    openAddProductModal() {
      this.state.activeProduct = null;
      setText('productModalTitle', 'Add New Product');
      setVal('prodIdInput', '');
      setVal('prodNameInput', '');
      setVal('prodTypeSelect', 'SOFTWARE');
      setVal('prodSalesPriceInput', '');
      setVal('prodCostPriceInput', '0.00');
      setVal('prodNotesInput', '');
      const activeChk = document.getElementById('prodIsActiveCheck');
      if (activeChk) activeChk.checked = true;

      // Clear inline variants container
      const container = document.getElementById('inlineVariantsContainer');
      if (container) container.innerHTML = '';

      // Add one default variant row for convenience
      this.addInlineVariantRow();

      const modalEl = document.getElementById('productModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
      }
    },

    openEditProductModal(productId) {
      const prod = this.state.products.find(p => p.id === productId);
      if (!prod) return;

      this.state.activeProduct = prod;
      setText('productModalTitle', `Edit Product #${prod.id}: ${prod.name}`);
      setVal('prodIdInput', prod.id);
      setVal('prodNameInput', prod.name);
      setVal('prodTypeSelect', prod.product_type);
      setVal('prodSalesPriceInput', prod.sales_price);
      setVal('prodCostPriceInput', prod.cost_price || '0.00');
      setVal('prodNotesInput', prod.notes || '');
      const activeChk = document.getElementById('prodIsActiveCheck');
      if (activeChk) activeChk.checked = !!prod.is_active;

      // Render existing inline variants
      const container = document.getElementById('inlineVariantsContainer');
      if (container) {
        container.innerHTML = '';
        const variants = prod.variants || [];
        if (variants.length === 0) {
          this.addInlineVariantRow();
        } else {
          variants.forEach(v => {
            this.addInlineVariantRow(v.id, v.attribute_name, v.attribute_value, v.price_extra);
          });
        }
      }

      const modalEl = document.getElementById('productModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
      }
    },

    addInlineVariantRow(id = '', attrName = 'Edition', attrVal = '', priceExtra = '0.00') {
      const container = document.getElementById('inlineVariantsContainer');
      if (!container) return;

      const rowId = `variant_row_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
      const rowHtml = `
        <div class="variant-form-row d-flex align-items-center gap-2" id="${rowId}" data-variant-id="${id}">
          <input type="hidden" class="v-id" value="${id}">
          <div style="flex: 2;">
            <input type="text" class="form-control form-control-sm v-name" placeholder="Attribute (e.g. Tier)" value="${attrName}" required>
          </div>
          <div style="flex: 2;">
            <input type="text" class="form-control form-control-sm v-val" placeholder="Value (e.g. Standard)" value="${attrVal}" required>
          </div>
          <div style="flex: 2;">
            <div class="input-group input-group-sm">
              <span class="input-group-text bg-white">+$</span>
              <input type="number" step="0.01" min="0" class="form-control v-price" placeholder="0.00" value="${priceExtra}">
            </div>
          </div>
          <button type="button" class="btn btn-outline-danger btn-sm px-2" onclick="document.getElementById('${rowId}').remove()" title="Remove variant">
            <i class="bi bi-trash"></i>
          </button>
        </div>
      `;
      container.insertAdjacentHTML('beforeend', rowHtml);
    },

    async saveProduct() {
      const prodId = document.getElementById('prodIdInput').value;
      const name = document.getElementById('prodNameInput').value.trim();
      const productType = document.getElementById('prodTypeSelect').value;
      const salesPrice = document.getElementById('prodSalesPriceInput').value;
      const costPrice = document.getElementById('prodCostPriceInput').value || '0.00';
      const notes = document.getElementById('prodNotesInput').value.trim();
      const isActive = document.getElementById('prodIsActiveCheck').checked;

      if (!name) {
        window.api.showToast('Product name is required.', 'error');
        return;
      }
      if (!salesPrice || parseFloat(salesPrice) < 0) {
        window.api.showToast('Please enter a valid base sales price.', 'error');
        return;
      }

      // Collect inline variants
      const variantRows = document.querySelectorAll('#inlineVariantsContainer .variant-form-row');
      const variantsPayload = [];
      for (const row of variantRows) {
        const vId = row.querySelector('.v-id').value;
        const vName = row.querySelector('.v-name').value.trim();
        const vVal = row.querySelector('.v-val').value.trim();
        const vPrice = row.querySelector('.v-price').value || '0.00';

        if (vName && vVal) {
          const item = {
            attribute_name: vName,
            attribute_value: vVal,
            price_extra: vPrice
          };
          if (vId) item.id = parseInt(vId);
          variantsPayload.push(item);
        }
      }

      const payload = {
        name,
        product_type: productType,
        sales_price: salesPrice,
        cost_price: costPrice,
        notes,
        is_active: isActive,
        variants: variantsPayload
      };

      try {
        window.api.showLoading(prodId ? 'Updating product...' : 'Creating product...');
        let res;
        if (prodId) {
          res = await window.api.put(`/api/products/${prodId}/`, payload);
          window.api.showToast(`Product '${res.name}' updated successfully!`, 'success');
        } else {
          res = await window.api.post('/api/products/', payload);
          window.api.showToast(`Product '${res.name}' created successfully!`, 'success');
        }

        // Close modal
        const modalEl = document.getElementById('productModal');
        if (modalEl && window.bootstrap) {
          const modal = bootstrap.Modal.getInstance(modalEl);
          if (modal) modal.hide();
        }

        // Reload products list
        await this.loadCatalogData();

      } catch (err) {
        console.error('Save product error:', err);
        window.api.showToast(window.api.formatError(err.data) || err.message, 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    // ==========================================
    // 5. PRODUCT DETAILS MODAL
    // ==========================================

    openProductDetailModal(productId) {
      const prod = this.state.products.find(p => p.id === productId);
      if (!prod) return;

      setText('detailProdName', prod.name);
      setText('detailProdId', `#${prod.id}`);
      setHtml('detailProdType', this.formatTypeBadge(prod.product_type));
      setHtml('detailProdStatus', prod.is_active
        ? '<span class="badge bg-success-subtle text-success border border-success-subtle font-mono small">Active</span>'
        : '<span class="badge bg-light text-muted border font-mono small">Inactive</span>');

      const sales = parseFloat(prod.sales_price || 0);
      const cost = parseFloat(prod.cost_price || 0);
      const margin = sales - cost;
      const marginPct = sales > 0 ? ((margin / sales) * 100).toFixed(1) : '0.0';

      setText('detailProdSalesPrice', this.formatCurrency(sales));
      setText('detailProdCostPrice', this.formatCurrency(cost));
      setText('detailProdMargin', `${this.formatCurrency(margin)} (${marginPct}%)`);
      setText('detailProdNotes', prod.notes || 'No description notes provided.');

      // Variants Table
      const vTbody = document.getElementById('detailVariantsTbody');
      if (vTbody) {
        const variants = prod.variants || [];
        if (variants.length === 0) {
          vTbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-3">No variants configured for this product.</td></tr>`;
        } else {
          vTbody.innerHTML = variants.map(v => {
            const extra = parseFloat(v.price_extra || 0);
            const effectivePrice = sales + extra;
            return `
              <tr>
                <td class="fw-semibold text-navy">${v.attribute_name}: ${v.attribute_value}</td>
                <td>${this.formatCurrency(sales)}</td>
                <td class="text-primary font-mono">+${this.formatCurrency(extra)}</td>
                <td class="fw-bold text-success font-mono">${this.formatCurrency(effectivePrice)}</td>
              </tr>
            `;
          }).join('');
        }
      }

      // Wire manage variants button inside details modal
      const btnManageVariants = document.getElementById('btnDetailManageVariants');
      if (btnManageVariants) {
        btnManageVariants.onclick = () => {
          const detailModal = bootstrap.Modal.getInstance(document.getElementById('productDetailModal'));
          if (detailModal) detailModal.hide();
          this.openVariantManagerModal(prod.id);
        };
      }

      const modalEl = document.getElementById('productDetailModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
      }
    },

    // ==========================================
    // 6. DELETE PRODUCT MODAL
    // ==========================================

    openDeleteConfirmModal(productId) {
      const prod = this.state.products.find(p => p.id === productId);
      if (!prod) return;

      this.state.activeProduct = prod;
      setText('deleteProdName', prod.name);
      setText('deleteProdId', `#${prod.id}`);

      const btnConfirm = document.getElementById('btnConfirmDeleteProduct');
      if (btnConfirm) {
        btnConfirm.onclick = () => this.confirmDeleteProduct(prod.id);
      }

      const modalEl = document.getElementById('deleteConfirmModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
      }
    },

    async confirmDeleteProduct(productId) {
      try {
        window.api.showLoading('Deleting product...');
        await window.api.delete(`/api/products/${productId}/`);
        window.api.showToast('Product successfully deleted.', 'success');

        const modalEl = document.getElementById('deleteConfirmModal');
        if (modalEl && window.bootstrap) {
          const modal = bootstrap.Modal.getInstance(modalEl);
          if (modal) modal.hide();
        }

        await this.loadCatalogData();

      } catch (err) {
        console.error('Delete product error:', err);
        window.api.showToast(window.api.formatError(err.data) || err.message, 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    // ==========================================
    // 7. DEDICATED VARIANT MANAGEMENT MODAL
    // ==========================================

    openVariantManagerModal(productId) {
      const prod = this.state.products.find(p => p.id === productId);
      if (!prod) return;

      this.state.activeProduct = prod;
      this.state.editingVariantId = null;

      setText('varModalProductName', prod.name);
      setText('varModalBasePrice', this.formatCurrency(prod.sales_price));

      this.resetVariantForm();
      this.renderVariantTableForProduct(prod);

      const modalEl = document.getElementById('variantModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
      }
    },

    renderVariantTableForProduct(prod) {
      const tbody = document.getElementById('variantManagerTbody');
      if (!tbody) return;

      const baseSales = parseFloat(prod.sales_price || 0);
      const variants = prod.variants || [];

      if (variants.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-4">No variants configured for ${prod.name}. Add one below.</td></tr>`;
        return;
      }

      tbody.innerHTML = variants.map(v => {
        const extra = parseFloat(v.price_extra || 0);
        const effective = baseSales + extra;

        return `
          <tr>
            <td class="fw-bold text-navy font-mono">${v.attribute_name}</td>
            <td class="fw-semibold text-slate-800">${v.attribute_value}</td>
            <td class="font-mono text-primary">+${this.formatCurrency(extra)}</td>
            <td class="font-mono fw-bold text-success">${this.formatCurrency(effective)}</td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-secondary py-0 px-2 me-1" onclick="products.editVariantInline(${v.id}, '${v.attribute_name}', '${v.attribute_value}', '${extra}')">
                <i class="bi bi-pencil"></i>
              </button>
              <button class="btn btn-sm btn-outline-danger py-0 px-2" onclick="products.deleteVariant(${v.id})">
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>
        `;
      }).join('');
    },

    resetVariantForm() {
      this.state.editingVariantId = null;
      setText('varFormTitle', 'Add New Variant');
      setVal('varAttrNameInput', 'Edition');
      setVal('varAttrValueInput', '');
      setVal('varPriceExtraInput', '0.00');
      setText('btnSaveVariant', 'Add Variant');
    },

    editVariantInline(variantId, attrName, attrVal, priceExtra) {
      this.state.editingVariantId = variantId;
      setText('varFormTitle', `Edit Variant #${variantId}`);
      setVal('varAttrNameInput', attrName);
      setVal('varAttrValueInput', attrVal);
      setVal('varPriceExtraInput', priceExtra);
      setText('btnSaveVariant', 'Update Variant');
    },

    async saveDedicatedVariant() {
      if (!this.state.activeProduct) return;

      const productId = this.state.activeProduct.id;
      const attrName = document.getElementById('varAttrNameInput').value.trim();
      const attrValue = document.getElementById('varAttrValueInput').value.trim();
      const priceExtra = document.getElementById('varPriceExtraInput').value || '0.00';

      if (!attrName || !attrValue) {
        window.api.showToast('Attribute name and value are required.', 'error');
        return;
      }

      try {
        window.api.showLoading('Saving variant...');

        if (this.state.editingVariantId) {
          // Update existing variant via PATCH /api/product-variants/{id}/
          await window.api.patch(`/api/product-variants/${this.state.editingVariantId}/`, {
            attribute_name: attrName,
            attribute_value: attrValue,
            price_extra: priceExtra
          });
          window.api.showToast('Variant updated successfully.', 'success');
        } else {
          // Create new standalone variant via POST /api/product-variants/
          await window.api.post('/api/product-variants/', {
            product: productId,
            attribute_name: attrName,
            attribute_value: attrValue,
            price_extra: priceExtra
          });
          window.api.showToast('Variant added successfully.', 'success');
        }

        this.resetVariantForm();

        // Refresh product data
        await this.loadCatalogData();
        const updatedProd = this.state.products.find(p => p.id === productId);
        if (updatedProd) {
          this.state.activeProduct = updatedProd;
          this.renderVariantTableForProduct(updatedProd);
        }

      } catch (err) {
        console.error('Variant save error:', err);
        window.api.showToast(window.api.formatError(err.data) || err.message, 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    async deleteVariant(variantId) {
      if (!confirm('Are you sure you want to delete this variant?')) return;

      try {
        window.api.showLoading('Deleting variant...');
        await window.api.delete(`/api/product-variants/${variantId}/`);
        window.api.showToast('Variant deleted.', 'success');

        await this.loadCatalogData();
        if (this.state.activeProduct) {
          const updatedProd = this.state.products.find(p => p.id === this.state.activeProduct.id);
          if (updatedProd) {
            this.state.activeProduct = updatedProd;
            this.renderVariantTableForProduct(updatedProd);
          }
        }
      } catch (err) {
        console.error('Delete variant error:', err);
        window.api.showToast(window.api.formatError(err.data) || err.message, 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    // ==========================================
    // 8. TAX RULES MANAGEMENT MODAL
    // ==========================================

    openTaxRulesModal() {
      this.resetTaxRuleForm();
      this.renderTaxRulesTable();

      const modalEl = document.getElementById('taxRulesModal');
      if (modalEl && window.bootstrap) {
        const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
        modal.show();
      }
    },

    renderTaxRulesTable() {
      const tbody = document.getElementById('taxRulesTableBody');
      if (!tbody) return;

      const taxes = this.state.taxRules || [];
      if (taxes.length === 0) {
        tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-3">No tax rules configured.</td></tr>`;
        return;
      }

      tbody.innerHTML = taxes.map(t => `
        <tr>
          <td class="fw-bold text-navy">${t.name}</td>
          <td class="font-mono fw-semibold">${parseFloat(t.rate)}%</td>
          <td>
            ${t.is_active
              ? '<span class="badge bg-success-subtle text-success border border-success-subtle font-mono small">Active</span>'
              : '<span class="badge bg-light text-muted border font-mono small">Inactive</span>'}
          </td>
          <td class="text-end">
            <button class="btn btn-sm btn-outline-secondary py-0 px-2 me-1" onclick="products.editTaxRuleInline(${t.id}, '${t.name}', '${t.rate}', ${t.is_active})">
              <i class="bi bi-pencil"></i>
            </button>
            <button class="btn btn-sm btn-outline-danger py-0 px-2" onclick="products.deleteTaxRule(${t.id})">
              <i class="bi bi-trash"></i>
            </button>
          </td>
        </tr>
      `).join('');
    },

    resetTaxRuleForm() {
      this.state.editingTaxRuleId = null;
      setText('taxRuleFormTitle', 'Add Tax Rule');
      setVal('taxRuleNameInput', '');
      setVal('taxRuleRateInput', '');
      const activeChk = document.getElementById('taxRuleIsActiveCheck');
      if (activeChk) activeChk.checked = true;
      setText('btnSaveTaxRule', 'Save Tax Rule');
    },

    editTaxRuleInline(taxId, name, rate, isActive) {
      this.state.editingTaxRuleId = taxId;
      setText('taxRuleFormTitle', `Edit Tax Rule #${taxId}`);
      setVal('taxRuleNameInput', name);
      setVal('taxRuleRateInput', rate);
      const activeChk = document.getElementById('taxRuleIsActiveCheck');
      if (activeChk) activeChk.checked = !!isActive;
      setText('btnSaveTaxRule', 'Update Tax Rule');
    },

    async saveTaxRule() {
      const name = document.getElementById('taxRuleNameInput').value.trim();
      const rate = document.getElementById('taxRuleRateInput').value;
      const isActive = document.getElementById('taxRuleIsActiveCheck').checked;

      if (!name || !rate) {
        window.api.showToast('Tax name and percentage rate are required.', 'error');
        return;
      }

      const payload = {
        name,
        rate: parseFloat(rate).toFixed(2),
        is_active: isActive
      };

      try {
        window.api.showLoading('Saving tax rule...');
        if (this.state.editingTaxRuleId) {
          await window.api.put(`/api/tax-rules/${this.state.editingTaxRuleId}/`, payload);
          window.api.showToast('Tax rule updated successfully.', 'success');
        } else {
          await window.api.post('/api/tax-rules/', payload);
          window.api.showToast('Tax rule created successfully.', 'success');
        }

        this.resetTaxRuleForm();
        await this.loadCatalogData();

      } catch (err) {
        console.error('Save tax rule error:', err);
        window.api.showToast(window.api.formatError(err.data) || err.message, 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    async deleteTaxRule(taxId) {
      if (!confirm('Are you sure you want to delete this tax rule?')) return;

      try {
        window.api.showLoading('Deleting tax rule...');
        await window.api.delete(`/api/tax-rules/${taxId}/`);
        window.api.showToast('Tax rule deleted.', 'success');
        await this.loadCatalogData();
      } catch (err) {
        console.error('Delete tax rule error:', err);
        window.api.showToast(window.api.formatError(err.data) || err.message, 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    // ==========================================
    // 8B. PLANS MANAGEMENT
    // ==========================================

    renderPlansTable() {
      const tbody = document.getElementById('plansTableBody');
      if (!tbody) return;

      const plans = this.state.plans || [];
      if (plans.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-4">No subscription plans found. Click 'Add Plan' to create one.</td></tr>`;
        return;
      }

      tbody.innerHTML = plans.map(p => {
        const periodBadgeMap = {
          DAILY: 'bg-info-subtle text-info border border-info-subtle',
          WEEKLY: 'bg-primary-subtle text-primary border border-primary-subtle',
          MONTHLY: 'bg-success-subtle text-success border border-success-subtle',
          YEARLY: 'bg-purple-subtle text-purple border',
        };
        const periodBadge = `<span class="badge ${periodBadgeMap[p.billing_period] || 'bg-light text-dark'} font-mono small">${p.billing_period}</span>`;

        return `
          <tr>
            <td class="fw-bold text-navy">${p.name}</td>
            <td>${periodBadge}</td>
            <td class="font-mono fw-bold text-slate-900">${this.formatCurrency(p.price)}</td>
            <td class="text-center">${p.min_quantity || 1}</td>
            <td>
              ${p.auto_close_at_end ? '<span class="badge bg-warning-subtle text-dark border small font-mono">Auto-Close</span>' : '<span class="text-muted small">No</span>'}
            </td>
            <td>
              ${p.allow_pause ? '<span class="badge bg-success-subtle text-success border small font-mono">Yes</span>' : '<span class="text-muted small">No</span>'}
            </td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-secondary py-1 px-2 me-1" onclick="products.openEditPlanModal(${p.id})">
                <i class="bi bi-pencil"></i>
              </button>
              <button class="btn btn-sm btn-outline-danger py-1 px-2" onclick="products.deletePlan(${p.id})">
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>
        `;
      }).join('');
    },

    openAddPlanModal() {
      this.state.editingPlanId = null;
      setText('planModalTitle', 'Add Subscription Plan');
      setVal('planIdInput', '');
      setVal('planNameInput', '');
      setVal('planPriceInput', '');
      setVal('planPeriodSelect', 'MONTHLY');
      setVal('planMinQtyInput', '1');
      const autoCloseChk = document.getElementById('planAutoCloseCheck');
      if (autoCloseChk) autoCloseChk.checked = false;
      const allowPauseChk = document.getElementById('planAllowPauseCheck');
      if (allowPauseChk) allowPauseChk.checked = false;
      const allowRenewChk = document.getElementById('planAllowRenewCheck');
      if (allowRenewChk) allowRenewChk.checked = true;

      const modalEl = document.getElementById('planModal');
      if (modalEl && window.bootstrap) {
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
      }
    },

    openEditPlanModal(planId) {
      const plan = this.state.plans.find(p => p.id === planId);
      if (!plan) return;

      this.state.editingPlanId = planId;
      setText('planModalTitle', `Edit Plan: ${plan.name}`);
      setVal('planIdInput', plan.id);
      setVal('planNameInput', plan.name);
      setVal('planPriceInput', plan.price);
      setVal('planPeriodSelect', plan.billing_period);
      setVal('planMinQtyInput', plan.min_quantity || 1);
      const autoCloseChk = document.getElementById('planAutoCloseCheck');
      if (autoCloseChk) autoCloseChk.checked = !!plan.auto_close_at_end;
      document.getElementById('planAllowPauseCheck').checked = !!plan.allow_pause;
      document.getElementById('planAllowRenewCheck').checked = plan.allow_renew !== false;

      const modalEl = document.getElementById('planModal');
      if (modalEl && window.bootstrap) {
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
      }
    },

    async savePlan() {
      const planId = this.state.editingPlanId;
      const name = document.getElementById('planNameInput').value.trim();
      const price = document.getElementById('planPriceInput').value;
      const billing_period = document.getElementById('planPeriodSelect').value;
      const min_quantity = parseInt(document.getElementById('planMinQtyInput').value) || 1;
      const auto_close_at_end = document.getElementById('planAutoCloseCheck').checked;
      const allow_pause = document.getElementById('planAllowPauseCheck').checked;
      const allow_renew = document.getElementById('planAllowRenewCheck').checked;

      if (!name || !price) {
        window.api.showToast('Plan name and price are required.', 'error');
        return;
      }

      const payload = {
        name,
        price,
        billing_period,
        min_quantity,
        auto_close_at_end,
        allow_pause,
        allow_renew
      };

      try {
        window.api.showLoading(planId ? 'Updating plan...' : 'Creating plan...');
        if (planId) {
          await window.api.put(`/api/plans/${planId}/`, payload);
          window.api.showToast(`Plan '${name}' updated successfully!`, 'success');
        } else {
          await window.api.post('/api/plans/', payload);
          window.api.showToast(`Plan '${name}' created successfully!`, 'success');
        }

        const modalEl = document.getElementById('planModal');
        if (modalEl && window.bootstrap) {
          bootstrap.Modal.getInstance(modalEl).hide();
        }

        await this.loadCatalogData();
      } catch (err) {
        console.error('Save plan error:', err);
        window.api.showToast(window.api.formatError(err.data) || err.message, 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    async deletePlan(planId) {
      if (!confirm('Are you sure you want to delete this subscription plan?')) return;

      try {
        window.api.showLoading('Deleting plan...');
        await window.api.delete(`/api/plans/${planId}/`);
        window.api.showToast('Plan deleted successfully.', 'success');
        await this.loadCatalogData();
      } catch (err) {
        console.error('Delete plan error:', err);
        window.api.showToast(window.api.formatError(err.data) || err.message, 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    // ==========================================
    // 8C. DISCOUNTS MANAGEMENT
    // ==========================================

    renderDiscountsTable() {
      const tbody = document.getElementById('discountsTableBody');
      if (!tbody) return;

      const discounts = this.state.discounts || [];
      if (discounts.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-4">No active discounts found.</td></tr>`;
        return;
      }

      tbody.innerHTML = discounts.map(d => {
        const valFormatted = d.discount_type === 'PERCENTAGE' ? `${parseFloat(d.value)}%` : this.formatCurrency(d.value);
        const usesLabel = d.max_uses ? `${d.current_uses} / ${d.max_uses}` : `${d.current_uses} (Unlimited)`;

        return `
          <tr>
            <td class="fw-bold font-mono text-navy">${d.code}</td>
            <td><span class="badge bg-light text-dark font-mono small">${d.discount_type}</span></td>
            <td class="fw-bold text-success font-mono">${valFormatted}</td>
            <td class="font-mono text-slate-600">${usesLabel}</td>
            <td>${d.is_active ? '<span class="badge bg-success-subtle text-success border small font-mono">Active</span>' : '<span class="badge bg-light text-muted border small font-mono">Inactive</span>'}</td>
            <td class="text-end">
              <button class="btn btn-sm btn-outline-danger py-1 px-2" onclick="products.deleteDiscount(${d.id})">
                <i class="bi bi-trash"></i>
              </button>
            </td>
          </tr>
        `;
      }).join('');
    },

    openAddDiscountModal() {
      setVal('discCodeInput', '');
      setVal('discTypeSelect', 'PERCENTAGE');
      setVal('discValueInput', '10.00');
      setVal('discMaxUsesInput', '');

      const modalEl = document.getElementById('discountModal');
      if (modalEl && window.bootstrap) {
        bootstrap.Modal.getOrCreateInstance(modalEl).show();
      }
    },

    async saveDiscount() {
      const code = document.getElementById('discCodeInput').value.trim().toUpperCase();
      const discount_type = document.getElementById('discTypeSelect').value;
      const value = document.getElementById('discValueInput').value;
      const max_uses = document.getElementById('discMaxUsesInput').value;

      if (!code || !value) {
        window.api.showToast('Discount code and value are required.', 'error');
        return;
      }

      const today = new Date().toISOString().split('T')[0];
      const nextYear = new Date(Date.now() + 365*24*3600*1000).toISOString().split('T')[0];

      const payload = {
        code,
        discount_type,
        value,
        start_date: today,
        end_date: nextYear,
        is_active: true
      };
      if (max_uses) payload.max_uses = parseInt(max_uses);

      try {
        window.api.showLoading('Creating discount...');
        await window.api.post('/api/discounts/', payload);
        window.api.showToast(`Discount '${code}' created!`, 'success');

        const modalEl = document.getElementById('discountModal');
        if (modalEl && window.bootstrap) {
          bootstrap.Modal.getInstance(modalEl).hide();
        }

        await this.loadCatalogData();
      } catch (err) {
        console.error('Save discount error:', err);
        window.api.showToast(window.api.formatError(err.data) || err.message, 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    async deleteDiscount(discId) {
      if (!confirm('Are you sure you want to delete this discount?')) return;

      try {
        window.api.showLoading('Deleting discount...');
        await window.api.delete(`/api/discounts/${discId}/`);
        window.api.showToast('Discount deleted.', 'success');
        await this.loadCatalogData();
      } catch (err) {
        console.error('Delete discount error:', err);
        window.api.showToast(window.api.formatError(err.data) || err.message, 'error');
      } finally {
        window.api.hideLoading();
      }
    },

    // ==========================================
    // 9. FORMATTERS
    // ==========================================

    formatCurrency(val) {
      const num = parseFloat(val);
      if (isNaN(num)) return '$0.00';
      return '$' + num.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });
    },

    formatTypeBadge(typeVal) {
      const t = String(typeVal || 'SOFTWARE').toUpperCase();
      const map = {
        SOFTWARE: 'badge-type-software',
        SERVICE: 'badge-type-service',
        HARDWARE: 'badge-type-hardware',
        CONSUMABLE: 'badge-type-consumable'
      };
      return `<span class="badge ${map[t] || 'badge-type-software'} font-mono small">${t}</span>`;
    }
  };

  window.products = products;
  document.addEventListener('DOMContentLoaded', () => products.init());
})();

