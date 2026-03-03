#!/bin/bash
set -euo pipefail

# Update wrapper on a running VM without recreating it.
#
# Usage:
#   ./push.sh                    # Uses default VM name
#   ./push.sh my-custom-vm       # Specify VM name

VM_NAME="${1:-golden-config-vertex}"
ZONE="us-central1-a"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Pushing wrapper update to $VM_NAME..."

# Copy the updated wrapper
gcloud compute scp "$SCRIPT_DIR/wrapper_vertex.py" "$VM_NAME":~/ --zone="$ZONE"

# Kill old process and restart
gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="
    pkill -f wrapper_vertex.py || true
    sleep 1
    nohup ~/start_golden_config.sh > ~/service.log 2>&1 &
    sleep 2
    echo 'Service restarted.'
"

# Quick health check
EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" \
    --zone="$ZONE" \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "Health check:"
curl -s "http://$EXTERNAL_IP:5008/health" | python3 -m json.tool || echo "(Service starting...)"
