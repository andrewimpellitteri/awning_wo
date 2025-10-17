# API Reference

This document provides a reference for all API endpoints and routes in the Awning Management System.

## Authentication

All routes require authentication via Flask-Login unless otherwise noted.

- **Login:** `POST /auth/login`
- **Logout:** `GET /auth/logout`
- **Register:** `POST /auth/register` (requires invite token)

---

## Work Orders

**Base URL:** `/work_orders`

### List & View

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/work_orders/` | GET | List all work orders (HTML view) |
| `/work_orders/<work_order_no>` | GET | View work order detail |
| `/work_orders/pending` | GET | View pending work orders |
| `/work_orders/completed` | GET | View completed work orders |
| `/work_orders/rush` | GET | View rush orders |
| `/work_orders/status/<status>` | GET | Filter by status |

### Create & Edit

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/work_orders/new` | GET, POST | Create new work order |
| `/work_orders/new/<prefill_cust_id>` | GET, POST | Create work order with customer pre-filled |
| `/work_orders/edit/<work_order_no>` | GET, POST | Edit work order |
| `/work_orders/cleaning-room/edit/<work_order_no>` | GET, POST | Simplified cleaning room edit |
| `/work_orders/delete/<work_order_no>` | POST | Delete work order |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/work_orders/api/work_orders` | GET | JSON API for work orders (supports filtering, sorting, pagination) |
| `/work_orders/api/next_wo_number` | GET | Get next available work order number |
| `/work_orders/api/customer_inventory/<cust_id>` | GET | Get inventory for customer |
| `/work_orders/api/open_repair_orders/<cust_id>` | GET | Get open repair orders for customer |

### File Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/work_orders/<work_order_no>/files` | GET | List files for work order |
| `/work_orders/<work_order_no>/files/upload` | POST | Upload file |
| `/work_orders/<work_order_no>/files/<file_id>/download` | GET | Download file |
| `/work_orders/thumbnail/<file_id>` | GET | Get PDF thumbnail |

### PDF Generation

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/work_orders/<work_order_no>/pdf/download` | GET | Generate and download PDF |

---

## Repair Orders

**Base URL:** `/repair_work_orders`

### List & View

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/repair_work_orders/` | GET | List all repair orders |
| `/repair_work_orders/<repair_order_no>` | GET | View repair order detail |
| `/repair_work_orders/pending` | GET | View pending repair orders |
| `/repair_work_orders/completed` | GET | View completed repair orders |

### Create & Edit

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/repair_work_orders/new` | GET, POST | Create new repair order |
| `/repair_work_orders/new/<prefill_cust_id>` | GET, POST | Create with customer pre-filled |
| `/repair_work_orders/edit/<repair_order_no>` | GET, POST | Edit repair order |
| `/repair_work_orders/delete/<repair_order_no>` | POST | Delete repair order |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/repair_work_orders/api/repair_orders` | GET | JSON API for repair orders |
| `/repair_work_orders/api/next_ro_number` | GET | Get next available repair order number |

### PDF Generation

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/repair_work_orders/<repair_order_no>/pdf/download` | GET | Generate and download PDF |

---

## Customers

**Base URL:** `/customers`

### List & View

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/customers/` | GET | List all customers |
| `/customers/<cust_id>` | GET | View customer detail |

### Create & Edit

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/customers/new` | GET, POST | Create new customer |
| `/customers/edit/<cust_id>` | GET, POST | Edit customer |
| `/customers/delete/<cust_id>` | POST | Delete customer |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/customers/api/customers` | GET | JSON API for customers |
| `/customers/search` | GET | Search customers by name/phone |

---

## Sources (Vendors)

**Base URL:** `/sources`

### List & View

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sources/` | GET | List all sources |
| `/sources/<source_id>` | GET | View source detail |

### Create & Edit

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sources/new` | GET, POST | Create new source |
| `/sources/edit/<source_id>` | GET, POST | Edit source |
| `/sources/delete/<source_id>` | POST | Delete source |

---

## Queue Management

**Base URL:** `/cleaning_queue`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/cleaning_queue/` | GET | View cleaning queue |
| `/cleaning_queue/api/queue_items` | GET | JSON API for queue items |

---

## In Progress

**Base URL:** `/in_progress`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/in_progress/` | GET | View in-progress orders |
| `/in_progress/api/in_progress_items` | GET | JSON API for in-progress items |

---

## Inventory

**Base URL:** `/inventory`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/inventory/` | GET | List inventory items |
| `/inventory/new` | GET, POST | Create new inventory item |
| `/inventory/edit/<inv_id>` | GET, POST | Edit inventory item |
| `/inventory/delete/<inv_id>` | POST | Delete inventory item |

---

## Analytics

**Base URL:** `/analytics`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analytics/` | GET | Analytics dashboard |
| `/analytics/api/data` | GET | JSON data for charts |

---

## Machine Learning

**Base URL:** `/ml`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ml/` | GET | ML dashboard |
| `/ml/predict` | POST | Get completion time prediction |
| `/ml/train` | POST | Train ML model |
| `/ml/cron/retrain` | POST | Cron job for retraining (requires secret header) |

---

## Admin

**Base URL:** `/admin`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/users` | GET | Manage users (admin only) |
| `/admin/invite` | POST | Create invite token (admin only) |
| `/admin/delete_user/<user_id>` | POST | Delete user (admin only) |

---

## Dashboard

**Base URL:** `/`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard |
| `/health` | GET | Health check endpoint (no auth required) |

---

## Common API Parameters

### Pagination

Most list API endpoints support pagination:

```
?page=1&per_page=20
```

### Filtering

API endpoints support column-based filtering:

```
?filter_<column>=<value>
```

Examples:
- `?filter_Source=Boat%20Covers`
- `?filter_CustID=123`

### Sorting

API endpoints support Tabulator-style sorting:

```
?sort[0][field]=<column>&sort[0][dir]=<asc|desc>
```

Example:
- `?sort[0][field]=DateIn&sort[0][dir]=desc`

### Search

Some endpoints support full-text search:

```
?search=<query>
```

---

## Response Formats

### HTML Responses

Most `GET` routes return HTML templates for browser viewing.

### JSON API Responses

API endpoints return JSON in this format:

#### Success Response
```json
{
  "data": [...],
  "total": 100,
  "page": 1,
  "per_page": 20
}
```

#### Error Response
```json
{
  "error": "Error message"
}
```

---

## File Uploads

File uploads use `multipart/form-data` encoding and are stored in AWS S3.

**Supported File Types:**
- PDF (.pdf)
- Images (.jpg, .jpeg, .png, .gif)
- Documents (.doc, .docx, .xls, .xlsx)

**Max File Size:** 10MB (configurable)

---

## Authentication Details

### Login
**Endpoint:** `POST /auth/login`

**Form Data:**
- `username` (string, required)
- `password` (string, required)

**Response:** Redirects to dashboard on success

### Session Management

The application uses Flask-Login for session management:
- Sessions are cookie-based
- Cookies are HTTP-only and secure (in production)
- Session timeout: 30 days (remember me) or browser session

---

## Error Codes

| HTTP Code | Description |
|-----------|-------------|
| 200 | Success |
| 302 | Redirect (often after POST) |
| 400 | Bad Request (invalid input) |
| 401 | Unauthorized (not logged in) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 500 | Server Error |

---

## Rate Limiting

Currently, no rate limiting is implemented. This may be added in future versions.

---

## Examples

### Get Work Orders List (JSON)

```bash
curl -X GET "http://localhost:5000/work_orders/api/work_orders?page=1&per_page=20" \
  --cookie "session=<your-session-cookie>"
```

### Create Work Order

```bash
curl -X POST "http://localhost:5000/work_orders/new" \
  --cookie "session=<your-session-cookie>" \
  --form "CustID=123" \
  --form "WOName=Summer Cleaning" \
  --form "DateIn=2024-01-15"
```

### Upload File

```bash
curl -X POST "http://localhost:5000/work_orders/12345/files/upload" \
  --cookie "session=<your-session-cookie>" \
  --form "file=@document.pdf"
```

---

## Code References

For implementation details, see:

- [routes/work_orders.py](../../routes/work_orders.py) - Work order routes
- [routes/repair_order.py](../../routes/repair_order.py) - Repair order routes
- [routes/customers.py](../../routes/customers.py) - Customer routes
- [routes/analytics.py](../../routes/analytics.py) - Analytics routes
- [models/](../../models/) - Database models

---

## Need Help?

- Check the [FAQ](../reference/faq.md)
- See [Troubleshooting](../reference/troubleshooting.md)
- Report bugs on [GitHub Issues](https://github.com/andrewimpellitteri/awning_wo/issues)
