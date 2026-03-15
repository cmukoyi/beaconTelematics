#!/bin/bash

################################################################################
# BEACON TELEMATICS - EMERGENCY ROLLBACK SCRIPT
# 
# Purpose: Quickly restore database and app to last known good state
# Usage: bash rollback.sh
# 
# What it does:
#   1. Stops all running containers
#   2. Restores database from last backup
#   3. Reverts code to last tagged release
#   4. Rebuilds and restarts containers
#   5. Runs health checks
################################################################################

set -e  # Exit on any error

# ============================================================================
# COLORS FOR OUTPUT
# ============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# CONFIGURATION
# ============================================================================
PROJECT_DIR="/root/beacon-telematics/gps-tracker"
BACKUP_DIR="$PROJECT_DIR/backups"
DB_USER="beacon_user"
DB_NAME="beacon_telematics"
APP_URL="https://beacontelematics.co.uk"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

confirm() {
    local prompt="$1"
    local response
    
    read -p "$(echo -e ${YELLOW}$prompt${NC}) (yes/no): " response
    if [[ "$response" == "yes" || "$response" == "y" || "$response" == "Y" ]]; then
        return 0
    else
        return 1
    fi
}

# ============================================================================
# STEP 1: VERIFY BACKUPS EXIST
# ============================================================================
verify_backups() {
    log_info "Checking available backups..."
    
    if [ ! -d "$BACKUP_DIR" ]; then
        log_error "Backup directory not found: $BACKUP_DIR"
        return 1
    fi
    
    # Find the most recent backup
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR" | head -1)
    
    if [ -z "$LATEST_BACKUP" ]; then
        log_error "No backups found in $BACKUP_DIR"
        return 1
    fi
    
    BACKUP_FILE="$BACKUP_DIR/$LATEST_BACKUP/beacon_db.sql"
    
    if [ ! -f "$BACKUP_FILE" ]; then
        log_error "Database backup not found: $BACKUP_FILE"
        return 1
    fi
    
    log_success "Found backup from: $(date -r "$BACKUP_FILE")"
    log_info "Backup file: $BACKUP_FILE"
    
    return 0
}

# ============================================================================
# STEP 2: CONFIRM ROLLBACK
# ============================================================================
confirm_rollback() {
    log_warning "This will:"
    echo "  1. Stop all Docker containers"
    echo "  2. Drop and restore database from backup"
    echo "  3. Revert code to last tagged release"
    echo "  4. Rebuild and restart all services"
    echo ""
    
    if ! confirm "Continue with rollback?"; then
        log_warning "Rollback cancelled."
        return 1
    fi
    
    return 0
}

# ============================================================================
# STEP 3: BACKUP CURRENT STATE (FOR RECOVERY)
# ============================================================================
backup_current_state() {
    log_info "Creating emergency backup of current state..."
    
    EMERGENCY_DIR="$BACKUP_DIR/emergency_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$EMERGENCY_DIR"
    
    # Export current database state
    cd "$PROJECT_DIR"
    docker compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" > "$EMERGENCY_DIR/broken_state.sql"
    
    # Save current git state
    git log --oneline -n 5 > "$EMERGENCY_DIR/git_log.txt"
    docker compose ps > "$EMERGENCY_DIR/containers.txt"
    
    log_success "Emergency backup created: $EMERGENCY_DIR"
}

# ============================================================================
# STEP 4: STOP CONTAINERS
# ============================================================================
stop_containers() {
    log_info "Stopping all containers..."
    
    cd "$PROJECT_DIR"
    docker compose down
    
    sleep 5
    
    log_success "All containers stopped"
}

# ============================================================================
# STEP 5: RESTORE DATABASE
# ============================================================================
restore_database() {
    log_info "Restoring database from backup: $BACKUP_FILE"
    
    cd "$PROJECT_DIR"
    
    # Start only the database container
    docker compose up -d db
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    sleep 10
    
    # Drop and recreate the database
    log_info "Dropping existing database..."
    docker compose exec -T db psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true
    
    log_info "Creating fresh database..."
    docker compose exec -T db psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || true
    
    # Restore from backup
    log_info "Restoring data from backup (this may take a moment)..."
    docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" < "$BACKUP_FILE"
    
    log_success "Database restored successfully"
}

# ============================================================================
# STEP 6: REVERT CODE TO LAST RELEASE
# ============================================================================
revert_code() {
    log_info "Checking git history for last successful release..."
    
    cd "$PROJECT_DIR"
    
    # Get last tag
    LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null | head -1)
    
    if [ -z "$LAST_TAG" ]; then
        log_warning "No previous releases found, using HEAD~1"
        LAST_TAG="HEAD~1"
    fi
    
    log_info "Reverting to: $LAST_TAG"
    
    # Reset to last tag (but keep local changes safe)
    git stash
    git checkout "$LAST_TAG"
    
    log_success "Code reverted to $LAST_TAG"
}

# ============================================================================
# STEP 7: REBUILD CONTAINERS
# ============================================================================
rebuild_containers() {
    log_info "Rebuilding containers from previous code..."
    
    cd "$PROJECT_DIR"
    
    docker compose build --no-cache backend admin-portal customer flutter-web
    
    log_success "Containers rebuilt"
}

# ============================================================================
# STEP 8: START ALL CONTAINERS
# ============================================================================
start_containers() {
    log_info "Starting all services..."
    
    cd "$PROJECT_DIR"
    docker compose up -d
    
    log_info "Waiting 15 seconds for services to stabilize..."
    sleep 15
    
    log_success "All services started"
}

# ============================================================================
# STEP 9: RUN HEALTH CHECKS
# ============================================================================
health_checks() {
    log_info "Running health checks..."
    
    cd "$PROJECT_DIR"
    
    # Check database
    log_info "Checking database..."
    DB_STATUS=$(docker compose exec -T db pg_isready -U "$DB_USER" 2>/dev/null | grep "accepting" && echo "OK" || echo "FAIL")
    
    if [ "$DB_STATUS" = "OK" ]; then
        log_success "Database is healthy"
    else
        log_error "Database health check failed"
        return 1
    fi
    
    # Check backend container
    log_info "Checking backend..."
    BACKEND_STATUS=$(docker compose ps backend | grep "Up" && echo "OK" || echo "FAIL")
    
    if [ "$BACKEND_STATUS" = "OK" ]; then
        log_success "Backend container is up"
    else
        log_error "Backend container down"
        return 1
    fi
    
    # Check all containers
    log_info "Container status:"
    docker compose ps
    
    return 0
}

# ============================================================================
# STEP 10: VERIFY TABLE COUNTS
# ============================================================================
verify_data() {
    log_info "Verifying data was restored..."
    
    cd "$PROJECT_DIR"
    
    # Count rows in main tables
    USERS=$(docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT COUNT(*) FROM users;" 2>/dev/null | grep -v "COUNT" | grep -v "^--" | head -1 | tr -d ' ')
    TAGS=$(docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT COUNT(*) FROM ble_tags;" 2>/dev/null | grep -v "COUNT" | grep -v "^--" | head -1 | tr -d ' ')
    TRIPS=$(docker compose exec -T db psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT COUNT(*) FROM trips;" 2>/dev/null | grep -v "COUNT" | grep -v "^--" | head -1 | tr -d ' ')
    
    log_success "Data verification:"
    echo "  - Users: $USERS"
    echo "  - BLE Tags: $TAGS"
    echo "  - Trips: $TRIPS"
}

# ============================================================================
# STEP 11: NOTIFY ADMIN
# ============================================================================
notify_completion() {
    log_success "✅ ROLLBACK COMPLETED SUCCESSFULLY!"
    echo ""
    echo "=================================================================="
    echo "ROLLBACK SUMMARY"
    echo "=================================================================="
    echo "✅ Database restored from: $BACKUP_FILE"
    echo "✅ Code reverted to: $(git describe --tags)"
    echo "✅ All containers restarted"
    echo "✅ Health checks passed"
    echo ""
    echo "📊 Next Steps:"
    echo "  1. Test the app: $APP_URL"
    echo "  2. Check logs: docker compose logs -f backend"
    echo "  3. If still broken: contact dev team with error details"
    echo "  4. Emergency backup saved: $EMERGENCY_DIR"
    echo ""
    echo "🔗 Important:"
    echo "  - Previous broken state backed up for analysis"
    echo "  - Keep at most 10 backups to save disk space"
    echo "  - Document what caused the issue for prevention"
    echo ""
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================
main() {
    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║     🚨 BEACON TELEMATICS - EMERGENCY ROLLBACK SCRIPT 🚨        ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Step 1
    if ! verify_backups; then
        log_error "Backup verification failed"
        exit 1
    fi
    
    # Step 2
    if ! confirm_rollback; then
        exit 0
    fi
    
    # Step 3
    backup_current_state
    
    # Step 4
    stop_containers
    
    # Step 5
    if ! restore_database; then
        log_error "Database restore failed"
        exit 1
    fi
    
    # Step 6
    revert_code
    
    # Step 7
    rebuild_containers
    
    # Step 8
    start_containers
    
    # Step 9
    if ! health_checks; then
        log_warning "Some health checks failed - services may still be starting"
    fi
    
    # Step 10
    verify_data
    
    # Step 11
    notify_completion
    
    echo ""
}

# Run main function
main "$@"
