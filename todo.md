# Awning Work Order Management App - To-Do List and Roadmap

This document outlines the necessary steps to enhance the Awning Work Order Management Flask app, migrate it to a production-ready environment, and improve its overall functionality and security.

## Phase 1: Core Functionality and UI/UX Improvements

This phase focuses on completing the core features of the application and improving the user interface.

### To-Do Checklist:

- [ ] **Implement Tabulator Tables:**
    - [ ] Integrate Tabulator.js for the work orders list (`/work_orders/list.html`).
    - [ ] Integrate Tabulator.js for the repair orders list (`/repair_orders/list.html`).
    - [ ] Integrate Tabulator.js for the sources list (`/source/list.html`).
    - [ ] Ensure all tables have consistent styling and functionality with the existing customers list.
- [ ] **Complete Work Order Management:**
    - [ ] Create a new route and template for editing existing work orders.
    - [ ] Implement the backend logic for updating work orders in the database.
    - [ ] Create a new route and template for creating new work orders.
    - [ ] Ensure the "Create Work Order" form (`/work_orders/create.html`) is fully functional.
- [ ] **Complete Repair Order Management:**
    - [ ] Create a new route and template for editing existing repair orders.
    - [ ] Implement the backend logic for updating repair orders in the database.
    - [ ] Create a new route and template for creating new repair orders.
- [ ] **User Management:**
    - [ ] Enhance the user management page (`/admin/manage_users.html`) to allow administrators to edit user roles and permissions.
    - [ ] Implement password reset functionality for users.
- [ ] **Refine Navigation and Layout:**
    - [ ] Review and improve the navigation menu in `base.html` to ensure it is intuitive and provides access to all key sections of the application.
    - [ ] Ensure a consistent and clean layout across all pages.

## Phase 2: Security, Testing, and Refactoring

This phase focuses on securing the application, adding a robust test suite, and refactoring the code for better maintainability.

### To-Do Checklist:

- [ ] **Security Enhancements:**
    - [ ] **Authentication and Authorization:**
        - [ ] Implement role-based access control (RBAC) using decorators to restrict access to certain routes based on user roles (e.g., admin, user).
        - [ ] Enforce password complexity requirements and secure password storage (e.g., using Werkzeug's security helpers).
        - [ ] Protect against common vulnerabilities like CSRF, XSS, and SQL injection.
    - [ ] **Session Management:**
        - [ ] Use secure session cookies with the `HttpOnly` and `Secure` flags.
        - [ ] Implement session timeouts.
- [ ] **Testing:**
    - [ ] **Unit Tests:**
        - [ ] Write unit tests for all models to ensure data integrity.
        - [ ] Write unit tests for all routes to verify correct behavior and access control.
    - [ ] **Integration Tests:**
        - [ ] Write integration tests to simulate user workflows, such as creating a work order and assigning it to a customer.
- [ ] **Code Refactoring:**
    - [ ] **Blueprints:**
        - [ ] Organize the application into Flask Blueprints for better structure and modularity.
    - [ ] **Database:**
        - [ ] Review and optimize database queries for performance.
        - [ ] Ensure all database interactions are handled through the SQLAlchemy ORM.
    - [ ] **Configuration:**
        - [ ] Move sensitive information like secret keys and database URIs to environment variables.

## Phase 3: Database Migration and Deployment

This phase focuses on migrating the application from SQLite to PostgreSQL and deploying it to a cloud environment.

### Roadmap:

1.  **Database Migration (SQLite to PostgreSQL):**
    - **Step 1: Set up a PostgreSQL Database:**
        - Install and configure PostgreSQL locally for development.
        - Create a new database and user for the application.
    - **Step 2: Update Application Configuration:**
        - Install the `psycopg2-binary` package.
        - Update the `SQLALCHEMY_DATABASE_URI` in `config.py` to connect to the PostgreSQL database.
    - **Step 3: Run Database Migrations:**
        - Use Flask-Migrate to generate and apply the necessary database migrations to the PostgreSQL database.
2.  **Deployment to AWS:**
    - **Step 1: Set up AWS Infrastructure:**
        - **RDS:** Create a managed PostgreSQL database instance using Amazon RDS.
        - **EC2/Elastic Beanstalk:** Choose a deployment target (EC2 for more control, Elastic Beanstalk for ease of use).
        - **S3:** Set up an S3 bucket for storing static files and user uploads.
    - **Step 2: Configure the Application for Production:**
        - Create a production configuration file with settings for the AWS environment.
        - Use a production-ready WSGI server like Gunicorn or uWSGI.
    - **Step 3: Deploy the Application:**
        - Deploy the application to the chosen AWS service.
        - Configure the web server (e.g., Nginx) to serve the application and static files.
    - **Step 4: Set up CI/CD (Optional but Recommended):**
        - Implement a CI/CD pipeline using a tool like Jenkins, GitLab CI/CD, or AWS CodePipeline to automate testing and deployment.

## Additional Recommendations

- **Logging and Monitoring:**
    - Implement comprehensive logging to track application events and errors.
    - Set up monitoring and alerting to be notified of any issues in the production environment.
- **Documentation:**
    - Create detailed documentation for the application, including setup instructions, API documentation, and user guides.


- [ ]add inventory item to customer page
    - [ ]edit button for items in both inventory page and create work order

- [ ] in add wo auto populate name of customer
- [ ] storage time field is seasonal/temp 

- [ ] rack should be location in add wo 
 
- [ ] need rack and storage time

- [ ] storage and rack number are redunadant --> make one field "location"

- [x] storage time to drop down
 - [x] seasonal or tempor


- [x] return status should be drop down
    - ship deliver pickup rehang unknown 

- [x] change clean treat to dates from yes/ no
- [x] quote (yes/done/approved)

- [x] remove clean/treat from create wo

- [ ] debug selected item not adding from create wo

- [ ] debug inventory item add + edit in wo create/edit (not adding items already in inventory)

- [ ] sort customer WOs by WO# in customer detail page

- [ ] show repair orders prefixed with "R"

ttt