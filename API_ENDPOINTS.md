# Brightloop Software - API Endpoints Documentation

Base URL: `/api/`  
Authentication scheme: `Bearer <jwt_token>` via `Authorization` header.  
CORS Allowed Origins: `http://localhost:5173`, `http://127.0.0.1:5500`, `http://localhost:3000`

---

## 1. Authentication & User Profile

| Method | Endpoint | Allowed Roles | Description | Request Body Fields |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/signup/` | Anyone (Public) | Self-service registration; always creates accounts with `role: CUSTOMER` | `email` (string, required, email format)<br>`password` (string, required, min 9 chars)<br>`first_name` (string, optional)<br>`last_name` (string, optional) |
| `POST` | `/api/auth/login/` | Anyone (Public) | SimpleJWT token generation | `email` (string, required)<br>`password` (string, required) |
| `POST` | `/api/auth/token/refresh/` | Anyone (Public) | Refresh expired JWT access token | `refresh` (string, required) |
| `POST` | `/api/auth/password-reset/` | Anyone (Public) | Dispatches salted password reset link via console email | `email` (string, required) |
| `POST` | `/api/auth/password-reset/confirm/` | Anyone (Public) | Verifies token and resets password | `uidb64` (string, required)<br>`token` (string, required)<br>`new_password` (string, required) |
| `GET` | `/api/auth/me/` | `ADMIN`, `STAFF`, `CUSTOMER` | Returns `{id, email, first_name, last_name, role}` for the authenticated user | *None* |
| `POST` | `/api/auth/users/create-staff/` | `ADMIN` only | Provision internal `STAFF` account | `email` (string, required)<br>`password` (string, required)<br>`first_name` (string, optional)<br>`last_name` (string, optional) |

---

## 2. Catalog: Products & Variants

| Method | Endpoint | Allowed Roles | Description | Request Body Fields |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/products/` | `ADMIN`, `STAFF` | List products with nested variants | *None* |
| `POST` | `/api/products/` | `ADMIN` only | Create a product with optional nested variants | `name` (string, required)<br>`product_type` (`SERVICE`, `SOFTWARE`, `HARDWARE`, `CONSUMABLE`, default: `SOFTWARE`)<br>`sales_price` (decimal, required)<br>`cost_price` (decimal, optional, default: `0.00`)<br>`notes` (string, optional)<br>`is_active` (boolean, optional, default: `true`)<br>`variants` (array of `{attribute_name, attribute_value, price_extra}`, optional) |
| `GET` | `/api/products/{id}/` | `ADMIN`, `STAFF` | Retrieve product details | *None* |
| `PUT` | `/api/products/{id}/` | `ADMIN` only | Full product update | Same as `POST /api/products/` |
| `PATCH` | `/api/products/{id}/` | `ADMIN` only | Partial product update | Any fields from `POST /api/products/` |
| `DELETE` | `/api/products/{id}/` | `ADMIN` only | Delete product | *None* |
| `GET` | `/api/product-variants/` | `ADMIN`, `STAFF` | List variants | *None* |
| `POST` | `/api/product-variants/` | `ADMIN` only | Create standalone variant | `product` (integer ID, required)<br>`attribute_name` (string, required)<br>`attribute_value` (string, required)<br>`price_extra` (decimal, optional, default: `0.00`) |
| `GET` | `/api/product-variants/{id}/` | `ADMIN`, `STAFF` | Retrieve variant details | *None* |
| `PUT` | `/api/product-variants/{id}/` | `ADMIN` only | Full variant update | Same as `POST /api/product-variants/` |
| `PATCH` | `/api/product-variants/{id}/` | `ADMIN` only | Partial variant update | Any fields from `POST /api/product-variants/` |
| `DELETE` | `/api/product-variants/{id}/` | `ADMIN` only | Delete variant | *None* |

---

## 3. Catalog: Tax Rules

| Method | Endpoint | Allowed Roles | Description | Request Body Fields |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/tax-rules/` | `ADMIN`, `STAFF` | List tax rules | *None* |
| `POST` | `/api/tax-rules/` | `ADMIN` only | Create a tax rule | `name` (string, required)<br>`rate` (decimal, required, e.g. `20.00`)<br>`is_active` (boolean, optional, default: `true`) |
| `GET` | `/api/tax-rules/{id}/` | `ADMIN`, `STAFF` | Retrieve tax rule | *None* |
| `PUT` | `/api/tax-rules/{id}/` | `ADMIN` only | Full tax rule update | Same as `POST /api/tax-rules/` |
| `PATCH` | `/api/tax-rules/{id}/` | `ADMIN` only | Partial tax rule update | Any fields from `POST /api/tax-rules/` |
| `DELETE` | `/api/tax-rules/{id}/` | `ADMIN` only | Delete tax rule | *None* |

---

## 4. Catalog: Plans

| Method | Endpoint | Allowed Roles | Description | Request Body Fields |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/plans/` | `ADMIN`, `STAFF` | List plans | *None* |
| `POST` | `/api/plans/` | `ADMIN` only | Create a recurring billing plan | `name` (string, required)<br>`price` (decimal, required)<br>`billing_period` (`DAILY`, `WEEKLY`, `MONTHLY`, `YEARLY`, default: `MONTHLY`)<br>`min_quantity` (integer, optional, default: 1)<br>`available_from` (date YYYY-MM-DD, optional, default: today)<br>`available_to` (date YYYY-MM-DD, optional)<br>`auto_close_at_end` (boolean, optional, default: `false`)<br>`allow_early_close` (boolean, optional, default: `true`)<br>`allow_pause` (boolean, optional, default: `false`)<br>`allow_renew` (boolean, optional, default: `true`) |
| `GET` | `/api/plans/{id}/` | `ADMIN`, `STAFF` | Retrieve plan | *None* |
| `PUT` | `/api/plans/{id}/` | `ADMIN` only | Full plan update | Same as `POST /api/plans/` |
| `PATCH` | `/api/plans/{id}/` | `ADMIN` only | Partial plan update | Any fields from `POST /api/plans/` |
| `DELETE` | `/api/plans/{id}/` | `ADMIN` only | Delete plan | *None* |

---

## 5. Catalog: Discounts

| Method | Endpoint | Allowed Roles | Description | Request Body Fields |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/discounts/` | `ADMIN`, `STAFF` | List discounts with computed `is_valid_now` | *None* |
| `POST` | `/api/discounts/` | `ADMIN` only | Create a promotional discount | `code` (string, required, unique)<br>`discount_type` (`PERCENTAGE`, `FIXED`, required)<br>`value` (decimal, required)<br>`products` (array of integer product IDs, optional; empty = whole subscription)<br>`min_purchase_amount` (decimal, optional, default: `0.00`)<br>`min_quantity` (integer, optional, default: 0)<br>`start_date` (date YYYY-MM-DD, required)<br>`end_date` (date YYYY-MM-DD, required)<br>`max_uses` (integer, optional, null = unlimited)<br>`is_active` (boolean, optional, default: `true`) |
| `GET` | `/api/discounts/{id}/` | `ADMIN`, `STAFF` | Retrieve discount details | *None* |
| `PUT` | `/api/discounts/{id}/` | `ADMIN` only | Full discount update | Same as `POST /api/discounts/` |
| `PATCH` | `/api/discounts/{id}/` | `ADMIN` only | Partial discount update | Any fields from `POST /api/discounts/` |
| `DELETE` | `/api/discounts/{id}/` | `ADMIN` only | Delete discount | *None* |

---

## 6. Quotation Templates & Lines

| Method | Endpoint | Allowed Roles | Description | Request Body Fields |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/quotation-templates/` | `ADMIN`, `STAFF` | List quotation templates with lines | *None* |
| `POST` | `/api/quotation-templates/` | `ADMIN`, `STAFF` | Create quotation template with nested lines | `name` (string, required)<br>`plan` (integer ID, required)<br>`validity_days` (integer, optional, default: 30)<br>`lines` (array of `{product, variant, quantity, unit_price}`, optional) |
| `GET` | `/api/quotation-templates/{id}/` | `ADMIN`, `STAFF` | Retrieve quotation template | *None* |
| `PUT` | `/api/quotation-templates/{id}/` | `ADMIN`, `STAFF` | Full template update | Same as `POST /api/quotation-templates/` |
| `PATCH` | `/api/quotation-templates/{id}/` | `ADMIN`, `STAFF` | Partial template update | Any fields from `POST /api/quotation-templates/` |
| `DELETE` | `/api/quotation-templates/{id}/` | `ADMIN`, `STAFF` | Delete quotation template | *None* |
| `POST` | `/api/quotation-templates/{id}/create-subscription/` | `ADMIN`, `STAFF` | Generate a subscription from template | `customer` (integer ID, required, role must be `CUSTOMER`)<br>`start_date` (date YYYY-MM-DD, optional, default: today)<br>`discount` (integer ID, optional)<br>`payment_terms_days` (integer, optional, default: 30) |
| `GET` | `/api/quotation-template-lines/` | `ADMIN`, `STAFF` | List quotation template lines | *None* |
| `POST` | `/api/quotation-template-lines/` | `ADMIN`, `STAFF` | Create quotation template line | `template` (integer ID, required)<br>`product` (integer ID, required)<br>`variant` (integer ID, optional)<br>`quantity` (integer, optional, default: 1)<br>`unit_price` (decimal, optional; calculated if omitted) |
| `GET` | `/api/quotation-template-lines/{id}/` | `ADMIN`, `STAFF` | Retrieve quotation template line | *None* |
| `PUT` | `/api/quotation-template-lines/{id}/` | `ADMIN`, `STAFF` | Update quotation template line | Same as `POST /api/quotation-template-lines/` |
| `PATCH` | `/api/quotation-template-lines/{id}/` | `ADMIN`, `STAFF` | Partial line update | Any fields from `POST /api/quotation-template-lines/` |
| `DELETE` | `/api/quotation-template-lines/{id}/` | `ADMIN`, `STAFF` | Delete quotation template line | *None* |

---

## 7. Subscriptions & Lines

| Method | Endpoint | Allowed Roles | Description | Request Body Fields |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/subscriptions/` | `ADMIN`, `STAFF`, `CUSTOMER` | List subscriptions. Customers only see their own. Staff/Admin see all. | *None* |
| `POST` | `/api/subscriptions/` | `ADMIN`, `STAFF` | Create subscription. Auto-generates `subscription_number: SUB-YYYY-XXXX`. Line `unit_price = sales_price + price_extra`. | `customer` (integer ID, required, role must be `CUSTOMER`)<br>`plan` (integer ID, required)<br>`discount` (integer ID, optional)<br>`start_date` (date YYYY-MM-DD, optional, default: today)<br>`expiry_date` (date YYYY-MM-DD, optional)<br>`payment_terms_days` (integer, optional, default: 30)<br>`status` (`DRAFT`, `QUOTATION`, `CONFIRMED`, `ACTIVE`, `PAUSED`, `CLOSED`, default: `DRAFT`)<br>`lines` (array of `{product, variant, quantity, tax_rule}`, optional) |
| `GET` | `/api/subscriptions/{id}/` | `ADMIN`, `STAFF`, `CUSTOMER` (owner only) | Retrieve subscription details | *None* |
| `PUT` | `/api/subscriptions/{id}/` | `ADMIN`, `STAFF` | Full subscription update | Same as `POST /api/subscriptions/` |
| `PATCH` | `/api/subscriptions/{id}/` | `ADMIN`, `STAFF` | Partial subscription update | Any fields from `POST /api/subscriptions/` |
| `DELETE` | `/api/subscriptions/{id}/` | `ADMIN`, `STAFF` | Delete subscription | *None* |
| `POST` | `/api/subscriptions/{id}/transition/` | `ADMIN`, `STAFF` | State machine transition via `transition_to()`. When moving to `ACTIVE`, sets `next_billing_date = start_date`. Returns `400` on invalid jumps. | `status` or `new_status` (`DRAFT`, `QUOTATION`, `CONFIRMED`, `ACTIVE`, `PAUSED`, `CLOSED`, required) |
| `POST` | `/api/subscriptions/create-from-template/` | `ADMIN`, `STAFF` | Generate a subscription and its lines from a designated `QuotationTemplate` | `template` (integer ID, required)<br>`customer` (integer ID, required)<br>`start_date` (date YYYY-MM-DD, optional)<br>`discount` (integer ID, optional)<br>`payment_terms_days` (integer, optional, default: 30) |
| `GET` | `/api/subscription-lines/` | `ADMIN`, `STAFF`, `CUSTOMER` | List subscription lines (customers view own only) | *None* |
| `POST` | `/api/subscription-lines/` | `ADMIN`, `STAFF` | Add a subscription line. Unit price auto-calculated. | `subscription` (integer ID, required)<br>`product` (integer ID, required)<br>`variant` (integer ID, optional)<br>`quantity` (integer, optional, default: 1)<br>`tax_rule` (integer ID, optional) |
| `GET` | `/api/subscription-lines/{id}/` | `ADMIN`, `STAFF`, `CUSTOMER` (owner only) | Retrieve subscription line | *None* |
| `PUT` | `/api/subscription-lines/{id}/` | `ADMIN`, `STAFF` | Full line update | Same as `POST /api/subscription-lines/` |
| `PATCH` | `/api/subscription-lines/{id}/` | `ADMIN`, `STAFF` | Partial line update | Any fields from `POST /api/subscription-lines/` |
| `DELETE` | `/api/subscription-lines/{id}/` | `ADMIN`, `STAFF` | Delete subscription line | *None* |

---

## 8. Invoices

| Method | Endpoint | Allowed Roles | Description | Request Body Fields |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/invoices/` | `ADMIN`, `STAFF`, `CUSTOMER` | List invoices. Customers view own only. Staff/Admin view all. | *None* |
| `GET` | `/api/invoices/{id}/` | `ADMIN`, `STAFF`, `CUSTOMER` (owner only) | Retrieve full invoice details including lines, payments, and balance | *None* |
| `POST` | `/api/invoices/{id}/confirm/` | `ADMIN`, `STAFF` | Transitions invoice status `DRAFT` $\rightarrow$ `CONFIRMED` | *None* |
| `POST` | `/api/invoices/{id}/cancel/` | `ADMIN`, `STAFF` | Transitions invoice status to `CANCELLED` | *None* |
| `POST` | `/api/invoices/{id}/send/` | `ADMIN`, `STAFF` | Dispatches invoice summary email to customer (console mailer) | *None* |
| `GET` | `/api/invoices/{id}/pdf/` | `ADMIN`, `STAFF`, `CUSTOMER` (owner only) | Streams invoice as a formatted PDF 1.4 document | *None* |
| `GET` | `/api/invoices/{id}/print/` | `ADMIN`, `STAFF`, `CUSTOMER` (owner only) | Alias for `/pdf/` | *None* |
| `POST` | `/api/invoices/{id}/pay/` | `ADMIN`, `STAFF` | Record payment directly on invoice | `amount` (decimal, required, $> 0$, $\le$ amount due)<br>`method` (`CREDIT_CARD`, `BANK_TRANSFER`, `CASH`, `OTHER`, default: `BANK_TRANSFER`)<br>`transaction_reference` (string, optional)<br>`note` (string, optional) |

---

## 9. Payments

| Method | Endpoint | Allowed Roles | Description | Request Body Fields |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/payments/` | `ADMIN`, `STAFF` | Log payment against confirmed invoice. Row-locked. Transitions invoice to `PAID` upon full settlement. **POST only** (`GET` returns `405`). | `invoice` (integer ID, required; status must be `CONFIRMED`)<br>`amount` (decimal, required, $> 0$, $\le$ amount due)<br>`method` (`CREDIT_CARD`, `BANK_TRANSFER`, `CASH`, `OTHER`, default: `BANK_TRANSFER`)<br>`transaction_reference` (string, optional)<br>`note` (string, optional) |

---

## 10. Finance Dashboard

*Staff and Admin only (`ADMIN`, `STAFF`). All queries use indexed lookups and database aggregations.*

| Method | Endpoint | Allowed Roles | Description | Query Parameters | Request Body |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/dashboard/` | `ADMIN`, `STAFF` | High-level financial KPIs overview: active subscriptions, total revenue, outstanding balance, overdue invoices count & amount. | `start_date` (YYYY-MM-DD)<br>`end_date` (YYYY-MM-DD)<br>`customer` (customer ID or email)<br>`status` (SubscriptionStatus choice)<br>`method` (PaymentMethod choice) | *None* |
| `GET` | `/api/dashboard/overview/` | `ADMIN`, `STAFF` | Explicit action alias for high-level KPIs overview. | Same as `/api/dashboard/` | *None* |
| `GET` | `/api/dashboard/overdue-invoices/` | `ADMIN`, `STAFF` | Paginated list of overdue invoices (`CONFIRMED`, `due_date < today`, unpaid), ordered by `due_date`. | `customer` (ID or email)<br>`start_date` (issue_date $\ge$)<br>`end_date` (issue_date $\le$)<br>`page` (int)<br>`page_size` (int) | *None* |
| `GET` | `/api/dashboard/payments/` | `ADMIN`, `STAFF` | Paginated list of all payments with related invoice & customer details, ordered by `-payment_date`. | `customer` (ID or email)<br>`start_date` (payment_date $\ge$)<br>`end_date` (payment_date $\le$)<br>`method` (payment method)<br>`page` (int)<br>`page_size` (int) | *None* |

---

## 11. Background Management Commands

| Command | Usage | Description |
| :--- | :--- | :--- |
| `generate_invoices` | `python manage.py generate_invoices [--date YYYY-MM-DD]` | Scans `ACTIVE` subscriptions where `next_billing_date <= today`. Copies lines from `SubscriptionLines` only, generates `INV-YYYY-XXXX`, evaluates discount rules and increments `current_uses` via `F()`, advances `next_billing_date`, auto-closes on expiry if `plan.auto_close_at_end`, and guarantees idempotency. Prints summary: `created`, `skipped`, `errors`. |
| `seed_demo` | `python manage.py seed_demo [--flush]` | Generates demo dataset: 50 customers, 5 products with variants, 3 plans, 2,000 subscriptions with lines, 2,000 invoices with partial/full payments and overdue invoices. Seeds primary test users: `admin@brightloop.io`, `staff@brightloop.io`, `customer@brightloop.io` with password `Password123!`. |


