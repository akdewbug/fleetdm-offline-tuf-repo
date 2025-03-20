# FleetCTL Mirror Setup Instructions

This guide provides step-by-step instructions to initialize a `fleetctl` repository, manage passphrases, run mirroring and timestamp scripts, and set up Nginx with SSL to host the repository.

## Prerequisites

- Ensure you have the following installed:
  - `fleetctl` (Fleet Device Management CLI)
  - Python 3.x
  - `pexpect` Python library (`pip install pexpect`)
  - `requests` Python library (`pip install requests`)
  - Nginx
  - `certbot` (for SSL certificates)
  - `cron` (for scheduling tasks)

- Root privileges may be required for some steps (e.g., directory creation, Nginx setup).

- The Python scripts `fleet-tuf-mirror.py` and `fleet-updatetime.py` should be available in a `scripts` directory.

---

## Step 1: Create Directories and Initialize a FleetCTL Repository

1. **Create Required Directories**:
   Create the working directory for `fleetctl` and the staging directory for downloads:
   ```bash
   sudo mkdir -p /data/files/fleet-update
   sudo mkdir -p /data/fleetd
   ```
   Set appropriate permissions (e.g., for the current user or a specific service account):
   ```bash
   sudo chown $USER:$USER /data/files/fleet-update /data/fleetd
   ```

2. **Initialize the Repository**:
   Navigate to the working directory and initialize a `fleetctl` updates repository:
   ```bash
   cd /data/files/fleet-update
   fleetctl updates init
   ```
   This creates a TUF (The Update Framework) repository structure in `/data/files/fleet-update`.

---

## Step 2: Add Passphrases to `passphrases.txt`

1. **Create the Passphrases File**:
   Create a file named `passphrases.txt` in the `root/fleet/` directory to store the required passphrases:
   ```bash
   mkdir -p /data/files/fleet-update/root/fleet
   nano /data/files/fleet-update/root/fleet/passphrases.txt
   ```

2. **Add Passphrases**:
   Add the following lines to `root/fleet/passphrases.txt`, replacing the placeholder values with your actual passphrases:
   ```
   TIMESTAMP_PASSPHRASE=your_timestamp_passphrase
   SNAPSHOT_PASSPHRASE=your_snapshot_passphrase
   TARGET_PASSPHRASE=your_target_passphrase
   ```

3. **Secure the File**:
   Restrict permissions to prevent unauthorized access:
   ```bash
   chmod 600 /data/files/fleet-update/root/fleet/passphrases.txt
   ```

---

## Step 3: Remove `root.json` After Key Generation

1. **Generate Keys** (if not already done):
   During `fleetctl updates init`, keys are generated in the `root` directory. If you need to regenerate them, consult the `fleetctl` documentation.

2. **Backup Keys** (if not already done):
    ```bash
    cp -R /data/files/fleet-update/ /root/fleet-update-backup
    ```
3. **Remove `root.json`**:
   After generating all necessary keys and ensuring they are backed up, remove the `root.json` file from the `keys` directory:
   ```bash
   rm keys/root.json
   ```
   **Note**: Ensure you have a backup of the keys before removing `root.json`.

---

## Step 4: Set Up and Run the Mirroring and Timestamp Scripts

1. **Prepare the Scripts Directory**:
   Ensure the Python scripts are placed in a `scripts` directory:
   ```bash
   mkdir -p scripts
   ```
   - `fleet-tuf-mirror.py`: Mirrors the TUF repository.
   - `fleet-updatetime.py`: Updates the timestamp.

2. **Copy the Scripts**:
   Place `fleet-tuf-mirror.py` and `fleet-updatetime.py` in the `scripts` directory. Ensure they are configured to read passphrases from `/data/files/fleet-update/root/fleet/passphrases.txt`.

3. **Make Scripts Executable**:
   ```bash
   chmod +x scripts/fleet-tuf-mirror.py
   chmod +x scripts/fleet-updatetime.py
   ```

4. **Test the Scripts**:
   Run each script manually to ensure they work:
   ```bash
   python3 scripts/fleet-tuf-mirror.py
   python3 scripts/fleet-updatetime.py
   ```

5. **Schedule with Cron**:
   - **Daily Run for `fleet-tuf-mirror.py`**:
     Open the cron table for editing:
     ```bash
     crontab -e
     ```
     Add the following line to run daily at midnight (00:00):
     ```
     0 0 * * * /usr/bin/python3 /path/to/scripts/fleet-tuf-mirror.py >> /var/log/fleet-tuf-mirror.log 2>&1
     ```
     Replace `/path/to/scripts/` with the absolute path to your `scripts` directory.

   - **Weekly Run for `fleet-updatetime.py`**:
     Add the following line to run weekly on Monday at 1:00 AM:
     ```
     0 1 * * 1 /usr/bin/python3 /path/to/scripts/fleet-updatetime.py >> /var/log/fleet-updatetime.log 2>&1
     ```
     Replace `/path/to/scripts/` with the absolute path to your `scripts` directory.

   - **Create Log Files** (optional):
     ```bash
     sudo touch /var/log/fleet-tuf-mirror.log /var/log/fleet-updatetime.log
     sudo chmod 664 /var/log/fleet-tuf-mirror.log /var/log/fleet-updatetime.log
     ```

---

## Step 5: Set Up Nginx with SSL

1. **Install Nginx** (if not already installed):
   On Ubuntu/Debian:
   ```bash
   sudo apt update
   sudo apt install nginx
   ```

2. **Configure Nginx**:
   Create a new Nginx configuration file:
   ```bash
   sudo nano /etc/nginx/sites-available/fleet-update
   ```
   Add the following configuration, adjusting the `server_name` and paths as needed:
   ```
   server {
       listen 80;
       server_name yourdomain.com;

       # Redirect HTTP to HTTPS
       return 301 https://$host$request_uri;
   }

   server {
       listen 443 ssl;
       server_name yourdomain.com;

       ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

       root /data/files/fleet-update/repository;
       index index.html;

       location / {
           try_files $uri $uri/ =404;
       }
   }
   ```

3. **Enable the Configuration**:
   Link the configuration to `sites-enabled`:
   ```bash
   sudo ln -s /etc/nginx/sites-available/fleet-update /etc/nginx/sites-enabled/
   ```

4. **Obtain SSL Certificate**:
   Use `certbot` to set up SSL:
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d yourdomain.com
   ```
   Follow the prompts to configure SSL.

5. **Test and Reload Nginx**:
   Test the configuration and reload Nginx:
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

---

## Notes

- Replace `yourdomain.com` with your actual domain.
- Ensure the paths (`/data/files/fleet-update`, `/data/fleetd`) match your system setup.
- Back up all keys and passphrases securely before removing any files.
- The scripts `fleet-tuf-mirror.py` and `fleet-updatetime.py` must be configured to read passphrases from `/data/files/fleet-update/root/fleet/passphrases.txt`.
- Check the log files (`/var/log/fleet-tuf-mirror.log`, `/var/log/fleet-updatetime.log`) for debugging if issues arise.

You’re now set up to mirror the FleetCTL repository daily and update timestamps weekly, serving it over HTTPS!
