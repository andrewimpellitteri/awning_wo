# Frequently Asked Questions (FAQ)

## Table of Contents

- [General Questions](#general-questions)
- [Account & Access](#account--access)
- [Work Orders](#work-orders)
- [Repair Orders](#repair-orders)
- [Customers](#customers)
- [File Uploads](#file-uploads)
- [PDF Generation](#pdf-generation)
- [Analytics & Reports](#analytics--reports)
- [Technical Questions](#technical-questions)
- [Billing & Pricing](#billing--pricing)

---

## General Questions

### What is the Awning Management System?

The Awning Management System is a web-based application designed to manage awning cleaning and repair operations. It handles work orders, repair orders, customer information, inventory tracking, and business analytics.

### Who can use the application?

The application is designed for:
- **Office staff** - Create and manage orders, handle customer interactions
- **Cleaning crew** - View queue, update order status
- **Managers** - Access analytics, manage inventory
- **Administrators** - Full system access, user management

### Can I use the app on mobile devices?

Yes, the application is responsive and works on mobile devices (phones and tablets). However, some features work best on desktop computers:
- **Works well on mobile:** Viewing orders, checking queue, basic edits
- **Better on desktop:** Creating complex orders, analytics dashboards, PDF generation

**Recommended:**
- Use mobile for quick tasks and viewing information
- Use desktop for data entry and detailed work

### How do I get started?

1. Receive login credentials from your administrator
2. Navigate to the application URL
3. Log in with your username and password
4. Start with the [Getting Started Guide](../user-guide/getting-started.md)

### Is my data backed up?

Yes, the system includes multiple backup mechanisms:
- **Daily automated backups** of the database (retained for 7 days)
- **Manual snapshots** before each deployment
- **S3 file versioning** for uploaded documents
- **Point-in-time recovery** available for the last 35 days

---

## Account & Access

### How do I reset my password?

Contact your system administrator to reset your password. They will:
1. Generate a new invite token
2. Send you a registration link
3. You can then set a new password

**Note:** There is currently no self-service password reset. This feature may be added in the future.

### Why was I logged out?

Sessions expire after 24 hours of inactivity. You may also be logged out if:
- You cleared your browser cookies
- You logged in from another device
- An administrator reset your password
- The application was restarted

### How do I change my username?

Contact your system administrator. Usernames cannot be changed by regular users.

### What are the different user roles?

**Admin:**
- Full system access
- User management
- System configuration
- All features available

**User (Standard):**
- Create and edit work orders and repair orders
- Manage customers and inventory
- View analytics
- Cannot access admin features

### Can I have multiple accounts?

No, each person should have only one account. If you need different permission levels for different tasks, contact your administrator.

---

## Work Orders

### How do I create a new work order?

1. Click "Work Orders" in the navigation
2. Click "New Work Order" button
3. Select or create a customer
4. Add items (from customer's catalog or new items)
5. Fill in dates and pricing
6. Click "Save"

**See also:** [Work Orders User Guide](../user-guide/work-orders.md)

### How do I add multiple items to a work order?

**Option 1: Select from customer's catalog**
- Check boxes next to existing items
- Items from previous orders appear here

**Option 2: Add new items**
- Click "Add New Item" button
- Fill in description, material, color, quantity
- Repeat for each item
- New items are automatically added to customer's catalog

### Can I edit a completed work order?

Yes, but be cautious:
- Editing completed work orders may affect historical data
- Analytics and reports may show different results
- ML predictions use historical data for training

**Best practice:** Only edit completed orders to fix errors, not to make routine changes.

### How do I delete a work order?

1. Open the work order detail page
2. Click "Delete" button
3. Confirm deletion

**Warning:** Deletion is permanent and cannot be undone. All associated items and files will be deleted.

### What do the different work order statuses mean?

- **Pending** - Order created, not yet picked up
- **In Progress** - Being cleaned or worked on
- **Completed** - Finished and ready for return
- **Returned** - Delivered back to customer

### How do I change a work order's position in the queue?

1. Go to "Cleaning Queue"
2. Drag and drop work orders to reorder
3. Changes save automatically

Orders with higher priority should be placed higher in the queue.

### Can I print a work order?

Yes:
1. Open the work order detail page
2. Click "Download PDF" button
3. Open the PDF and print

The PDF includes all order details, customer information, and items.

---

## Repair Orders

### What's the difference between a work order and a repair order?

**Work Order:**
- For in-house awning cleaning
- Tracked through internal queue
- Simpler workflow (picked up → cleaned → returned)

**Repair Order:**
- For repairs sent to external vendors (sail lofts)
- Includes source/vendor tracking
- More complex workflow (picked up → sent out → received → returned)

### How do I create a repair order?

1. Click "Repair Orders" in navigation
2. Click "New Repair Order"
3. Select customer and source/vendor
4. Add items to be repaired
5. Fill in dates (sent out, received, etc.)
6. Save

### Can I see all repair orders sent to a specific vendor?

Yes:
1. Go to "Sources" (vendors)
2. Click on the source/vendor name
3. View list of all repair orders sent to that vendor

### How long do repairs typically take?

The system includes an ML prediction feature that estimates completion time based on:
- Historical repair order data
- Vendor/source performance
- Item complexity

Average repair times vary by vendor and are displayed in the analytics dashboard.

---

## Customers

### How do I add a new customer?

1. Click "Customers" in navigation
2. Click "New Customer" button
3. Fill in customer information:
   - Name (required)
   - Phone, email, address (optional)
4. Click "Save"

### What is a customer catalog?

The customer catalog is a collection of items that belong to a specific customer. When you add items to work orders or repair orders, they're automatically saved to the customer's catalog for easy reuse.

**Benefits:**
- Quick item selection for future orders
- Consistent item descriptions
- Track customer's inventory over time

### Can I merge duplicate customers?

Currently, there is no automated merge feature. Contact your administrator to manually merge customer records and transfer order history.

### How do I search for a customer?

**Option 1: Browse list**
- Go to "Customers"
- Scroll through the list
- Use pagination at bottom

**Option 2: Use search**
- Type customer name in search box
- Results appear as you type
- Click on customer to view details

**Tips:**
- Search is case-insensitive
- Partial names work (e.g., "john" finds "John Doe Yachts")
- Type at least 3 characters for best results

### Can I export customer data?

Currently, customer data export is not available in the user interface. Contact your administrator if you need a customer data export.

---

## File Uploads

### What types of files can I upload?

**Allowed file types:**
- **Documents:** PDF, DOC, DOCX, XLS, XLSX
- **Images:** JPG, JPEG, PNG, GIF

**Use cases:**
- Photos of awnings before/after cleaning
- Repair quotes from vendors
- Customer correspondence
- Invoices and receipts

### What is the file size limit?

Maximum file size: **10MB per file**

If your file is too large:
- Compress images (reduce quality or size)
- Convert documents to PDF
- Split large files into smaller parts
- Contact administrator if you need to upload larger files

### Where are my uploaded files stored?

Files are stored securely in AWS S3 (Amazon Simple Storage Service):
- **Not stored** on the web server
- **Encrypted** in transit and at rest
- **Backed up** with versioning enabled
- **Accessible** only to authenticated users

### Can I delete an uploaded file?

Yes:
1. Open the work order with the file
2. Find the file in the "Files" section
3. Click "Delete" button
4. Confirm deletion

**Warning:** Deletion is permanent.

### Why did my file upload fail?

Common reasons:
- File too large (>10MB)
- Invalid file type
- Network timeout
- S3 connection issue

**See:** [Troubleshooting - File Upload Issues](troubleshooting.md#file-upload-issues)

---

## PDF Generation

### How do I generate a PDF for a work order?

1. Open the work order detail page
2. Click "Download PDF" button
3. PDF will download automatically

The PDF includes:
- Company logo and header
- Customer information
- Work order details
- Items list
- Pricing information
- Notes

### Can I customize the PDF format?

PDF formatting is standardized for consistency. If you need custom formatting, contact your administrator to request changes to the PDF template.

### The PDF isn't generating. What should I do?

**Check these common issues:**
1. Work order has a customer assigned
2. Work order has at least one item
3. Browser allows downloads
4. Pop-ups aren't blocked

**See:** [Troubleshooting - PDF Generation](troubleshooting.md#pdf-generation-issues)

### Can I email PDFs directly from the system?

This feature is not currently available. You can:
1. Download the PDF
2. Attach to email manually
3. Send via your email client

---

## Analytics & Reports

### What analytics are available?

The analytics dashboard provides:
- **Revenue trends** over time
- **Order volume** statistics
- **Source/vendor performance** breakdown
- **Customer analytics** (top customers, order frequency)
- **Completion time** analysis
- **ML predictions** for future orders

### How do I filter analytics by date range?

1. Go to Analytics dashboard
2. Select start date and end date
3. Click "Apply"
4. Charts update automatically

**Tip:** Use shorter date ranges (e.g., last 30 days) for better performance.

### Can I export analytics data?

Currently, analytics export is not available in the UI. Administrators can export data via database queries or contact support for custom reports.

### What is the ML prediction feature?

The ML (Machine Learning) model predicts work order completion times based on:
- Historical completion data
- Customer patterns
- Item complexity
- Seasonal trends

**How it works:**
1. Model trains daily on historical data
2. Analyzes completed work orders
3. Predicts completion time for new orders
4. Improves accuracy over time

**Accuracy:** Model accuracy improves with more data (typically >100 completed orders needed)

---

## Technical Questions

### What browsers are supported?

**Fully supported:**
- Google Chrome (recommended)
- Mozilla Firefox
- Apple Safari
- Microsoft Edge

**Version requirements:**
- Use the latest stable version
- JavaScript must be enabled
- Cookies must be allowed

**Not supported:**
- Internet Explorer
- Very old browser versions (<2 years old)

### Do I need to install any software?

No, the Awning Management System is a web-based application. You only need:
- A supported web browser
- Internet connection
- Login credentials

No downloads or installations required.

### Does the app work offline?

No, the application requires an internet connection. All data is stored on the server, not locally.

If you lose connection:
- Unsaved changes may be lost
- Refresh the page when connection returns
- Log in again if session expired

### Where is my data stored?

**Database:** AWS RDS (PostgreSQL) in US-East-1 region
**Files:** AWS S3 in US-East-1 region
**Application:** AWS Elastic Beanstalk

All data is stored within the United States and follows AWS security best practices.

### Is my data secure?

Yes, the application includes multiple security measures:
- **HTTPS encryption** for all data in transit
- **Database encryption** at rest
- **User authentication** required for all access
- **Role-based access control** (admin vs. user)
- **Automated backups** with encryption
- **Regular security updates**

### How often is the application updated?

**Regular updates:**
- Security patches: As needed (urgent)
- Bug fixes: Weekly to bi-weekly
- New features: Monthly to quarterly

**Maintenance windows:**
- Deployments: Usually weekday mornings (low traffic)
- Downtime: Typically 1-2 minutes
- Users are notified of major updates

---

## Billing & Pricing

### How much does the application cost?

Pricing information is not publicly available. Contact your organization's administrator or management for licensing costs.

### Are there usage limits?

Current limits:
- **File uploads:** 10MB per file
- **No limit** on number of work orders, customers, or users

For cloud hosting costs, your organization's AWS usage determines the cost.

### Can I add more users?

Yes, administrators can create new user accounts at any time. There is no hard limit on number of users.

**To add users:**
- Administrator generates invite token
- Sends registration link to new user
- User sets password and logs in

---

## Common Questions by User Type

### For Office Staff

**Q: How do I handle a customer call about their order?**
1. Search for customer by name
2. View customer detail page
3. Check work order or repair order status
4. Update customer with current status

**Q: How do I prioritize rush orders?**
1. Go to "Cleaning Queue"
2. Drag rush order to top of queue
3. Mark order with high priority (if available)

### For Cleaning Crew

**Q: What should I work on next?**
1. Go to "Cleaning Queue"
2. Work on orders from top to bottom
3. Update status as you progress

**Q: How do I mark an order as complete?**
1. Open the work order
2. Click "Edit"
3. Update "Cleaned" date and status
4. Save

### For Managers

**Q: How do I see overall business performance?**
1. Go to "Analytics" dashboard
2. Review revenue trends, order volume
3. Filter by date range for specific periods
4. Export data if needed (contact admin)

**Q: Which vendors are performing best?**
1. Go to "Analytics"
2. View "Source Performance" chart
3. Compare completion times and volume

---

## Still Have Questions?

### For Users

1. Check the [User Guide](../user-guide/getting-started.md)
2. Review [Troubleshooting Guide](troubleshooting.md)
3. Contact your system administrator
4. Email: support@yourdomain.com

### For Administrators

1. Check the [Developer Guide](../developer-guide/index.md)
2. Review [Operations Runbook](../deployment/operations-runbook.md)
3. Check [GitHub Issues](https://github.com/andrewimpellitteri/awning_wo/issues)
4. Create a new issue with details

---

## Document Information

**Last Updated:** 2025-11-16

**Feedback:** If you have suggestions for improving this FAQ, please contact your administrator or create a GitHub issue.
