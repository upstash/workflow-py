#!/bin/bash

set -e

# Check if an argument is provided
if [ $# -eq 0 ]; then
    echo "Please provide a path argument."
    echo "Usage: $0 <path>"
    exit 1
fi

# store project argument
project_arg="$1"

# create dist
cd ..
pip install -e .

# install dependencies
cd examples/$project_arg
pip install -r requirements.txt
if [ "$project_arg" == "nextjs-fastapi" ]; then
    npm install
fi

# Start ngrok and capture the public URL
ngrok http localhost:8000 --log=stdout > ngrok.log &
NGROK_PID=$!
sleep 5  # Allow some time for ngrok to start

# Extract the ngrok URL from the logs
ngrok_url=$(grep -o 'url=https://[a-zA-Z0-9.-]*\.ngrok-free\.app' ngrok.log | cut -d '=' -f 2 | head -n1)
export UPSTASH_WORKFLOW_URL=$ngrok_url

final_path=$ngrok_url
echo "Setup complete. Full URL: $final_path"
echo "ngrok is running. Press Ctrl+C to stop it."

# Start the server
if [ "$project_arg" == "fastapi" ]; then
    uvicorn main:app --reload
elif [ "$project_arg" == "flask" ]; then
    flask --app main run -p 8000
elif [ "$project_arg" == "nextjs-fastapi" ]; then
    npm run dev
else
    echo "Invalid project argument."
    exit 1
fi

# Wait for ngrok to be manually stopped
wait $NGROK_PID
