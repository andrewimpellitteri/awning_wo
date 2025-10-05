#!/bin/bash
# Remove .gitignore from hooks directory - EB tries to execute it as a script
rm -f /var/app/current/.platform/hooks/postdeploy/.gitignore
echo "Cleanup: Removed .gitignore from postdeploy hooks"
