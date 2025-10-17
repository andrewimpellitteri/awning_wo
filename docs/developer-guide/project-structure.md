# Project Structure

## Overview

The Awning Management System follows a modular Flask application structure.

## Directory Structure

```
awning_wo/
├── app.py                  # Application factory
├── application.py          # AWS EB entry point
├── config.py              # Configuration
├── extensions.py          # Flask extensions
├── decorators.py          # Custom decorators
├── models/                # SQLAlchemy models
│   ├── customer.py
│   ├── work_order.py
│   ├── repair_order.py
│   ├── source.py
│   └── ...
├── routes/                # Blueprint route handlers
│   ├── auth.py
│   ├── work_orders.py
│   ├── repair_order.py
│   └── ...
├── templates/             # Jinja2 templates
│   ├── base.html
│   ├── work_orders/
│   ├── repair_orders/
│   └── ...
├── static/               # CSS, JS, images
│   ├── css/
│   ├── js/
│   └── images/
└── tests/                # Test suite
```

## Key Files

### Application Entry Points

- `app.py` - Flask application factory, blueprint registration
- `application.py` - AWS Elastic Beanstalk WSGI entry point
- `config.py` - Environment-based configuration

### Models

Models are in `models/` and use SQLAlchemy ORM:

- `customer.py` - Customer information
- `work_order.py` - Work order model
- `repair_order.py` - Repair order model
- `source.py` - Vendor/source model

### Routes

Routes are organized as Flask blueprints in `routes/`:

- `work_orders.py` - Work order CRUD operations
- `repair_order.py` - Repair order operations
- `customers.py` - Customer management
- `analytics.py` - Analytics dashboard

### Templates

Jinja2 templates in `templates/` follow feature-based organization.

## Code Organization Principles

1. **Blueprints** - Each feature area has its own blueprint
2. **Models** - One file per model
3. **Templates** - Organized by feature
4. **DRY** - Shared logic in decorators and utilities

## Next Steps

- Learn the [Database Schema](database-schema.md)
- Explore [API Reference](api-reference.md)
- Read about [Testing](testing.md)
