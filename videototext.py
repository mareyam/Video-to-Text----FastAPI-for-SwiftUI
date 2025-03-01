import os
import time
import requests
import threading
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from typing import Dict, List
import io

load_dotenv()

app = FastAPI()
logs: List[str] = []
results: Dict[str, Dict] = {} 

CLOUDCONVERT_API_KEY = os.getenv("CLOUDCONVERT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLOUDCONVERT_URL = os.getenv("CLOUDCONVERT_URL")
OPENAI_URL = os.getenv("OPENAI_URL")

@app.get("/")
async def read_root():
    return {"message": "Hello, World!"}

@app.get("/current_step")
async def get_current_step():
    print('logs are', logs)
    return {"logs": logs} if logs else {"message": "No steps started yet"}

@app.post("/process_video/")
async def process_video(file: UploadFile = File(...)):
    logs.clear()
    logs.append("[Step 0/9] Starting process_video...")
    print("[Step 0/9] Starting process_video...")


    if not file.filename.endswith(".mp4"):
        logs.append("[Error] Invalid file type")
        print("[Error] Invalid file type")

        raise HTTPException(status_code=400, detail="Only MP4 files are allowed")

    file_bytes = await file.read()
    thread = threading.Thread(target=process_video_task, args=(file_bytes, file.filename))
    thread.start()

    return JSONResponse(content={"message": "Processing started, check /current_step"})

def process_video_task(file_bytes: bytes, filename: str):
    """Runs the video processing logic in a separate thread."""
    try:
        logs.append("[Step 1/9] Uploading to CloudConvert...")
        print("[Step 1/9] Uploading to CloudConvert...")

        file_id = upload_to_cloudconvert(file_bytes, filename)
        print("file_id", file_id)

        logs.append("[Step 2/9] Starting conversion to MP3...")
        print("[Step 2/9] Starting conversion to MP3...")

        job_id = start_conversion(file_id, "mp3")
        print("job_id", job_id)


        time.sleep(10)

        logs.append("[Step 3/9] Checking job status...")
        print("[Step 3/9] Checking job status...")

        job_data = get_job_status(job_id)
        print("job_data", job_data)

        # converted_task_id = next(
        #     (task["id"] for task in job_data["tasks"] if task["operation"] == "convert" and task["status"] == "finished"),
        #     None
        # )

        converted_task_id = wait_for_job_completion(job_id)
        print("converted_task_id", converted_task_id)

        if not converted_task_id:
            logs.append("[Error] Conversion failed")
            print("[Error] Conversion failed")
            return {"error": "Conversion failed"}

        logs.append("[Step 4/9] Creating export task...")
        print("[Step 4/9] Creating export task...")
        export_job_id = create_export_task(converted_task_id)
        print("export_job_id", export_job_id)


        logs.append("[Step 5/9] Getting export  URL...")
        print("[Step 5/9] Getting export  URL...")
        # audio_url = get_export_download_url(export_job_id)
        audio_url = get_export_download_url_with_retry(export_job_id)


        print("audio_url", audio_url)


        if not audio_url:
            logs.append("[Error] Export failed")
            print("[Error] Export failed")
            return {"error": "Export failed"}

        logs.append("[Step 6/9] Retrieving audio file...")
        print("[Step 6/9] Retrieving audio file...")
        # audio_path = download_audio(audio_url)
        # print("audio_path", audio_path)


        logs.append("[Step 7/9] Transcribing audio...")
        print("[Step 7/9] Transcribing audio...")

        # transcript = transcribe_audio(audio_path)
        transcript = transcribe_audio(audio_url)
        print("-----------Transcript is:", transcript)

        logs.append("[Step 8/9] Summarizing text...")
        print("[Step 8/9] Summarizing text...")

        summary = summarize_text(transcript)
        print("-----------Summary is:", summary)

        logs.append("[Step 9/9] Processing complete.")
        print("[Step 9/9] Processing complete.")

        results[filename] = {
            "message": "Processing complete",
            "filename": filename,
            "mp3_url": audio_url,
            "transcript": transcript,
            "summary": summary,
        }
        print("results[filename]", results[filename])
        return results[filename] 

    except Exception as e:
        logs.append(f"[Error] Exception occurred 1: {str(e)}")
        print(f"[Error] Exception occurred 1: {str(e)}")
        return {"error": str(e)}

@app.get("/results/{filename}")
async def get_results(filename: str):
    if filename in results:
        return results[filename]
    return {"message": "Results not available yet"}

def upload_to_cloudconvert(file_bytes: bytes, filename: str):
    url = f"{CLOUDCONVERT_URL}/import/upload"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

    response = requests.post(url, json={"filename": filename}, headers=headers)
    response.raise_for_status()

    upload_data = response.json()["data"]
    upload_url = upload_data["result"]["form"]["url"]
    parameters = upload_data["result"]["form"]["parameters"]

    requests.post(upload_url, files={"file": (filename, file_bytes, "video/mp4")}, data=parameters).raise_for_status()
    return upload_data["id"]

def start_conversion(file_id: str, output_format="mp3"):
    url = f"{CLOUDCONVERT_URL}/jobs"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}", "Content-Type": "application/json"}

    data = {"tasks": {"convert": {"operation": "convert", "input": [file_id], "output_format": output_format}}}
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    return response.json()["data"]["id"]

def get_job_status(job_id: str):
    url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()["data"]

def wait_for_job_completion(job_id, max_retries=30, delay=5):
    """Polls CloudConvert job status until it's finished or fails."""
    for _ in range(max_retries):
        job_data = get_job_status(job_id)
        print("job_data in WFJC", job_data)

        # Check if the job contains the finished conversion task
        converted_task_id = next(
            (task["id"] for task in job_data.get("tasks", []) 
             if task.get("operation") == "convert" and task.get("status") == "finished"),
            None
        )

        if converted_task_id:
            return converted_task_id  # Conversion successful
        
        print("converted_task_id in WFJC", converted_task_id)

        if any(task.get("status") in ["failed", "error"] for task in job_data.get("tasks", [])):
            print("[Error] Conversion failed")
            logs.append("[Error] Conversion failed")
            return None

        print("[Step 3/9] Still processing... Retrying in", delay, "seconds")
        time.sleep(delay)

    print("[Error] Conversion timed out")
    logs.append("[Error] Conversion timed out")
    return None  # Timeout error


def create_export_task(converted_task_id: str):
    url = f"{CLOUDCONVERT_URL}/jobs"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}", "Content-Type": "application/json"}

    data = {"tasks": {"export": {"operation": "export/url", "input": [converted_task_id]}}}
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    return response.json()["data"]["id"]

def get_export_download_url(job_id: str):
    url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    for task in response.json()["data"]["tasks"]:
        if task["operation"] == "export/url" and task["status"] == "finished":
            return task["result"]["files"][0]["url"]

    return None

def get_export_download_url_with_retry(job_id: str, retries=5, delay=5):
    for attempt in range(retries):
        print(f"Attempt {attempt + 1}: Fetching export URL...")
        url = get_export_download_url(job_id)
        print('url is', url)
        if url:
            return url
        time.sleep(delay)  # Wait before retrying
    return None  # Return None if retries fail

def download_audio(audio_url: str, output_path="audio.mp3"):
    response = requests.get(audio_url)
    response.raise_for_status()

    with open(output_path, "wb") as file:
        file.write(response.content)
    return output_path

def transcribe_audio(audio_url: str):
    url = f"{OPENAI_URL}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

    print("Transcribe URL:", url)

    try:
        audio_response = requests.get(audio_url, stream=True)
        print('aud res ', audio_response)
        if audio_response.status_code != 200:
            print("Error downloading audio file:", audio_response.status_code)
            return None

        audio_file = io.BytesIO(audio_response.content)
        print('audio_file', audio_file)


        files = {
            'file': ('audio.mp3', audio_file, 'audio/mpeg')  # Send file-like object
        }
        data = {'model': 'whisper-1'}
        print('files', files)


        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()  # Raise an error if request fails
        
        print("Transcription Response:", response.json())
        return response.json()["text"]

    except Exception as e:
        print("An error occurred:", str(e))
        return None
    
def summarize_text(text: str):
    url = f"{OPENAI_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

    data = {"model": "gpt-4", "messages": [{"role": "system", "content": "Summarize this transcript:"}, {"role": "user", "content": text}]}
    response = requests.post(url, json=data, headers=headers)

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]




# def transcribe_audio(audio_url: str):
#     url = f"{OPENAI_URL}/audio/transcriptions"
#     headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}


#     print("transcribe url is", url)
#     # with open(audio_path, "rb") as audio_file:
#     #     files = {"file": audio_file, "model": (None, "whisper-1")}
#     #     response = requests.post(url, headers=headers, files=files)

#     response = requests.post(url, headers=headers, json={"audio_url": audio_url, "model": "whisper-1"})
#     response.raise_for_status()
    
#     print('trans response is', response.json)
#     return response.json()["text"]
