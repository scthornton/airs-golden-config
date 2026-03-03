#!/bin/bash
set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
VM_NAME="golden-config-vertex"
ZONE="us-central1-a"
MACHINE_TYPE="e2-medium"
PORT=5008
GCP_PROJECT="${GCP_PROJECT:?Set GCP_PROJECT before deploying}"

# These must be set in your shell before running
: "${PANW_AI_SEC_API_KEY:?Set PANW_AI_SEC_API_KEY before deploying}"
: "${OPENAI_API_KEY:?Set OPENAI_API_KEY before deploying}"
: "${PRISMA_AIRS_PROFILE:=redteamtest}"
: "${LLM_MODEL:=gpt-4o-mini}"

echo "========================================"
echo "Golden Config — AIRS Hard-Block Wrapper"
echo "========================================"
echo "VM:       $VM_NAME"
echo "Zone:     $ZONE"
echo "Project:  $GCP_PROJECT"
echo "Profile:  $PRISMA_AIRS_PROFILE"
echo "Model:    $LLM_MODEL"
echo ""

# ── Step 1: Create VM ─────────────────────────────────────────────────────────
echo "[1/5] Creating GCP VM..."
gcloud compute instances create "$VM_NAME" \
    --zone="$ZONE" \
    --machine-type="$MACHINE_TYPE" \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --boot-disk-size=10GB \
    --tags=golden-config \
    --metadata=startup-script='#!/bin/bash
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv > /dev/null
python3 -m venv /opt/golden-config
/opt/golden-config/bin/pip install flask requests --quiet
echo "Startup complete" > /tmp/startup-done
'

# ── Step 2: Wait for startup ──────────────────────────────────────────────────
echo "[2/5] Waiting for VM startup (up to 90s)..."
for i in $(seq 1 18); do
    if gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="test -f /tmp/startup-done" 2>/dev/null; then
        echo "  VM ready."
        break
    fi
    sleep 5
done

# ── Step 3: Copy wrapper ──────────────────────────────────────────────────────
echo "[3/5] Copying wrapper to VM..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
gcloud compute scp "$SCRIPT_DIR/wrapper_vertex.py" "$VM_NAME":~/ --zone="$ZONE"

# ── Step 4: Create service script with env vars ───────────────────────────────
echo "[4/5] Creating service script on VM..."
TMPSCRIPT=$(mktemp)
cat > "$TMPSCRIPT" << EOF
#!/bin/bash
export PANW_AI_SEC_API_KEY="${PANW_AI_SEC_API_KEY}"
export PRISMA_AIRS_PROFILE="${PRISMA_AIRS_PROFILE}"
export OPENAI_API_KEY="${OPENAI_API_KEY}"
export LLM_MODEL="${LLM_MODEL}"

exec /opt/golden-config/bin/python3 -u ~/wrapper_vertex.py
EOF

gcloud compute scp "$TMPSCRIPT" "$VM_NAME":~/start_golden_config.sh --zone="$ZONE"
gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="chmod +x ~/start_golden_config.sh"
rm -f "$TMPSCRIPT"

# ── Step 5: Start service ─────────────────────────────────────────────────────
echo "[5/5] Starting service..."
gcloud compute ssh "$VM_NAME" --zone="$ZONE" --command="nohup ~/start_golden_config.sh > ~/service.log 2>&1 & sleep 2"

# ── Firewall ──────────────────────────────────────────────────────────────────
echo ""
echo "Checking firewall rule..."
if ! gcloud compute firewall-rules describe allow-golden-config 2>/dev/null | grep -q "golden-config"; then
    echo "Creating firewall rule..."
    gcloud compute firewall-rules create allow-golden-config \
        --allow tcp:$PORT \
        --target-tags=golden-config \
        --source-ranges=0.0.0.0/0 \
        --description="Allow red team scanner access to golden-config wrapper"
else
    echo "  Firewall rule already exists."
fi

# ── Output ────────────────────────────────────────────────────────────────────
EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" \
    --zone="$ZONE" \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "========================================"
echo "Deployment Complete!"
echo "========================================"
echo "External IP: $EXTERNAL_IP"
echo "Endpoint:    http://$EXTERNAL_IP:$PORT/v1/chat/completions"
echo "Health:      http://$EXTERNAL_IP:$PORT/health"
echo "Debug:       http://$EXTERNAL_IP:$PORT/debug"
echo ""
echo "Mode:    HARD-BLOCK (attacks never reach the LLM)"
echo "Profile: $PRISMA_AIRS_PROFILE"
echo "Model:   $LLM_MODEL"
echo ""
echo "========================================"
echo "SCM Target Registration:"
echo "========================================"
echo "Target Name: Golden Config Red Team Target"
echo "Endpoint:    http://$EXTERNAL_IP:$PORT/v1/chat/completions"
echo ""
echo "Request Body:"
echo '{"messages":[{"role":"user","content":"{INPUT}"}],"max_tokens":1024}'
echo ""
echo "Response JSON Path:"
echo '{"choices":[{"message":{"content":"{RESPONSE}"}}]}'
echo ""
echo "========================================"
echo "Logs:  gcloud compute ssh $VM_NAME --zone=$ZONE --command='tail -f ~/service.log'"
echo "========================================"
