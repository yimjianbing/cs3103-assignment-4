#!/bin/bash
# Simple demo script to test H-UDP

echo "Starting H-UDP Demo"
echo "==================="
echo ""
echo "Starting receiver in background..."
python recvapp.py --bind-port 19999  &
RECV_PID=$!

sleep 1

echo "Starting sender for 5 seconds..."
python senderapp.py --server-port 19999 --pps 20 --reliable-ratio 0.6 --duration-sec 5 

echo ""
echo "Waiting for final packets..."
sleep 2

echo "Stopping receiver..."

kill -INT $RECV_PID 2>/dev/null || true
sleep 1

if kill -0 $RECV_PID 2>/dev/null; then
  kill -TERM $RECV_PID 2>/dev/null || true
  sleep 1
fi

if kill -0 $RECV_PID 2>/dev/null; then
  kill -KILL $RECV_PID 2>/dev/null || true
fi

wait $RECV_PID 2>/dev/null || true

echo ""
echo "==================="
echo "Demo complete!"
echo ""

