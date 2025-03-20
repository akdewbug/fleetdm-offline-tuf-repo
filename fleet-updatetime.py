import os
import pexpect

FLEETCTL_WORKING_DIR = "/data/files/fleet-update"
PASSPHRASE_FILE = "/root/fleet/passphrases.txt"

# Read passphrases from /root/fleet/passphrases.txt
def read_passphrases():
    """Reads passphrases from /root/fleet/passphrases.txt"""
    passphrases = {}
    try:
        with open(PASSPHRASE_FILE, "r") as file:
            for line in file:
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

def run_fleetctl_timestamp():
    """Runs 'fleetctl updates timestamp' with automated passphrase entry."""
    print("🚀 Running 'fleetctl updates timestamp'...")

    try:
        # Start the FleetCTL process
        child = pexpect.spawn("fleetctl updates timestamp", cwd=FLEETCTL_WORKING_DIR, timeout=120, encoding="utf-8")

        # Enable logging for debugging
        log_file = open("/tmp/fleetctl_timestamp_debug.log", "w")
        child.logfile = log_file

        while True:
            index = child.expect_exact([
                "Enter timestamp key passphrase:",
                "Enter snapshot key passphrase:",
                "Enter targets key passphrase:",
                pexpect.EOF,
                pexpect.TIMEOUT
            ], timeout=10)

            if index == 0:
                print("🔑 Entering TIMESTAMP passphrase...")
                child.sendline(TIMESTAMP_PASSPHRASE + "\r")  # Ensure carriage return is sent

            elif index == 3:  # EOF (Process completed)
                print("✅ FleetCTL timestamp update completed successfully.")
                break

            elif index == 4:  # Timeout
                print("⚠️ Timeout while waiting for FleetCTL prompt. Check logs for details.")
                break

        child.wait()
        log_file.close()
        print("🎉 FleetCTL timestamp process finished.")

    except pexpect.exceptions.TIMEOUT:
        print("❌ ERROR: FleetCTL process timed out! Check /tmp/fleetctl_timestamp_debug.log for details.")

    except pexpect.exceptions.EOF:
        print("❌ ERROR: FleetCTL process exited unexpectedly.")

    except Exception as e:
        print(f"❌ ERROR: Unexpected error: {e}")

if __name__ == "__main__":
    run_fleetctl_timestamp()
