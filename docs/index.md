# Awning Management System Documentation

![CI](https://github.com/andrewimpellitteri/awning_wo/actions/workflows/python-ci.yml/badge.svg)
![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/andrewimpellitteri/44c7c17b0a9d04574018f0518fd13a6b/raw/awning-coverage.json)

Welcome to the documentation for the Awning Management System - a comprehensive Flask-based application for managing work orders, repair orders, customers, inventory, and analytics for an awning cleaning and repair business.

## Quick Links

<div class="grid cards" markdown>

-   :material-account-group:{ .lg .middle } **User Guide**

    ---

    Learn how to use the application's features for day-to-day operations.

    [:octicons-arrow-right-24: Get Started](user-guide/getting-started.md)

-   :material-code-braces:{ .lg .middle } **Developer Guide**

    ---

    Set up your development environment and learn the codebase architecture.

    [:octicons-arrow-right-24: Setup](developer-guide/setup.md)

-   :material-database:{ .lg .middle } **Database**

    ---

    Learn about database migrations, schema changes, and data management.

    [:octicons-arrow-right-24: Alembic Guide](database/ALEMBIC_GUIDE.md)

-   :material-rocket-launch:{ .lg .middle } **Deployment**

    ---

    Deploy to AWS Elastic Beanstalk and manage production environments.

    [:octicons-arrow-right-24: Deployment Guide](deployment/aws-eb.md)

</div>

## What is the Awning Management System?

The Awning Management System is a full-featured web application built with Flask that helps manage:

- **Work Orders** - Track cleaning jobs from intake to completion
- **Repair Orders** - Manage repair jobs with detailed item tracking
- **Customers** - Maintain customer records and order history
- **Sources & Vendors** - Track sail lofts and vendor relationships
- **Inventory** - Monitor inventory items and usage
- **Queue Management** - Organize cleaning and repair queues
- **Analytics** - Visualize business metrics and trends with interactive dashboards
- **ML Predictions** - Predict work order completion times using machine learning

## Key Features

### For Users

- **Intuitive Interface** - Clean, easy-to-navigate UI for daily operations
- **Queue Workflows** - Streamlined cleaning and repair queue management
- **PDF Generation** - Automated PDF reports for work orders and repair orders
- **Real-time Analytics** - Interactive dashboards with business insights
- **Keyboard Shortcuts** - Power user shortcuts for faster data entry
- **Multi-user Support** - Role-based access control and user management

### For Developers

- **Modern Stack** - Flask, SQLAlchemy, PostgreSQL, Alembic
- **ML Integration** - LightGBM model for completion time predictions
- **Cloud Ready** - Deployed on AWS Elastic Beanstalk with RDS and S3
- **Well Tested** - Comprehensive pytest test suite with high coverage
- **CI/CD Pipeline** - GitHub Actions for automated testing and deployment
- **Database Migrations** - Alembic for safe schema evolution

## Documentation Structure

### :material-account: User Guide
Everything users need to know to operate the system effectively.

- [Getting Started](user-guide/getting-started.md) - First steps and login
- [Work Orders](user-guide/work-orders.md) - Creating and managing work orders
- [Repair Orders](user-guide/repair-orders.md) - Handling repair jobs
- [Analytics Dashboard](user-guide/analytics.md) - Understanding business metrics
- [Keyboard Shortcuts](user-guide/keyboard-shortcuts.md) - Power user tips

### :material-code-braces: Developer Guide
For developers working on or extending the codebase.

- [Setup & Installation](developer-guide/setup.md) - Local development setup
- [Project Structure](developer-guide/project-structure.md) - Codebase organization
- [Database Schema](developer-guide/database-schema.md) - Data models and relationships
- [Testing](developer-guide/testing.md) - Running and writing tests
- [Contributing](developer-guide/contributing.md) - Contribution guidelines

### :material-database: Database
Database schema, migrations, and data management.

- [Alembic Migration Guide](database/ALEMBIC_GUIDE.md) - Complete migration workflow
- [Storage Fields Guide](database/STORAGE_FIELDS_GUIDE.md) - Understanding storage fields

### :material-rocket: Deployment
Production deployment and operations.

- [AWS Elastic Beanstalk](deployment/aws-eb.md) - Deployment to AWS
- [Deployment Checklist](deployment/DEPLOYMENT_CHECKLIST.md) - Pre-deployment verification
- [Monitoring & Logging](deployment/monitoring.md) - Production monitoring

### :material-chart-line: Architecture
System design, performance, and technical deep-dives.

- [System Overview](architecture/overview.md) - High-level architecture
- [ML Prediction System](architecture/ml-system.md) - Machine learning implementation
- [Caching Strategy](architecture/CACHING_GUIDE.md) - Performance optimization
- [Performance Analysis](architecture/PERFORMANCE_ANALYSIS.md) - Query optimization
- [Concurrency Audit](architecture/CONCURRENCY_AUDIT.md) - Thread safety and locking

### :material-lightbulb: Planning
Future improvements and refactoring plans.

- [Improvement Roadmap](planning/IMPROVEMENTS.md) - Planned enhancements
- [Refactoring Plan](planning/REFACTORING_PLAN.md) - Code improvement plans
- [Denormalization Analysis](planning/DENORMALIZATION_ANALYSIS.md) - Database optimization plans

## Tech Stack

| Category | Technologies |
|----------|-------------|
| **Backend** | Flask 2.3.3, Python 3.x |
| **Database** | PostgreSQL, SQLAlchemy, Alembic |
| **Authentication** | Flask-Login |
| **Forms** | Flask-WTF, WTForms |
| **ML/Analytics** | scikit-learn, LightGBM, pandas, polars, plotly |
| **Documents** | reportlab, PyMuPDF, python-docx |
| **Cloud** | AWS Elastic Beanstalk, RDS, S3 |
| **Testing** | pytest, pytest-flask, pytest-cov |
| **CI/CD** | GitHub Actions |

## Getting Help

- **For Users:** See the [User Guide](user-guide/index.md) or [FAQ](reference/faq.md)
- **For Developers:** Check the [Developer Guide](developer-guide/index.md) or [Troubleshooting](reference/troubleshooting.md)
- **Issues:** Report bugs on [GitHub Issues](https://github.com/andrewimpellitteri/awning_wo/issues)

## Quick Start

### For Users
1. Navigate to the application URL
2. Log in with your credentials
3. Start with the [Getting Started Guide](user-guide/getting-started.md)

### For Developers
```bash
# Clone the repository
git clone https://github.com/andrewimpellitteri/awning_wo.git
cd awning_wo

# Follow the setup guide
```
See the full [Setup & Installation Guide](developer-guide/setup.md) for detailed instructions.

## Repository

**GitHub:** [andrewimpellitteri/awning_wo](https://github.com/andrewimpellitteri/awning_wo)

---

!!! info "Documentation Version"
    This documentation is automatically built from the latest version of the codebase.
