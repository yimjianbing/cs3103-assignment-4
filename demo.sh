#!/bin/bash
# Simple demo script to test H-UDP

echo "Starting H-UDP Demo"
echo "==================="
echo ""
echo "Starting receiver in background..."
python recvapp.py --bind-port 19999 > receiver.log 2>&1 &
RECV_PID=$!

sleep 1

echo "Starting sender for 5 seconds..."
python senderapp.py --server-port 19999 --pps 20 --reliable-ratio 0.6 --duration-sec 5 --loss 0.05

echo ""
echo "Waiting for final packets..."
sleep 2

echo "Stopping receiver..."
kill $RECV_PID 2>/dev/null

# Wait for receiver to fully terminate
wait $RECV_PID 2>/dev/null

echo ""
echo "==================="
echo "Demo complete!"
echo ""
echo "Receiver log (last 30 packet deliveries):"
grep "DELIVER\|EVENT" receiver.log | tail -30

rm -f receiver.log

