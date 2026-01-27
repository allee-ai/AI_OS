#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")"

echo "🧹 Cleaning SQLite temp files..."
find . -name "*.db-shm" -type f -delete
find . -name "*.db-wal" -type f -delete

echo "📦 Staging all changes..."
git add .

# Check if a message was provided as an argument
MSG="$1"

# If no argument, ask for input
if [ -z "$MSG" ]; then
    echo "💬 Enter commit message (Press Enter for 'update'): "
    read input_msg
    if [ -z "$input_msg" ]; then
        MSG="update"
    else
        MSG="$input_msg"
    fi
fi

echo "📝 Committing with message: '$MSG'"
git commit -m "$MSG"

echo "rocket Pushing to remote..."
git push

echo ""
echo "Finished! Closing..."
sleep 1
osascript -e 'tell application "Terminal" to close front window' & exit
