import os
import time
import requests
import threading
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from typing import Dict, List

# Load environment variables
load_dotenv()

# FastAPI app initialization
app = FastAPI()
logs: List[str] = []
results: Dict[str, Dict] = {}  # Store results temporarily

# API Keys and URLs
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
    logs.append("[Step 0] Starting process_video...")
    print("[Step 0] Starting process_video...")


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
        logs.append("[Step 1] Uploading to CloudConvert...")
        print("[Step 1] Uploading to CloudConvert...")

        file_id = upload_to_cloudconvert(file_bytes, filename)

        logs.append("[Step 2] Starting conversion to MP3...")
        print("[Step 2] Starting conversion to MP3...")

        job_id = start_conversion(file_id, "mp3")

        time.sleep(10)

        logs.append("[Step 3] Checking job status...")
        print("[Step 3] Checking job status...")

        job_data = get_job_status(job_id)

        converted_task_id = next(
            (task["id"] for task in job_data["tasks"] if task["operation"] == "convert" and task["status"] == "finished"),
            None
        )

        if not converted_task_id:
            logs.append("[Error] Conversion failed")
            print("[Error] Conversion failed")
            return {"error": "Conversion failed"}

        logs.append("[Step 4] Creating export task...")
        print("[Step 4] Creating export task...")
        export_job_id = create_export_task(converted_task_id)

        logs.append("[Step 5] Getting export download URL...")
        print("[Step 5] Getting export download URL...")
        audio_url = get_export_download_url(export_job_id)

        if not audio_url:
            logs.append("[Error] Export failed")
            print("[Error] Export failed")
            return {"error": "Export failed"}

        logs.append("[Step 6] Downloading audio file...")
        print("[Step 6] Downloading audio file...")
        audio_path = download_audio(audio_url)

        logs.append("[Step 7] Transcribing audio...")
        print("[Step 7] Transcribing audio...")

        transcript = transcribe_audio(audio_path)
        print("-----------Transcript is:", transcript)

        logs.append("[Step 8] Summarizing text...")
        print("[Step 8] Summarizing text...")

        summary = summarize_text(transcript)
        print("-----------Summary is:", summary)

        logs.append("[Step 9] Processing complete.")
        print("[Step 9] Processing complete.")

        # Store result in `results`
        results[filename] = {
            "message": "Processing complete",
            "filename": filename,
            "mp3_url": audio_url,
            "transcript": transcript,
            "summary": summary,
        }

        return results[filename]  # ✅ Returns response immediately

    except Exception as e:
        logs.append(f"[Error] Exception occurred: {str(e)}")
        print(f"[Error] Exception occurred: {str(e)}")
        return {"error": str(e)}



@app.get("/results/{filename}")
async def get_results(filename: str):
    if filename in results:
        return results[filename]
    return {"message": "Results not available yet"}


def upload_to_cloudconvert(file_bytes: bytes, filename: str):
    logs.append("[Step 1] Uploading to CloudConvert...")
    print("[Step 1] Uploading to CloudConvert...")


    url = f"{CLOUDCONVERT_URL}/import/upload"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

    response = requests.post(url, json={"filename": filename}, headers=headers)
    response.raise_for_status()

    upload_data = response.json()["data"]
    upload_url = upload_data["result"]["form"]["url"]
    parameters = upload_data["result"]["form"]["parameters"]

    requests.post(upload_url, files={"file": (filename, file_bytes, "video/mp4")}, data=parameters).raise_for_status()

    logs.append("[Step 2] Upload finished.")
    print("[Step 2] Upload finished.")

    return upload_data["id"]


def start_conversion(file_id: str, output_format="mp3"):
    logs.append("[Step 3] Starting CloudConvert job...")
    print("[Step 3] Starting CloudConvert job...")

    url = f"{CLOUDCONVERT_URL}/jobs"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}", "Content-Type": "application/json"}

    data = {"tasks": {"convert": {"operation": "convert", "input": [file_id], "output_format": output_format}}}
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()

    logs.append("[Step 4] Conversion job started.")
    print("[Step 4] Conversion job started.")
    return response.json()["data"]["id"]


def get_job_status(job_id: str):
    logs.append("[Step 5] Checking job status...")
    print("[Step 5] Checking job status...")

    url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    logs.append("[Step 6] Job status retrieved.")
    print("[Step 6] Job status retrieved.")
    return response.json()["data"]


def create_export_task(file_id: str):
    logs.append("[Step 7] Creating export task...")
    print("[Step 7] Creating export task...")

    url = f"{CLOUDCONVERT_URL}/jobs"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}", "Content-Type": "application/json"}

    data = {"tasks": {"export": {"operation": "export/url", "input": [file_id]}}}
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()

    logs.append("[Step 8] Export task created.")
    print("[Step 8] Export task created.")
    return response.json()["data"]["id"]


def get_export_download_url(job_id: str):
    logs.append("[Step 9] Getting export download URL...")
    print("[Step 9] Getting export download URL...")

    url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    for task in response.json()["data"]["tasks"]:
        if task["operation"] == "export/url" and task["status"] == "finished":
            logs.append("[Step 10] Download URL found.")
            print("[Step 10] Download URL found.")
            return task["result"]["files"][0]["url"]

    return None


def download_audio(audio_url: str, output_path="audio.mp3"):
    logs.append("[Step 11] Downloading audio file...")
    print("[Step 11] Downloading audio file...")

    response = requests.get(audio_url)
    response.raise_for_status()

    with open(output_path, "wb") as file:
        file.write(response.content)

    logs.append("[Step 12] Audio downloaded.")
    print("[Step 12] Audio downloaded.")

    return output_path


def transcribe_audio(audio_path: str):
    logs.append("[Step 13] Transcribing audio...")
    print("[Step 13] Transcribing audio...")


    url = f"{OPENAI_URL}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

    with open(audio_path, "rb") as audio_file:
        files = {"file": audio_file, "model": (None, "whisper-1")}
        response = requests.post(url, headers=headers, files=files)

    response.raise_for_status()
    logs.append("[Step 14] Transcription complete.")
    print("[Step 14] Transcription complete.")
    return response.json()["text"]


def summarize_text(text: str):
    logs.append("[Step 15] Summarizing text...")
    print("[Step 15] Summarizing text...")


    url = f"{OPENAI_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

    data = {"model": "gpt-4", "messages": [{"role": "system", "content": "Summarize this transcript:"}, {"role": "user", "content": text}]}
    response = requests.post(url, json=data, headers=headers)

    response.raise_for_status()
    logs.append("[Step 16] Summary generated.")
    print("[Step 16] Summary generated.")
   
    return response.json()["choices"][0]["message"]["content"]

# # import os
# # import time
# # import requests
# # from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
# # from fastapi.responses import JSONResponse
# # from dotenv import load_dotenv
# # from typing import Dict, List

# # # Load environment variables
# # load_dotenv()

# # # FastAPI app initialization
# # app = FastAPI()
# # logs: List[str] = []

# # # API Keys and URLs
# # CLOUDCONVERT_API_KEY = os.getenv("CLOUDCONVERT_API_KEY")
# # OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# # CLOUDCONVERT_URL = os.getenv("CLOUDCONVERT_URL")
# # OPENAI_URL = os.getenv("OPENAI_URL")

# # @app.get("/")
# # async def read_root():
# #     return {"message": "Hello, World!"}

# # @app.get("/current_step")
# # async def get_current_step():
# #     return {"logs": logs} if logs else {"message": "No steps started yet"}

# # @app.post("/process_video/")
# # async def process_video(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
# #     logs.clear()
# #     logs.append("[Step 0] Starting process_video...")

# #     if not file.filename.endswith(".mp4"):
# #         logs.append("[Error] Invalid file type")
# #         raise HTTPException(status_code=400, detail="Only MP4 files are allowed")

# #     file_bytes = await file.read()
    
# #     # Run the processing in the background
# #     background_tasks.add_task(process_video_task, file_bytes, file.filename)

# #     return {"message": "Processing started"}

# # def process_video_task(file_bytes: bytes, filename: str):
# #     """Runs the video processing logic in the background."""
# #     try:
# #         logs.append("[Step 1] Uploading to CloudConvert...")
# #         file_id = upload_to_cloudconvert(file_bytes, filename)

# #         logs.append("[Step 2] Starting conversion to MP3...")
# #         job_id = start_conversion(file_id, "mp3")

# #         time.sleep(10)

# #         logs.append("[Step 3] Checking job status...")
# #         job_data = get_job_status(job_id)

# #         converted_task_id = next((task["id"] for task in job_data["tasks"] if task["operation"] == "convert" and task["status"] == "finished"), None)

# #         if not converted_task_id:
# #             logs.append("[Error] Conversion failed")
# #             return

# #         logs.append("[Step 4] Creating export task...")
# #         export_job_id = create_export_task(converted_task_id)

# #         logs.append("[Step 5] Getting export download URL...")
# #         audio_url = get_export_download_url(export_job_id)

# #         if not audio_url:
# #             logs.append("[Error] Export failed")
# #             return

# #         logs.append("[Step 6] Downloading audio file...")
# #         audio_path = download_audio(audio_url)

# #         logs.append("[Step 7] Transcribing audio...")
# #         transcript = transcribe_audio(audio_path)

# #         logs.append("[Step 8] Summarizing text...")
# #         summary = summarize_text(transcript)

# #         logs.append("[Step 9] Sending results...")
# #         send_results(transcript, summary)

# #         logs.append("[Step 10] Processing complete.")

# #     except Exception as e:
# #         logs.append(f"[Error] Exception occurred: {str(e)}")

# # def upload_to_cloudconvert(file_bytes: bytes, filename: str):
# #     logs.append("[Step 1] Uploading to CloudConvert...")
# #     url = f"{CLOUDCONVERT_URL}/import/upload"
# #     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}
# #     response = requests.post(url, json={"filename": filename}, headers=headers)
# #     response.raise_for_status()
# #     upload_data = response.json()["data"]
# #     upload_url = upload_data["result"]["form"]["url"]
# #     parameters = upload_data["result"]["form"]["parameters"]
# #     requests.post(upload_url, files={"file": (filename, file_bytes, "video/mp4")}, data=parameters).raise_for_status()
# #     logs.append("[Step 2] Upload finished.")
# #     return upload_data["id"]

# # def start_conversion(file_id: str, output_format="mp3"):
# #     logs.append("[Step 3] Starting CloudConvert job...")
# #     url = f"{CLOUDCONVERT_URL}/jobs"
# #     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}", "Content-Type": "application/json"}
# #     data = {"tasks": {"convert": {"operation": "convert", "input": [file_id], "output_format": output_format}}}
# #     response = requests.post(url, json=data, headers=headers)
# #     response.raise_for_status()
# #     logs.append("[Step 4] Conversion job started.")
# #     return response.json()["data"]["id"]

# # def get_job_status(job_id: str):
# #     logs.append("[Step 5] Checking job status...")
# #     url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
# #     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}
# #     response = requests.get(url, headers=headers)
# #     response.raise_for_status()
# #     logs.append("[Step 6] Job status retrieved.")
# #     return response.json()["data"]

# # def create_export_task(file_id: str):
# #     logs.append("[Step 7] Creating export task...")
# #     url = f"{CLOUDCONVERT_URL}/jobs"
# #     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}", "Content-Type": "application/json"}
# #     data = {"tasks": {"export": {"operation": "export/url", "input": [file_id]}}}
# #     response = requests.post(url, json=data, headers=headers)
# #     response.raise_for_status()
# #     logs.append("[Step 8] Export task created.")
# #     return response.json()["data"]["id"]

# # def get_export_download_url(job_id: str):
# #     logs.append("[Step 9] Getting export download URL...")
# #     url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
# #     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}
# #     response = requests.get(url, headers=headers)
# #     response.raise_for_status()
# #     for task in response.json()["data"]["tasks"]:
# #         if task["operation"] == "export/url" and task["status"] == "finished":
# #             logs.append("[Step 10] Download URL found.")
# #             return task["result"]["files"][0]["url"]
# #     return None

# # def download_audio(audio_url: str, output_path="audio.mp3"):
# #     logs.append("[Step 11] Downloading audio file...")
# #     response = requests.get(audio_url)
# #     response.raise_for_status()
# #     with open(output_path, "wb") as file:
# #         file.write(response.content)
# #     logs.append("[Step 12] Audio downloaded.")
# #     return output_path

# # def transcribe_audio(audio_path: str):
# #     logs.append("[Step 13] Transcribing audio...")
# #     url = f"{OPENAI_URL}/audio/transcriptions"
# #     headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
# #     with open(audio_path, "rb") as audio_file:
# #         files = {"file": audio_file, "model": (None, "whisper-1")}
# #         response = requests.post(url, headers=headers, files=files)
# #     response.raise_for_status()
# #     logs.append("[Step 14] Transcription complete.")
# #     return response.json()["text"]

# # def summarize_text(text: str):
# #     logs.append("[Step 15] Summarizing text...")
# #     url = f"{OPENAI_URL}/chat/completions"
# #     headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
# #     data = {"model": "gpt-4", "messages": [{"role": "system", "content": "Summarize this transcript:"}, {"role": "user", "content": text}]}
# #     response = requests.post(url, json=data, headers=headers)
# #     response.raise_for_status()
# #     logs.append("[Step 16] Summary generated.")
# #     return response.json()["choices"][0]["message"]["content"]

# # def send_results(transcript: str, summary: str):
# #     logs.append("[Step 17] Returning results instead of sending them...")
# #     return {"transcript": transcript, "summary": summary}

# # # import os
# # # import time
# # # import requests
# # # import threading
# # # from fastapi import FastAPI, File, UploadFile, HTTPException
# # # from fastapi.responses import JSONResponse
# # # from dotenv import load_dotenv
# # # from typing import Dict
# # # # Load environment variables
# # # load_dotenv()

# # # # FastAPI app initialization
# # # app = FastAPI()
# # # logs = []

# # # # API Keys and URLs
# # # CLOUDCONVERT_API_KEY = os.getenv("CLOUDCONVERT_API_KEY")
# # # OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# # # CLOUDCONVERT_URL = os.getenv("CLOUDCONVERT_URL")
# # # OPENAI_URL = os.getenv("OPENAI_URL")
# # # # RESULTS_API_URL = os.getenv("RESULTS_API_URL")


# # # @app.get("/")
# # # async def read_root():
# # #     return {"message": "Hello, World!"}

# # # @app.get("/current_step")
# # # async def get_current_step():
# # #     if len(logs) > 0:
# # #         return {"logs": logs}
# # #     else:
# # #         return {"message": "No steps started yet"}


# # # @app.post("/process_video/")
# # # async def process_video(file: UploadFile = File(...)):
# # #     """
# # #     Receives an MP4 file, uploads bytes directly to CloudConvert,
# # #     converts to MP3, transcribes, summarizes, and sends results.
# # #     """
# # #     logs.clear()
# # #     print("Starting process_video handler...")

# # #     # Basic file check
# # #     if not file.filename.endswith(".mp4"):
# # #         print("Error: Invalid file type", file.filename)
# # #         raise HTTPException(status_code=400, detail="Only MP4 files are allowed")

# # #     # Read file bytes directly from the UploadFile
# # #     file_bytes = await file.read()
# # #     print("file_bytes", file_bytes)

# # #     try:
# # #         # Step 1: Upload bytes to CloudConvert
# # #         file_id = upload_to_cloudconvert(file_bytes, file.filename)
# # #         print("file_id", file_id)

# # #         # Step 2: Start conversion to MP3
# # #         job_id = start_conversion(file_id, "mp3")
# # #         print("job_id", job_id)

# # #         # Wait a bit for CloudConvert to process the job (demo approach)
# # #         time.sleep(10)

# # #         # Step 3: Check if the conversion is finished
# # #         job_data = get_job_status(job_id)
# # #         print("job_data", job_data)

# # #         converted_task_id = None
# # #         for task in job_data["tasks"]:
# # #             if task["operation"] == "convert" and task["status"] == "finished":
# # #                 converted_task_id = task["id"]
# # #                 break

# # #         print("converted_task_id", converted_task_id)

# # #         if not converted_task_id:
# # #             print("Error: Conversion failed")
# # #             raise HTTPException(status_code=500, detail="Conversion failed")

# # #         # Step 4: Create export task & retrieve download URL
# # #         export_job_id = create_export_task(converted_task_id)
# # #         print("export_job_id", export_job_id)

# # #         audio_url = get_export_download_url(export_job_id)
# # #         print("audio_url", audio_url)

# # #         if not audio_url:
# # #             print("Error: Export failed")
# # #             raise HTTPException(status_code=500, detail="Export failed")

# # #         # Step 5: Download the MP3 (optional local save if environment allows)
# # #         audio_path = download_audio(audio_url)
# # #         print("audio_path", audio_path)

# # #         # Step 6: Transcribe via OpenAI Whisper
# # #         transcript = transcribe_audio(audio_path)
# # #         print("transcript", transcript)

# # #         # Step 7: Summarize via OpenAI GPT
# # #         summary = summarize_text(transcript)
# # #         print("summary", summary)

# # #         # Step 8: Send results
# # #         send_results(transcript, summary)
# # #         print("Processing complete for", file.filename)

# # #         # Return a JSON response
# # #         return JSONResponse(content={
# # #             "message": "Processing complete",
# # #             "filename": file.filename,
# # #             "mp3_url": audio_url,
# # #             "transcript": transcript,
# # #             "summary": summary
# # #         })

# # #     except Exception as e:
# # #         print("Exception occurred:", str(e))
# # #         raise HTTPException(status_code=500, detail=str(e))



# # # def upload_to_cloudconvert(file_bytes: bytes, filename: str):
# # #     """
# # #     Uploads file bytes to CloudConvert and returns the file ID.
    
# # #     1. Requests an upload form from CloudConvert.
# # #     2. Uploads in-memory bytes to the presigned S3 URL.
# # #     3. Returns the file ID from CloudConvert.
# # #     """
# # #     print("[Step 1] Uploading to CloudConvert...")
# # #     logs.append("[Step 1] Uploading to CloudConvert...")

# # #     url = f"{CLOUDCONVERT_URL}/import/upload"
# # #     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

# # #     # 1. Get pre-signed upload form
# # #     response = requests.post(url, json={"filename": filename}, headers=headers)
# # #     response.raise_for_status()
# # #     upload_data = response.json()["data"]

# # #     # Extract the presigned S3 URL and form fields
# # #     upload_url = upload_data["result"]["form"]["url"]
# # #     parameters = upload_data["result"]["form"]["parameters"]

# # #     # 2. Upload the file bytes directly to the presigned URL (No local saving)
# # #     files = {
# # #         "file": (filename, file_bytes, "video/mp4")
# # #     }
# # #     requests.post(upload_url, files=files, data=parameters).raise_for_status()

# # #     print("[Step 2] Upload finished.")
# # #     logs.append("[Step 2] Upload finished.")
# # #     return upload_data["id"]


# # # def start_conversion(file_id: str, output_format="mp3"):
# # #     """
# # #     Starts a CloudConvert job to convert the uploaded file (by file_id)
# # #     into the specified output format.
# # #     """
# # #     print("[Step 3] Starting CloudConvert job...")
# # #     logs.append("[Step 3] Starting CloudConvert job...")

# # #     url = f"{CLOUDCONVERT_URL}/jobs"
# # #     headers = {
# # #         "Authorization": f"Bearer {CLOUDCONVERT_API_KEY}",
# # #         "Content-Type": "application/json"
# # #     }
# # #     data = {
# # #         "tasks": {
# # #             "convert": {
# # #                 "operation": "convert",
# # #                 "input": [file_id],
# # #                 "output_format": output_format
# # #             }
# # #         }
# # #     }
# # #     response = requests.post(url, json=data, headers=headers)
# # #     response.raise_for_status()

# # #     print("[Step 4] Conversion job started.")
# # #     logs.append("[Step 4] Conversion job started.")
# # #     return response.json()["data"]["id"]


# # # def get_job_status(job_id: str):
# # #     """
# # #     Checks the status of the CloudConvert job until the tasks
# # #     (e.g., conversion) are finished.
# # #     """
# # #     print("[Step 5] Checking job status...")
# # #     logs.append("[Step 5] Checking job status...")

# # #     url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
# # #     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

# # #     response = requests.get(url, headers=headers)
# # #     response.raise_for_status()

# # #     print("[Step 6] Job status retrieved.")
# # #     logs.append("[Step 6] Job status retrieved.")
# # #     return response.json()["data"]


# # # def create_export_task(file_id: str):
# # #     """
# # #     Creates an export task on CloudConvert that generates a
# # #     downloadable URL for the converted file.
# # #     """
# # #     print("[Step 7] Creating export task...")
# # #     logs.append("[Step 7] Creating export task...")

# # #     url = f"{CLOUDCONVERT_URL}/jobs"
# # #     headers = {
# # #         "Authorization": f"Bearer {CLOUDCONVERT_API_KEY}",
# # #         "Content-Type": "application/json"
# # #     }
# # #     data = {
# # #         "tasks": {
# # #             "export": {
# # #                 "operation": "export/url",
# # #                 "input": [file_id]
# # #             }
# # #         }
# # #     }
# # #     response = requests.post(url, json=data, headers=headers)
# # #     response.raise_for_status()

# # #     print("[Step 8] Export task created.")
# # #     logs.append("[Step 8] Export task created.")
# # #     return response.json()["data"]["id"]


# # # def get_export_download_url(job_id: str):
# # #     """
# # #     Retrieves the download URL for the file from the finished export task.
# # #     """
# # #     print("[Step 9] Getting export download URL...")
# # #     logs.append("[Step 9] Getting export download URL...")

# # #     url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
# # #     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}
# # #     response = requests.get(url, headers=headers)
# # #     response.raise_for_status()

# # #     # Look for the 'export/url' operation with 'finished' status
# # #     for task in response.json()["data"]["tasks"]:
# # #         if task["operation"] == "export/url" and task["status"] == "finished":
# # #             print("[Step 10] Download URL found.")
# # #             return task["result"]["files"][0]["url"]
# # #     return None


# # # def download_audio(audio_url: str, output_path="audio.mp3"):
# # #     """
# # #     Downloads the converted MP3 from the given URL into memory or a local path.
    
# # #     NOTE: If you're on a read-only or ephemeral environment, you might
# # #     skip saving and just keep the bytes in memory. For demonstration,
# # #     we'll show how to save it temporarily (if environment allows).
# # #     """
# # #     print("[Step 11] Downloading audio file...")
# # #     logs.append("[Step 11] Downloading audio file...")

# # #     response = requests.get(audio_url)
# # #     response.raise_for_status()

# # #     # Save to local path (optional, if the environment allows)
# # #     with open(output_path, "wb") as file:
# # #         file.write(response.content)

# # #     print("[Step 12] Audio downloaded.")
# # #     logs.append("[Step 12] Audio downloaded.")

# # #     return output_path


# # # def transcribe_audio(audio_path: str):
# # #     """
# # #     Sends the downloaded audio to OpenAI Whisper for transcription.
# # #     """
# # #     print("[Step 13] Transcribing audio...")
# # #     url = f"{OPENAI_URL}/audio/transcriptions"
# # #     headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

# # #     with open(audio_path, "rb") as audio_file:
# # #         files = {"file": audio_file, "model": (None, "whisper-1")}
# # #         response = requests.post(url, headers=headers, files=files)
# # #     response.raise_for_status()

# # #     transcription = response.json()["text"]
# # #     print("[Step 14] Transcription complete.")
# # #     logs.append("[Step 14] Transcription complete.")
# # #     return transcription


# # # def summarize_text(text: str):
# # #     """
# # #     Sends the transcribed text to OpenAI GPT for summarization.
# # #     """
# # #     print("[Step 15] Summarizing text...")
# # #     url = f"{OPENAI_URL}/chat/completions"
# # #     headers = {
# # #         "Authorization": f"Bearer {OPENAI_API_KEY}",
# # #         "Content-Type": "application/json"
# # #     }
# # #     data = {
# # #         "model": "gpt-4",
# # #         "messages": [
# # #             {"role": "system", "content": "Summarize this transcript:"},
# # #             {"role": "user", "content": text}
# # #         ]
# # #     }
# # #     response = requests.post(url, json=data, headers=headers)
# # #     response.raise_for_status()

# # #     summary = response.json()["choices"][0]["message"]["content"]
# # #     print("[Step 16] Summary generated.")
# # #     logs.append("[Step 16] Summary generated.")

# # #     return summary


# # # def send_results(transcript: str, summary: str):
# # #     print("[Step 17] Returning results instead of sending them...")
# # #     payload = {"transcript": transcript, "summary": summary}
# # #     print("payload is", payload)
# # #     print('logs are', logs)
# # #     return payload 


