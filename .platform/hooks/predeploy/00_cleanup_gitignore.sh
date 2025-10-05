#!/bin/bash
# Remove any .gitignore files from hooks directories that EB tries to execute
find /var/app/staging/.platform/hooks -name ".gitignore" -type f -delete 2>/dev/null || true
echo "Cleaned up .gitignore files from hooks directories"
