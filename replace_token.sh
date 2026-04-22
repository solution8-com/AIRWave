#!/bin/bash
SCRIPT_NAME=$(basename "$0")
echo "Searching for files containing 'GITHUB_TOKEN'..."
FILES=$(grep -rl "GITHUB_TOKEN" . | grep -v "$SCRIPT_NAME")

if [ -z "$FILES" ]; then
    echo "No matching files found."
    exit 0
fi

echo "Files to be updated:"
echo "$FILES"

for FILE in $FILES; do
    echo "Updating $FILE..."
    sed -i '' 's/GITHUB_TOKEN/GUB_TOKEN/g' "$FILE"
done

echo "Replacement complete."
