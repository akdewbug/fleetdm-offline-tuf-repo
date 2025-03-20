import os
import json
import hashlib
import requests
import pexpect

# Configuration variables
TUF_REPO_URL = "https://updates.fleetdm.com"  # TUF repository URL
SOURCE_CHANNEL = "stable"  # Source channel (e.g., "stable", "beta", "dev")
TARGET_CHANNEL = "stable"  # Target channel to push updates to
DOWNLOAD_DIR = "/data/fleetd"  # Staging area for downloads
FLEETCTL_WORKING_DIR = "/data/files/fleet-update"  # Directory where fleetctl runs
LOCAL_REPO_METADATA = os.path.join(FLEETCTL_WORKING_DIR, "repository", "targets.json")  # Local TUF metadata
TARGETS_JSON_URL = f"{TUF_REPO_URL}/targets.json"  # TUF metadata file
PASSPHRASE_FILE = "/root/fleet/passphrases.txt"  # Path to passphrase file
DEBUG_MODE = False  # Enable for verbose logging

# Ensure necessary directories exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(FLEETCTL_WORKING_DIR, exist_ok=True)

# Read passphrases from /root/fleet/passphrases.txt
def read_passphrases():
    """Reads passphrases from /root/fleet/passphrases.txt"""
    passphrases = {"TIMESTAMP_PASSPHRASE": "", "SNAPSHOT_PASSPHRASE": "", "TARGET_PASSPHRASE": ""}
    try:
        with open(PASSPHRASE_FILE, "r") as file:
            for line in file:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    passphrases[key.strip()] = value.strip()
    except FileNotFoundError:
        print("❌ Error: Passphrase file not found at /root/fleet/passphrases.txt")
        exit(1)
    except Exception as e:
        print(f"❌ Error reading passphrases: {e}")
        exit(1)
    return passphrases

# Load passphrases
passphrases = read_passphrases()
TIMESTAMP_PASSPHRASE = passphrases.get("TIMESTAMP_PASSPHRASE", "")
SNAPSHOT_PASSPHRASE = passphrases.get("SNAPSHOT_PASSPHRASE", "")
TARGET_PASSPHRASE = passphrases.get("TARGET_PASSPHRASE", "")

def debug_log(message):
    """ Logs debug messages if debug mode is enabled. """
    if DEBUG_MODE:
        print(f"[DEBUG] {message}")

def get_remote_targets():
    """ Fetches and filters targets.json based on SOURCE_CHANNEL. """
    debug_log(f"Fetching targets.json from {TARGETS_JSON_URL}...")

    try:
        response = requests.get(TARGETS_JSON_URL)
        response.raise_for_status()
        targets_json = response.json()

        targets = targets_json.get("signed", {}).get("targets", {})
        debug_log(f"Total targets found: {len(targets)}")

        filtered_targets = {name: info for name, info in targets.items() if SOURCE_CHANNEL in name}
        debug_log(f"Filtered {len(filtered_targets)} targets for channel '{SOURCE_CHANNEL}'.")

        return filtered_targets

    except requests.RequestException as e:
        print(f"❌ Error fetching targets.json: {e}")
        return {}

def compute_file_hash(file_path):
    """ Computes the SHA512 hash of a given file. """
    hash_sha512 = hashlib.sha512()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha512.update(chunk)
        computed_hash = hash_sha512.hexdigest()
        debug_log(f"Computed SHA512 hash for {file_path}: {computed_hash}")
        return computed_hash
    except FileNotFoundError:
        debug_log(f"File {file_path} not found. Assuming missing.")
        return None

def download_target(target_name, expected_hash):
    """ Downloads a target file manually using requests if it is missing or outdated. """
    remote_url = f"{TUF_REPO_URL}/targets/{target_name}"
    local_path = os.path.join(DOWNLOAD_DIR, target_name)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    # Check if file already exists and matches expected SHA512 hash
    local_hash = compute_file_hash(local_path)
    if local_hash == expected_hash:
        debug_log(f"✅ {target_name} is up-to-date. Skipping download.")
        return local_path

    debug_log(f"⬇️ Downloading {target_name} from {remote_url}...")

    try:
        response = requests.get(remote_url, stream=True)
        response.raise_for_status()

        with open(local_path, "wb") as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

        # Verify SHA512 hash after download
        new_hash = compute_file_hash(local_path)
        if new_hash != expected_hash:
            print(f"❌ SHA512 mismatch for {target_name}. Deleting corrupted file.")
            os.remove(local_path)
            return None

        debug_log(f"✅ Successfully downloaded: {target_name} -> {local_path}")
        return local_path

    except requests.RequestException as e:
        print(f"❌ Failed to download {target_name}: {e}")
        return None

def is_version_already_in_repo(target_name, version):
    """ Checks if the given version is already in the FleetCTL repository. """
    if not os.path.exists(LOCAL_REPO_METADATA):
        return False

    try:
        with open(LOCAL_REPO_METADATA, "r") as file:
            local_metadata = json.load(file)
            targets = local_metadata.get("signed", {}).get("targets", {})
            for existing_target, info in targets.items():
                if target_name in existing_target and info.get("custom", {}).get("version") == version:
                    debug_log(f"🔄 Version {version} of {target_name} already exists in the repo. Skipping update.")
                    return True
    except Exception as e:
        print(f"❌ Error reading local metadata: {e}")

    return False

def upload_to_target_channel(local_path, target_name, version):
    """ Pushes the file to the target repository using fleetctl with passphrases via pexpect. """
    if is_version_already_in_repo(target_name, version):
        return

    platform = target_name.split("/")[1]
    filename = target_name.split("/")[-1]
    name = target_name.split("/")[0]

    updates_args = [
        "fleetctl", "updates", "add",
        "--target", local_path,
        "--platform", platform,
        "--name", name,
        "--version", version,
        "-t", TARGET_CHANNEL
    ]

    debug_log(f"Executing FleetCTL command in {FLEETCTL_WORKING_DIR}: {' '.join(updates_args)}")

    try:
        child = pexpect.spawn(" ".join(updates_args), cwd=FLEETCTL_WORKING_DIR, timeout=60)

        child.expect("Enter timestamp key passphrase:")
        child.sendline(TIMESTAMP_PASSPHRASE)

        child.expect("Enter snapshot key passphrase:")
        child.sendline(SNAPSHOT_PASSPHRASE)

        child.expect("Enter targets key passphrase:")
        child.sendline(TARGET_PASSPHRASE)

        child.wait()
        debug_log(f"✅ Successfully uploaded {filename} to {TARGET_CHANNEL}.")

    except pexpect.exceptions.EOF:
        print(f"❌ Failed to upload {filename}: Unexpected EOF in output")
    except pexpect.exceptions.TIMEOUT:
        print(f"❌ Failed to upload {filename}: Command timed out")

def mirror_repository():
    remote_targets = get_remote_targets()

    if not remote_targets:
        print("⚠️ No targets found in the source channel.")
        return

    for target_name, info in remote_targets.items():
        version = info["custom"]["version"]
        expected_hash = info["hashes"]["sha512"]

        local_path = download_target(target_name, expected_hash)
        if local_path:
            upload_to_target_channel(local_path, target_name, version)

if __name__ == "__main__":
    mirror_repository()
