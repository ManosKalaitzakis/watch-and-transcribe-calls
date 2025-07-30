import os
import time
import re
import uuid
import whisper
import pandas as pd
from datetime import datetime
from pydub import AudioSegment
import threading
import shutil

# --- CONFIGURATION ---
CALLS_DIR = "C:/calls"
WORK_LOG_FILE = "C:/calls/fixed_work.csv"  # Changed to CSV
SYNC_LOG_FILE = r"C:\Users\Administrator\OneDrive - Epsilon Net S.A\fixed.csv"  # Changed to CSV
CONTACTS_CSV = "contacts.csv"
CHECK_INTERVAL_SECONDS = 1
PROCESSED_FILES = set()
SYNC_INTERVAL_SECONDS = 30
DESKTOP_PATH = r"C:\Users\Administrator\Desktop"


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


# --- Load Whisper Model ---
log("Loading Whisper model (large-v3)...")
model = whisper.load_model("large-v3")
log("Whisper model loaded.")


# --- CSV Initialization ---
def initialize_csv():
    if not os.path.exists(WORK_LOG_FILE):
        log("CSV log file does not exist. Creating new one.")
        df = pd.DataFrame(columns=["id", "Date", "Caller", "Name", "Transcript", "sent"])
        df.to_csv(WORK_LOG_FILE, index=False)
        log("CSV file created.")
    else:
        log("CSV file already exists.")


# --- Load Contacts ---
def load_contacts(csv_path):
    log(f"Loading contacts from '{csv_path}'...")
    try:
        df = pd.read_csv(csv_path, dtype=str).fillna("")
    except Exception as e:
        log(f"[ERROR] Failed to read contacts CSV: {e}")
        return {}

    id_map = {}
    for _, row in df.iterrows():
        email = row.get("Number", "")
        if "@voips.modulus.gr" in email:
            caller_id = email.split("@")[0].strip()
            name = row.get("Name", "").strip()
            if not name:
                name = f"{row.get('First Name', '').strip()} {row.get('Last Name', '').strip()}"
            id_map[caller_id] = name.strip()

        if row.get("Id", "").isdigit():
            id_map[row["Id"].strip()] = row.get("Name", "").strip()

    log(f"Loaded {len(id_map)} contacts.")
    return id_map


# --- Transcribe and Log ---
def transcribe_and_log(filepath, contacts_dict):
    filename = os.path.basename(filepath)
    log(f"📝 Starting transcription for {filename}")

    match = re.match(r"(\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})_(\d+)\.wav", filename)
    if not match:
        log(f"[WARN] Filename not matching expected format: {filename}")
        return

    timestamp_str, caller = match.groups()
    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d-%H-%M-%S")

    try:
        audio = AudioSegment.from_wav(filepath)
        trimmed_audio = audio[4000:]
        trimmed_audio.export(filepath, format="wav")

        result = model.transcribe(filepath, language="el")

        text = result.get("text", "").strip()
        text = text.replace(
            "Η κλήση ηχογραφείται. Αφήστε το μήνυμά σας και θα σας καλέσουμε σύντομα.", ""
        ).strip()
        text = text.replace(
            "Η κλίση ηχογραφείται. Αφήστε το μήνυμά σας και θα σας καλέσουμε σύντομα.", ""
        ).strip()
    except Exception as e:
        log(f"[ERROR] Failed to transcribe {filename}: {e}")
        return

    caller_name = contacts_dict.get(caller, "Unknown")

    new_row = {
        "id": str(uuid.uuid4()),
        "Date": timestamp,
        "Caller": caller,
        "Name": caller_name,
        "Transcript": text,
        "sent": 0
    }

    # Append new row immediately to CSV
    try:
        if not os.path.exists(WORK_LOG_FILE):
            initialize_csv()

        # Append without header, add mode 'a'
        pd.DataFrame([new_row]).to_csv(WORK_LOG_FILE, mode='a', index=False, header=False)
    except Exception as e:
        log(f"[ERROR] Failed to write to CSV log: {e}")
        return

    log(f"✅ Transcription logged for {caller_name} ({caller}) at {timestamp}")


# --- Move file to Desktop and back (to trigger OneDrive sync) ---
def move_file_to_desktop_and_back(filepath):
    if not os.path.exists(filepath):
        log(f"[MOVE] File does not exist: {filepath}")
        return

    base_name = os.path.basename(filepath)
    desktop_path = os.path.join(DESKTOP_PATH, base_name)

    try:
        shutil.move(filepath, desktop_path)
        log(f"[MOVE] Moved file to Desktop: {desktop_path}")
        time.sleep(2)
        shutil.move(desktop_path, filepath)
        log(f"[MOVE] Moved file back to original location: {filepath}")
    except Exception as e:
        log(f"[MOVE ERROR] {e}")


# --- Sync to OneDrive ---
def sync_to_onedrive():
    last_hash = None
    while True:
        try:
            if not os.path.exists(WORK_LOG_FILE):
                time.sleep(SYNC_INTERVAL_SECONDS)
                continue

            df = pd.read_csv(WORK_LOG_FILE)

            new_hash = hash(pd.util.hash_pandas_object(df).sum())
            if new_hash == last_hash:
                time.sleep(SYNC_INTERVAL_SECONDS)
                continue
            last_hash = new_hash

            df.to_csv(SYNC_LOG_FILE, index=False)
            log("📤 Synced to OneDrive.")

            # Trigger OneDrive sync by moving the file out and back in
            move_file_to_desktop_and_back(SYNC_LOG_FILE)

        except Exception as e:
            log(f"[SYNC ERROR] {e}")

        time.sleep(SYNC_INTERVAL_SECONDS)


# --- Periodic touch + pause to nudge OneDrive ---
def periodic_touch_pause(filepath):
    while True:
        try:
            log("[SYNC-NUDGE] Touching and closing CSV to alert OneDrive.")
            with open(filepath, "rb") as f:
                f.read(1024)  # light read to touch
            time.sleep(1)

            log("[SYNC-NUDGE] Sleeping 20s to release any locks.")
            time.sleep(20)
        except Exception as e:
            log(f"[NUDGE ERROR] {e}")

        time.sleep(40)  # rest of 60s cycle


# --- Main Watcher ---
def watch_directory(contacts_dict):
    log(f"👁️ Watching '{CALLS_DIR}' for new recordings...")
    initialize_csv()

    last_status_time = time.time()

    while True:
        try:
            files = [f for f in os.listdir(CALLS_DIR) if f.endswith(".wav")]
            new_files = 0

            for file in files:
                full_path = os.path.join(CALLS_DIR, file)
                if full_path not in PROCESSED_FILES:
                    transcribe_and_log(full_path, contacts_dict)
                    PROCESSED_FILES.add(full_path)
                    new_files += 1

            now = time.time()
            if now - last_status_time >= 5:
                log(f"[STATUS] Checked {len(files)} file(s), {new_files} new.")
                last_status_time = now

        except Exception as e:
            log(f"[ERROR] {e}")

        time.sleep(CHECK_INTERVAL_SECONDS)


# --- Entry Point ---
if __name__ == "__main__":
    contacts_dict = load_contacts(CONTACTS_CSV)
    threading.Thread(target=sync_to_onedrive, daemon=True).start()
    threading.Thread(target=periodic_touch_pause, args=(SYNC_LOG_FILE,), daemon=True).start()
    watch_directory(contacts_dict)
