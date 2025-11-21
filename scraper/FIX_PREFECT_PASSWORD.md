# Fix Prefect Server Password Configuration

## Problem

Prefect server is restarting because it can't authenticate to PostgreSQL. The password is in an environment variable, but Prefect isn't reading it properly.

## Solution

The `docker-compose.yml` has been updated to check for `POSTGRES_PASSWORD` environment variable first, then fall back to the secret file.

## Quick Fix

### Option 1: Set Environment Variable (Recommended)

**Windows PowerShell:**
```powershell
# Set the password environment variable
$env:POSTGRES_PASSWORD = "your_password_here"

# Restart Prefect server
docker-compose restart prefect-server
```

**Linux/Mac:**
```bash
# Set the password environment variable
export POSTGRES_PASSWORD="your_password_here"

# Restart Prefect server
docker-compose restart prefect-server
```

**Persistent (Windows):**
```powershell
# Set user-level environment variable (persists across sessions)
[System.Environment]::SetEnvironmentVariable("POSTGRES_PASSWORD", "your_password_here", "User")

# Restart PowerShell, then restart Prefect server
docker-compose restart prefect-server
```

### Option 2: Use Secret File

Ensure the secret file exists:
```bash
# Check if file exists
cat ../ops/secrets/postgres_password.txt

# If it doesn't exist, create it:
echo "your_password_here" > ../ops/secrets/postgres_password.txt
```

Then restart:
```bash
docker-compose restart prefect-server
```

## Verify Fix

1. **Check Prefect server logs:**
   ```bash
   docker logs bpo-prefect-server -f
   ```

2. **Look for success message:**
   ```
   Using database: postgresql://bpo_user:***@postgres:5432/bpo_intelligence
   Application startup complete.
   ```

3. **Check server status:**
   ```bash
   docker ps | grep prefect
   # Should show "Up" status (not "Restarting")
   ```

4. **Test API:**
   ```bash
   curl http://localhost:4200/health
   # Should return 200 OK
   ```

## Using the Fix Script

**PowerShell (Windows):**
```powershell
cd scraper
.\fix_prefect_server.ps1
```

**Bash (Linux/Mac):**
```bash
cd scraper
chmod +x fix_prefect_server.sh
./fix_prefect_server.sh
```

## Configuration Details

The updated `docker-compose.yml` now checks in this order:

1. **Environment Variable**: `POSTGRES_PASSWORD`
2. **Secret File**: `/run/secrets/postgres_password`
3. **Error**: If neither is found, the container will exit with an error

This ensures Prefect can always see the password, whether it's in an environment variable or secret file.

## Troubleshooting

### Password Still Not Working

1. **Verify password matches PostgreSQL:**
   ```bash
   # Connect to Postgres with the password
   docker exec -it bpo-postgres psql -U bpo_user -d bpo_intelligence
   # Enter password when prompted
   ```

2. **Check environment variable is set:**
   ```powershell
   # PowerShell
   echo $env:POSTGRES_PASSWORD
   
   # Bash
   echo $POSTGRES_PASSWORD
   ```

3. **Check secret file content:**
   ```bash
   # From host
   cat ../ops/secrets/postgres_password.txt
   
   # From container
   docker exec bpo-prefect-server cat /run/secrets/postgres_password
   ```

4. **View detailed logs:**
   ```bash
   docker logs bpo-prefect-server --tail 50
   ```

### Container Still Restarting

If the container is still restarting after setting the password:

1. **Stop the container:**
   ```bash
   docker stop bpo-prefect-server
   ```

2. **Remove and recreate:**
   ```bash
   docker-compose rm -f prefect-server
   docker-compose up -d prefect-server
   ```

3. **Check logs again:**
   ```bash
   docker logs bpo-prefect-server -f
   ```

