#!/bin/bash
# 🚨 BEACON TELEMATICS - FASTEST ROLLBACK (30 SECONDS)
# 
# One-liner for instant rollback when seconds matter
# Usage: bash emergency-rollback-30sec.sh
#
# ⚠️  WARNING: This is the ULTRA-FAST version with NO confirmations
#     Use this ONLY when app is completely broken and seconds count
#     Use deploy/rollback.sh for safer, step-by-step rollback

cd /root/beacon-telematics/gps-tracker || exit 1

echo "🚨 EMERGENCY ROLLBACK - STARTING..."

# Get latest backup
LATEST=$(ls -t backups/ | head -1)
BACKUP_FILE="backups/$LATEST/beacon_db.sql"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ No backup found at $BACKUP_FILE"
    exit 1
fi

echo "🔄 Step 1: Stopping containers..."
docker compose down -q

echo "🔄 Step 2: Restoring database..."
docker compose up -d db > /dev/null 2>&1
sleep 8
docker compose exec -T db psql -U beacon_user -c "DROP DATABASE beacon_telematics;" 2>/dev/null
docker compose exec -T db psql -U beacon_user -c "CREATE DATABASE beacon_telematics;" 2>/dev/null
docker compose exec -T db psql -U beacon_user -d beacon_telematics < "$BACKUP_FILE" 2>/dev/null

echo "🔄 Step 3: Reverting code to last release..."
git stash > /dev/null 2>&1
git checkout $(git describe --tags --abbrev=0 2>/dev/null || echo "HEAD~1") > /dev/null 2>&1

echo "🔄 Step 4: Restarting all services..."
docker compose up -d > /dev/null 2>&1
sleep 12

echo ""
echo "✅ ROLLBACK COMPLETE!"
echo ""
docker compose ps
echo ""
echo "🔗 Check app: https://beacontelematics.co.uk"
echo "📋 Full logs: docker compose logs -f backend"
echo ""
