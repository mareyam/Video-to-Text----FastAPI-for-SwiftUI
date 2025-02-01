import os
import time
import requests
import threading
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from typing import Dict
# Load environment variables
load_dotenv()

# FastAPI app initialization
app = FastAPI()
logs = []

# API Keys and URLs
CLOUDCONVERT_API_KEY = os.getenv("CLOUDCONVERT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLOUDCONVERT_URL = os.getenv("CLOUDCONVERT_URL")
OPENAI_URL = os.getenv("OPENAI_URL")
RESULTS_API_URL = os.getenv("RESULTS_API_URL")


@app.get("/")
async def read_root():
    return {"message": "Hello, World!"}

def update_status(message: str):
    """Updates the global status list and prints to console."""
    global logs
    print(message)
    logs.append(message)  # Store logs in memory
    if len(logs) > 20:  # Limit logs to last 20 messages
        logs.pop(0)


@app.get("/get_logs")
async def get_logs():
    """Returns the latest status logs."""
    return {"logs": logs}

def upload_to_cloudconvert(file_bytes: bytes, filename: str):
    """
    Uploads file bytes to CloudConvert and returns the file ID.
    
    1. Requests an upload form from CloudConvert.
    2. Uploads in-memory bytes to the presigned S3 URL.
    3. Returns the file ID from CloudConvert.
    """
    print("[Step 1] Uploading to CloudConvert...")
    update_status("[Step 1] Uploading to CloudConvert...")

    url = f"{CLOUDCONVERT_URL}/import/upload"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

    # 1. Get pre-signed upload form
    response = requests.post(url, json={"filename": filename}, headers=headers)
    response.raise_for_status()
    upload_data = response.json()["data"]

    # Extract the presigned S3 URL and form fields
    upload_url = upload_data["result"]["form"]["url"]
    parameters = upload_data["result"]["form"]["parameters"]

    # 2. Upload the file bytes directly to the presigned URL (No local saving)
    files = {
        "file": (filename, file_bytes, "video/mp4")
    }
    requests.post(upload_url, files=files, data=parameters).raise_for_status()

    print("[Step 2] Upload finished.")
    update_status("[Step 2] Upload finished.")
    return upload_data["id"]


def start_conversion(file_id: str, output_format="mp3"):
    """
    Starts a CloudConvert job to convert the uploaded file (by file_id)
    into the specified output format.
    """
    print("[Step 3] Starting CloudConvert job...")
    update_status("[Step 3] Starting CloudConvert job...")

    url = f"{CLOUDCONVERT_URL}/jobs"
    headers = {
        "Authorization": f"Bearer {CLOUDCONVERT_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "tasks": {
            "convert": {
                "operation": "convert",
                "input": [file_id],
                "output_format": output_format
            }
        }
    }
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()

    print("[Step 4] Conversion job started.")
    update_status("[Step 4] Conversion job started.")
    return response.json()["data"]["id"]


def get_job_status(job_id: str):
    """
    Checks the status of the CloudConvert job until the tasks
    (e.g., conversion) are finished.
    """
    print("[Step 5] Checking job status...")
    update_status("[Step 5] Checking job status...")

    url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    print("[Step 6] Job status retrieved.")
    update_status("[Step 6] Job status retrieved.")
    return response.json()["data"]


def create_export_task(file_id: str):
    """
    Creates an export task on CloudConvert that generates a
    downloadable URL for the converted file.
    """
    print("[Step 7] Creating export task...")
    update_status("[Step 7] Creating export task...")

    url = f"{CLOUDCONVERT_URL}/jobs"
    headers = {
        "Authorization": f"Bearer {CLOUDCONVERT_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "tasks": {
            "export": {
                "operation": "export/url",
                "input": [file_id]
            }
        }
    }
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()

    print("[Step 8] Export task created.")
    update_status("[Step 8] Export task created.")
    return response.json()["data"]["id"]


def get_export_download_url(job_id: str):
    """
    Retrieves the download URL for the file from the finished export task.
    """
    print("[Step 9] Getting export download URL...")
    update_status("[Step 9] Getting export download URL...")

    url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    # Look for the 'export/url' operation with 'finished' status
    for task in response.json()["data"]["tasks"]:
        if task["operation"] == "export/url" and task["status"] == "finished":
            print("[Step 10] Download URL found.")
            return task["result"]["files"][0]["url"]
    return None


def download_audio(audio_url: str, output_path="audio.mp3"):
    """
    Downloads the converted MP3 from the given URL into memory or a local path.
    
    NOTE: If you're on a read-only or ephemeral environment, you might
    skip saving and just keep the bytes in memory. For demonstration,
    we'll show how to save it temporarily (if environment allows).
    """
    print("[Step 11] Downloading audio file...")
    update_status("[Step 11] Downloading audio file...")

    response = requests.get(audio_url)
    response.raise_for_status()

    # Save to local path (optional, if the environment allows)
    with open(output_path, "wb") as file:
        file.write(response.content)

    print("[Step 12] Audio downloaded.")
    update_status("[Step 12] Audio downloaded.")

    return output_path


def transcribe_audio(audio_path: str):
    """
    Sends the downloaded audio to OpenAI Whisper for transcription.
    """
    print("[Step 13] Transcribing audio...")
    url = f"{OPENAI_URL}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

    with open(audio_path, "rb") as audio_file:
        files = {"file": audio_file, "model": (None, "whisper-1")}
        response = requests.post(url, headers=headers, files=files)
    response.raise_for_status()

    transcription = response.json()["text"]
    print("[Step 14] Transcription complete.")
    update_status("[Step 14] Transcription complete.")
    return transcription


def summarize_text(text: str):
    """
    Sends the transcribed text to OpenAI GPT for summarization.
    """
    print("[Step 15] Summarizing text...")
    url = f"{OPENAI_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "Summarize this transcript:"},
            {"role": "user", "content": text}
        ]
    }
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()

    summary = response.json()["choices"][0]["message"]["content"]
    print("[Step 16] Summary generated.")
    update_status("[Step 16] Summary generated.")

    return summary


def send_results(transcript: str, summary: str):
    """
    Calls another API to send the transcript and summary.
    """
    print("[Step 17] Sending results to external API...")
    payload = {"transcript": transcript, "summary": summary}
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(RESULTS_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        print("[Step 18] [✅] Results sent successfully:", response.json())
        update_status("[Step 18] [✅] Results sent successfully:")
  
    except requests.exceptions.RequestException as e:
        print("[Step 19] [❌] Failed to send results:", str(e))
        update_status("[Step 19] [❌] Failed to send results:")



@app.post("/process_video/")
async def process_video(file: UploadFile = File(...)):
    """
    Receives an MP4 file, uploads bytes directly to CloudConvert,
    converts to MP3, transcribes, summarizes, and sends results.
    """
    print("[Step 20] Starting process_video handler...")
    update_status("[Step 20] Starting process_video handler...")


    # Basic file check
    if not file.filename.endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Only MP4 files are allowed")

    # Read file bytes directly from the UploadFile
    file_bytes = await file.read()

    try:
        # Step 1: Upload bytes to CloudConvert
        file_id = upload_to_cloudconvert(file_bytes, file.filename)

        # Step 2: Start conversion to MP3
        job_id = start_conversion(file_id, "mp3")

        # Wait a bit for CloudConvert to process the job (demo approach)
        time.sleep(10)

        # Step 3: Check if the conversion is finished
        job_data = get_job_status(job_id)
        converted_task_id = None
        for task in job_data["tasks"]:
            if task["operation"] == "convert" and task["status"] == "finished":
                converted_task_id = task["id"]
                break

        if not converted_task_id:
            raise HTTPException(status_code=500, detail="Conversion failed")

        # Step 4: Create export task & retrieve download URL
        export_job_id = create_export_task(converted_task_id)
        audio_url = get_export_download_url(export_job_id)
        if not audio_url:
            raise HTTPException(status_code=500, detail="Export failed")

        # Step 5: Download the MP3 (optional local save if environment allows)
        audio_path = download_audio(audio_url)

        # Step 6: Transcribe via OpenAI Whisper
        transcript = transcribe_audio(audio_path)

        # Step 7: Summarize via OpenAI GPT
        summary = summarize_text(transcript)

        # Step 8: Send results
        send_results(transcript, summary)

        # Return a JSON response
        return JSONResponse(content={
            "message": "Processing complete",
            "filename": file.filename,
            "mp3_url": audio_url,
            "transcript": transcript,
            "summary": summary
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))