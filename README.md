# Watch and Transcribe Calls

This project contains a Python script `watch_and_transcribe.py` that watches for audio input and transcribes calls automatically.

## Features

- Real-time audio watching  
- Automatic speech-to-text transcription  
- Easy to run and customize

## Requirements

- Python 3.x  
- Required libraries (see `requirements.txt`)

## Installation

1. Clone the repo:  
   ```bash
   git clone https://github.com/ManosKalaitzakis/watch-and-transcribe-calls.git

    Create and activate a virtual environment:

python -m venv venv
.\venv\Scripts\activate    # Windows

Install dependencies:

    pip install -r requirements.txt

Usage

Run the script with:

python watch_and_transcribe.py

## Automation Workflow

After running `watch_and_transcribe.py`, a Power Automate flow runs every minute to:

1. Read new call transcripts from an Excel file (`DATA.xlsx`) stored on OneDrive.  
2. Post a message with call details (date, caller, transcript, name) to a Microsoft Teams group chat.  
3. Update the Excel rows to mark them as sent, preventing duplicate messages.

This flow automates sharing call transcriptions seamlessly to your team.

Contributing

Feel free to open issues or pull requests.
License

This project is licensed under the MIT License. See the LICENSE file for details.
