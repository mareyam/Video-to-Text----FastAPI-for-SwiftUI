import os
import time
import requests
import shutil
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# FastAPI app initialization
app = FastAPI()

# Directories
UPLOAD_DIRECTORY = "uploads"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

# CloudConvert API and OpenAI API keys from env
CLOUDCONVERT_API_KEY = os.getenv("CLOUDCONVERT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLOUDCONVERT_URL = os.getenv("CLOUDCONVERT_URL")
OPENAI_URL = os.getenv("OPENAI_URL")


@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

def upload_to_cloudconvert(video_path: str):
    print('here 1')

    """Uploads the video to CloudConvert and returns the file ID."""
    url = f"{CLOUDCONVERT_URL}/import/upload"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

    response = requests.post(url, json={"filename": os.path.basename(video_path)}, headers=headers)
    response.raise_for_status()

    upload_data = response.json()["data"]
    upload_url = upload_data["result"]["form"]["url"]
    parameters = upload_data["result"]["form"]["parameters"]

    with open(video_path, "rb") as file:
        files = {"file": file}
        requests.post(upload_url, files=files, data=parameters).raise_for_status()

    print('here 11')

    return upload_data["id"]


def start_conversion(file_id: str, output_format="mp3"):

    print('here 2')

    """Starts a CloudConvert job to convert the file."""
    url = f"{CLOUDCONVERT_URL}/jobs"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}", "Content-Type": "application/json"}

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

    print('here 22')


    return response.json()["data"]["id"]


def get_job_status(job_id: str):
    print('here 3')

    """Checks the status of the conversion job."""
    url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    print('here 33')

    return response.json()["data"]


def create_export_task(file_id: str):
    print('here 4')

    """Creates an export task to generate a downloadable URL."""
    url = f"{CLOUDCONVERT_URL}/jobs"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}", "Content-Type": "application/json"}

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

    print('here 44')

    return response.json()["data"]["id"]


def get_export_download_url(job_id: str):

    print('here 5')

    """Gets the download URL of the exported file."""
    url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    for task in response.json()["data"]["tasks"]:
        if task["operation"] == "export/url" and task["status"] == "finished":
            return task["result"]["files"][0]["url"]

    print('here 55')
    return None


def download_audio(audio_url: str, output_path="audio.mp3"):
    print('here 6')

    """Downloads the converted MP3 file."""
    response = requests.get(audio_url)
    response.raise_for_status()

    with open(output_path, "wb") as file:
        file.write(response.content)

    print('here 66')

    return output_path


def transcribe_audio(audio_path: str):

    print('here 7')

    """Sends the audio file to OpenAI Whisper for transcription."""
    url = f"{OPENAI_URL}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

    with open(audio_path, "rb") as audio_file:
        files = {"file": audio_file, "model": (None, "whisper-1")}
        response = requests.post(url, headers=headers, files=files)

    response.raise_for_status()
    print('here 77')

    return response.json()["text"]


def summarize_text(text: str):
    print('here 8')

    """Sends the extracted text to OpenAI GPT for summarization."""
    url = f"{OPENAI_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

    data = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "Summarize this transcript:"},
            {"role": "user", "content": text}
        ]
    }

    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()

    print('here 88')

    return response.json()["choices"][0]["message"]["content"]


@app.post("/process_video/")
async def process_video(file: UploadFile = File(...)):
    """Handles video upload, conversion to MP3, transcription, and summarization."""
    if not file.filename.endswith(".mp4"):
        return {"error": "Only MP4 files are allowed"}

    file_path = os.path.join(UPLOAD_DIRECTORY, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Upload to CloudConvert
    file_id = upload_to_cloudconvert(file_path)

    # Start MP3 conversion
    job_id = start_conversion(file_id, "mp3")

    # Wait for conversion completion
    time.sleep(10)  

    job_data = get_job_status(job_id)

    converted_task_id = None
    for task in job_data["tasks"]:
        if task["operation"] == "convert" and task["status"] == "finished":
            converted_task_id = task["id"]
            break

    if not converted_task_id:
        return {"error": "Conversion failed"}

    # Export & download MP3
    export_job_id = create_export_task(converted_task_id)
    audio_url = get_export_download_url(export_job_id)

    if not audio_url:
        return {"error": "Export failed"}

    audio_path = download_audio(audio_url)

    # Transcribe & summarize
    transcript = transcribe_audio(audio_path)
    summary = summarize_text(transcript)

    return {
        "message": "Processing complete",
        "filename": file.filename,
        "mp3_url": audio_url,
        "transcript": transcript,
        "summary": summary
    }
