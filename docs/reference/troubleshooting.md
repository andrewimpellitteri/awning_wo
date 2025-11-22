# Troubleshooting Guide

## Overview

This comprehensive troubleshooting guide covers common issues, error messages, and their solutions for the Awning Management System.

## Quick Diagnosis

**Start here if you're experiencing issues:**

| Symptom | Likely Cause | Quick Fix | Detailed Section |
|---------|--------------|-----------|------------------|
| Cannot log in | Wrong credentials | Verify username/password | [Login Issues](#login-issues) |
| Page won't load | Server error | Check logs, restart | [Application Errors](#application-errors) |
| Slow performance | Database query | Clear cache, optimize | [Performance Issues](#performance-issues) |
| PDF won't generate | Missing data | Check required fields | [PDF Generation](#pdf-generation-issues) |
| File upload fails | Size/type limit | Check file size (<10MB) | [File Upload Issues](#file-upload-issues) |
| Data not saving | Validation error | Check form fields | [Form Validation](#form-validation-errors) |

---

## Login Issues

### "Invalid username or password"

**Symptoms:**
- Error message on login page
- Cannot access application

**Causes:**
1. Incorrect credentials
2. User account disabled
3. Caps Lock enabled
4. Password recently changed

**Solutions:**

**Step 1: Verify credentials**
```
- Double-check username (case-sensitive)
- Verify password (check Caps Lock)
- Try copying/pasting password from password manager
```

**Step 2: Check account status**
```
Contact administrator to verify:
- Account exists
- Account is active (not disabled)
- Password hasn't expired
```

**Step 3: Reset password**
```
1. Contact system administrator
2. Request password reset
3. Administrator will generate new invite token
4. Follow registration link to set new password
```

### Session Expired

**Symptoms:**
- Logged out unexpectedly
- "Please log in to continue" message

**Causes:**
- Session timeout (24 hours default)
- Browser cookies cleared
- Multiple tabs/devices

**Solutions:**
```
1. Log in again
2. Check "Remember Me" box (if available)
3. Clear browser cookies and try again
4. Contact admin if issue persists
```

---

## Application Errors

### 500 Internal Server Error

**Symptoms:**
- "500 Internal Server Error" message
- Page fails to load
- Generic error page

**Common causes:**

**1. Database connection failure**
```
Solution: Contact administrator
- Application needs to be restarted
- Database may be down
```

**2. Application bug**
```
Solution: Report to administrator with:
- What you were trying to do
- Steps to reproduce
- Screenshot of error
```

### 404 Not Found

**Symptoms:**
- "404 Not Found" error
- Page doesn't exist

**Solutions:**
```
1. Check URL for typos
2. Verify resource exists (e.g., work order #123)
3. Return to dashboard and navigate again
4. Clear browser cache
```

### 403 Forbidden

**Symptoms:**
- "403 Forbidden" message
- "You don't have permission to access this resource"

**Causes:**
- Insufficient user permissions
- Accessing admin-only page as regular user

**Solutions:**
```
1. Contact administrator for permission upgrade
2. Verify you need access to this feature
3. Use a different account with proper permissions
```

---

## Performance Issues

### Page Loads Slowly

**Symptoms:**
- Pages take >5 seconds to load
- Timeout errors
- Application feels sluggish

**Solutions:**

**1. Clear browser cache**
```
Chrome: Ctrl+Shift+Delete (Cmd+Shift+Delete on Mac)
Firefox: Ctrl+Shift+Delete
Safari: Cmd+Option+E
```

**2. Check internet connection**
```
- Run speed test (speedtest.net)
- Try on different network
- Use wired connection instead of WiFi
```

**3. Try different browser**
```
- Test in Chrome, Firefox, or Safari
- Disable browser extensions
- Use incognito/private mode
```

**4. Contact administrator** (if persistent)
```
Provide:
- Which page is slow
- How long it takes to load
- Your internet speed
- Browser and version
```

### Dashboard Loads Slowly

**Symptoms:**
- Analytics dashboard takes >10 seconds
- Charts don't render
- Browser becomes unresponsive

**Solutions:**
```
1. Reduce date range (e.g., last 30 days vs. all time)
2. Filter by specific customers or sources
3. Clear browser cache
4. Close other browser tabs
5. Use Chrome for best performance
```

---

## PDF Generation Issues

### PDF Doesn't Generate

**Symptoms:**
- "PDF generation failed" error
- Download doesn't start
- Blank PDF downloaded

**Solutions:**

**1. Check browser settings**
```
- Enable pop-ups for this site
- Allow downloads
- Check Downloads folder
```

**2. Verify required fields**
```
- Work order has customer assigned
- Items exist on work order
- All dates are valid
```

**3. Try different browser**
```
- Chrome or Firefox recommended
- Disable PDF viewer extensions
- Try downloading instead of viewing
```

**4. Contact administrator** (if persistent)
```
Provide:
- Work order number
- Screenshot of error
- Browser and version
```

### PDF Formatting Issues

**Symptoms:**
- Text overlaps
- Images don't appear
- Wrong page size

**Solutions:**
```
1. Download PDF instead of viewing in browser
2. Open with Adobe Reader or Preview
3. Print to PDF if needed
4. Report formatting issues to administrator
```

---

## File Upload Issues

### File Upload Fails

**Symptoms:**
- "File upload failed" error
- Upload progress bar stalls
- File doesn't appear after upload

**Solutions:**

**1. Check file size**
```
Maximum file size: 10MB
- Compress file before uploading
- Split into multiple smaller files
```

**2. Check file type**
```
Allowed types: PDF, JPG, PNG, GIF, DOC, DOCX, XLS, XLSX
- Convert file to allowed format
- Use PDF for documents, JPG/PNG for images
```

**3. Check internet connection**
```
- Try uploading again
- Use wired connection instead of WiFi
- Upload during off-peak hours
```

**4. Try different browser**
```
- Chrome or Firefox recommended
- Disable browser extensions
- Clear browser cache
```

### Uploaded File Doesn't Appear

**Symptoms:**
- Upload completes successfully
- File not visible in work order files list

**Solutions:**
```
1. Refresh page (Ctrl+R or Cmd+R)
2. Clear browser cache
3. Check if file was uploaded to correct work order
4. Wait 1-2 minutes and refresh again
5. Contact administrator if still missing
```

---

## Form Validation Errors

### "Required field" Error

**Symptoms:**
- Cannot submit form
- Red error message under field
- Form highlights missing fields

**Solutions:**
```
1. Fill in all required fields (marked with *)
2. Check for empty fields that appear filled
3. Verify date fields have valid dates (MM/DD/YYYY)
4. Ensure numeric fields have numbers
5. Remove any special characters
```

### "Invalid email format"

**Solutions:**
```
Use format: user@example.com

Correct:
- john@example.com
- jane.doe@company.org

Incorrect:
- john@example (no domain)
- @example.com (no username)
- john @example.com (space)
```

### "Invalid phone number"

**Solutions:**
```
Accepted formats:
- (555) 123-4567
- 555-123-4567
- 5551234567

Tips:
- Remove country code (+1)
- Use 10 digits only
- Hyphens and parentheses are optional
```

### Form Doesn't Save

**Symptoms:**
- Click "Save" but nothing happens
- Form resets or shows same errors
- Data not persisted

**Solutions:**
```
1. Disable browser extensions (ad blockers)
2. Try different browser (Chrome, Firefox, Safari)
3. Clear browser cache
4. Check internet connection
5. Contact admin with screenshot
```

---

## Search Issues

### Customer Search Not Working

**Symptoms:**
- Search returns no results
- Search is slow
- Wrong customers appear

**Solutions:**
```
1. Type at least 3 characters
2. Check spelling
3. Try partial name (e.g., "john" instead of "john doe yachts")
4. Clear search and try again
5. Refresh page
```

### Search Returns Too Many Results

**Solutions:**
```
1. Be more specific in search terms
2. Use full customer name
3. Include unique identifiers
4. Use advanced filters (if available)
```

---

## Work Order Issues

### Cannot Save Work Order

**Symptoms:**
- "Cannot save work order" error
- Validation errors
- Form won't submit

**Solutions:**
```
1. Check all required fields are filled:
   - Customer name
   - At least one item
   - Valid dates (if entered)

2. Verify customer exists:
   - Search for customer first
   - Create customer if doesn't exist

3. Check items:
   - Description not empty
   - Quantity is a number
   - No special characters in fields

4. Try again:
   - Clear form and start over
   - Refresh page
   - Try different browser
```

### Cannot Find Work Order

**Symptoms:**
- Work order doesn't appear in list
- Search returns no results
- "Work order not found"

**Solutions:**
```
1. Check work order number is correct
2. Use search function with customer name
3. Filter by status (pending, in progress, completed)
4. Check if work order was deleted
5. Contact administrator to verify
```

---

## Browser-Specific Issues

### Chrome

**Cookies not persisting**
```
1. Settings > Privacy and security > Cookies
2. Allow cookies from application domain
3. Disable "Block third-party cookies" if needed
```

**PDF downloads fail**
```
1. Settings > Downloads
2. Turn off "Ask where to save each file"
3. Clear download history
```

### Firefox

**Session expires immediately**
```
1. Options > Privacy & Security
2. History: Use custom settings
3. Accept cookies from sites
4. Keep until: they expire
```

### Safari

**Forms don't submit**
```
1. Safari > Preferences > Privacy
2. Uncheck "Prevent cross-site tracking"
3. Cookies: Allow from websites I visit
```

---

## Mobile Device Issues

### iPhone/iPad

**Cannot upload files**
```
1. Use "Files" app integration
2. Or email file to yourself and download
3. Then upload from Downloads folder
```

**Form inputs don't work**
```
1. Use Safari browser (not Chrome)
2. Enable JavaScript in Settings
3. Disable content blockers for this site
```

### Android

**PDF doesn't download**
```
1. Enable "Download without notification"
2. Check Download folder
3. Use Chrome or Firefox browser
```

**Forms are hard to use**
```
1. Use landscape mode for better layout
2. Zoom in on form fields
3. Use desktop site mode (3-dot menu > Desktop site)
```

---

## Getting Help

### Before Contacting Support

Gather this information:
- [ ] What were you trying to do?
- [ ] What did you expect to happen?
- [ ] What actually happened?
- [ ] Screenshot of error (if any)
- [ ] Browser and version
- [ ] Date and time of issue
- [ ] Username (don't include password)

### How to Get Help

**For Users:**
```
1. Check this troubleshooting guide
2. Check FAQ (docs/reference/faq.md)
3. Contact your system administrator
4. Email: support@yourdomain.com
```

**For Administrators:**
```
1. Check operations runbook (docs/deployment/operations-runbook.md)
2. Review application logs
3. Check GitHub issues
4. Create new issue with details
```

---

## Quick Reference

### Error Code Meanings

| Code | Meaning | Common Cause |
|------|---------|--------------|
| 400 | Bad Request | Invalid form data |
| 401 | Unauthorized | Not logged in |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 500 | Internal Server Error | Application bug |
| 502 | Bad Gateway | Server overloaded |
| 503 | Service Unavailable | Server down/restarting |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+S | Save form (if supported) |
| Ctrl+R | Refresh page |
| F5 | Refresh page |
| Ctrl+Shift+Delete | Clear browser cache |

---

## Last Updated

This troubleshooting guide was last updated on 2025-11-16.
