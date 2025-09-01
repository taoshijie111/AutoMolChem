#!/bin/bash

# Start the backend server
echo "Starting backend server..."
cd backend
npm start &
BACKEND_PID=$!

# Wait for backend to start
sleep 2

# Start the frontend development server
echo "Starting frontend development server..."
cd ..
npm run dev &
FRONTEND_PID=$!

echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "Frontend: http://0.0.0.0:5173 (externally accessible)"
echo "Backend:  http://0.0.0.0:3001 (externally accessible)"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for interrupt
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait