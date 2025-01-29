from fastapi import FastAPI, UploadFile, File
import shutil
import os
import time
import requests


import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

CLOUDCONVERT_API_KEY = os.getenv("CLOUDCONVERT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
VIDEO_PATH = os.getenv("VIDEO_PATH")
AUDIO_PATH = os.getenv("AUDIO_PATH")
CLOUDCONVERT_URL = os.getenv("CLOUDCONVERT_URL")
OPENAI_URL = os.getenv("OPENAI_URL")

print("Loaded API Keys and URLs:")
print("CLOUDCONVERT_API_KEY:", CLOUDCONVERT_API_KEY)
print("OPENAI_API_KEY:", OPENAI_API_KEY)
print("VIDEO_PATH:", VIDEO_PATH)
print("AUDIO_PATH:", AUDIO_PATH)
print("CLOUDCONVERT_URL:", CLOUDCONVERT_URL)
print("OPENAI_URL:", OPENAI_URL)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialize FastAPI
app = FastAPI()


@app.get("/")
# print('hello')
def home():
    return {"message": "API is running!"}

@app.post("/upload/")
async def upload_video(file: UploadFile = File(...)):
    """ Uploads a video file and processes it to extract text """
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Step 1: Upload to CloudConvert
    file_id = upload_to_cloudconvert(file_path)
    
    # Step 2: Convert video to MP3
    job_id = start_conversion(file_id, "mp3")

    time.sleep(10)  # Wait for conversion

    # Step 3: Get conversion job status
    job_data = get_job_status(job_id)
    
    converted_task_id = None
    for task in job_data["tasks"]:
        if task["operation"] == "convert" and task["status"] == "finished":
            converted_task_id = task["id"]
            break

    if not converted_task_id:
        return {"error": "Conversion failed!"}

    # Step 4: Export the MP3 file
    export_job_id = create_export_task(converted_task_id)
    audio_url = get_export_download_url(export_job_id)

    # Step 5: Download MP3
    audio_path = download_audio(audio_url)

    # Step 6: Transcribe Audio
    transcript = transcribe_audio(audio_path)

    # Step 7: Summarize Text
    summary = summarize_text(transcript)

    return {
        "message": "Video processed successfully!",
        "transcription": transcript,
        "summary": summary
    }

# --------------------------------
# 🔹 CloudConvert Functions
# --------------------------------

def upload_to_cloudconvert(video_path):
    """ Uploads a video file to CloudConvert """
    url = f"{CLOUDCONVERT_URL}/import/upload"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

    response = requests.post(url, json={"filename": os.path.basename(video_path)}, headers=headers)
    response.raise_for_status()

    upload_data = response.json()["data"]
    upload_url = upload_data["result"]["form"]["url"]
    parameters = upload_data["result"]["form"]["parameters"]

    with open(video_path, "rb") as file:
        files = {"file": file}
        requests.post(upload_url, files=files, data=parameters)

    return upload_data["id"]

def start_conversion(file_id, output_format="mp3"):
    """ Starts CloudConvert conversion from video to MP3 """
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

    return response.json()["data"]["id"]

def get_job_status(job_id):
    """ Retrieves CloudConvert job status """
    url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()["data"]

def create_export_task(file_id):
    """ Creates an export task to get a downloadable MP3 URL """
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

    return response.json()["data"]["id"]

def get_export_download_url(job_id):
    """ Retrieves the downloadable MP3 file URL """
    url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
    headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    job_data = response.json()["data"]

    for task in job_data["tasks"]:
        if task["operation"] == "export/url" and task["status"] == "finished":
            return task["result"]["files"][0]["url"]

    return None

def download_audio(audio_url, output_path="audio.mp3"):
    """ Downloads the MP3 file from CloudConvert """
    response = requests.get(audio_url)
    response.raise_for_status()

    with open(output_path, "wb") as file:
        file.write(response.content)

    return output_path

# --------------------------------
# 🔹 OpenAI Functions (Whisper + GPT)
# --------------------------------

def transcribe_audio(audio_path):
    """ Sends the MP3 file to OpenAI Whisper for transcription """
    url = f"{OPENAI_URL}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

    with open(audio_path, "rb") as audio_file:
        files = {"file": audio_file, "model": (None, "whisper-1")}
        response = requests.post(url, headers=headers, files=files)

    response.raise_for_status()
    return response.json()["text"]

def summarize_text(text):
    """ Sends the transcription to OpenAI GPT for summarization """
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

    return response.json()["choices"][0]["message"]["content"]


# import os
# import time
# import requests
# from fastapi import FastAPI, File, UploadFile, HTTPException
# from fastapi.responses import JSONResponse
# import shutil

# CLOUDCONVERT_API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIxIiwianRpIjoiNWUyM2U3Mjk4ZTY0MTk3MjZkZWZmM2M4MjFiNDA4YmI5NTlkMTcyZmFhMjI2ZGY4NTQ5YzhhOTg2NTA2MDYxMDAyY2RlMWViNmM0ZThmMDYiLCJpYXQiOjE3MzYyNDY0NzMuMjM3ODk0LCJuYmYiOjE3MzYyNDY0NzMuMjM3ODk1LCJleHAiOjQ4OTE5MjAwNzMuMjMwMjI4LCJzdWIiOiI1NDczMjQxNiIsInNjb3BlcyI6WyJ1c2VyLnJlYWQiLCJ1c2VyLndyaXRlIiwidGFzay5yZWFkIiwidGFzay53cml0ZSIsIndlYmhvb2sucmVhZCIsIndlYmhvb2sud3JpdGUiLCJwcmVzZXQucmVhZCIsInByZXNldC53cml0ZSJdfQ.SGIbHe6DG8UOgiHgDsxhoJhEVQQJZX18fvKY-aiPWqvXY-jYHgkjTYa2tQcRxggCO_0zFSxGUEu3z1IFueGudsxpDaphZcrP-3dhFByCdvx6J6MhDooMcGOTavgiB-7sS1-jWKr2TSdtooBbSMFPLqivwRbTaUZjF5x9kHnGQbVtOm-nmGYWgqczG4c1jNj0i5VzgjzpHLTWeVvCOS99ob-LhwRUSAIInEFoVCDGJPKzVi0uCJe4_zFLlqzErQ0YRxqcfAjnzzF5tJYuOXRLdWsikpV7z9FCz79IMkrfAEvdCzF4tIsfzjXN8V7Y5oms0ICifQXDGJr9USKzpQHRKtZNO3pagJqGtVVOeEIhxKTcNEHdj15CY90HWbdPIsl6Kh-QLWMWWUMIO3MMTETK29G1Qq7TyIrsSYP7rPZjcSM---y4bS59g2bNCc6b12gRZwuS0jK695OKF1lpJtyY81AG9_MoNfcJ77qVTtf5lxsYJwOVGY84byHr0xpjlQUZcTjsz2JoM9zi-Hu8B0BhZdILTpzJpVPXrYBuD_wrVc5P04J_9rm_zoAxrRss2k_QwR2rVi8Or1oVvGD1PW8_fQOg8XTcay7iuPC93fSEEuJH_q2isbpCZ6q2VXRliEfvgq-Q2oCm0uE0Sh22kK7Xxqmr4XquRBixOOaeg1gWXiA"
# OPENAI_API_KEY = "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"
# VIDEO_PATH = "./07. Checkout Page Sign-Ups.mp4"
# AUDIO_URL="https://eu-central.storage.cloudconvert.com/tasks/eed084c6-5881-4d13-ae6b-e6c31bb80c76/test2.mp3?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=cloudconvert-production%2F20250129%2Ffra%2Fs3%2Faws4_request&X-Amz-Date=20250129T061118Z&X-Amz-Expires=86400&X-Amz-Signature=03975049d08def70aba591465267f0ff1605d6bdffc3561540896cdf5fadc811&X-Amz-SignedHeaders=host&response-content-disposition=attachment%3B%20filename%3D%22test2.mp3%22&response-content-type=audio%2Fmpeg&x-id=GetObject"
# AUDIO_PATH = "audio.mp3"
# CLOUDCONVERT_URL = "https://api.cloudconvert.com/v2"
# OPENAI_URL = "https://api.openai.com/v1"

# app = FastAPI()


# @app.post("/convert-video/")
# async def convert_video(file: UploadFile = File(...)):
#     """
#     API Endpoint to accept a video file, convert it to audio, transcribe it, and summarize it.
#     """
#     # Save the uploaded file locally
#     video_path = f"./{file.filename}"
#     with open(video_path, "wb") as buffer:
#         shutil.copyfileobj(file.file, buffer)

#     try:
#         # 1️⃣ Upload Video to CloudConvert
#         file_id = upload_to_cloudconvert(video_path)

#         # 2️⃣ Convert Video to Audio (MP3)
#         job_id = start_conversion(file_id, "mp3")

#         # 3️⃣ Wait for Conversion to Complete
#         time.sleep(10)  # Adjust sleep time based on expected conversion duration
#         job_data = get_job_status(job_id)

#         # Find the correct converted task ID
#         converted_task_id = next(
#             (task["id"] for task in job_data["tasks"] if task["operation"] == "convert" and task["status"] == "finished"),
#             None
#         )
#         if not converted_task_id:
#             raise HTTPException(status_code=400, detail="Conversion task not found.")

#         # 4️⃣ Export Audio File
#         export_job_id = create_export_task(converted_task_id)
#         audio_url = get_export_download_url(export_job_id)
#         audio_path = download_audio(audio_url)

#         # 5️⃣ Transcribe Audio
#         transcript = transcribe_audio(audio_path)

#         # 6️⃣ Summarize Text
#         summary = summarize_text(transcript)

#         return JSONResponse({
#             "message": "Video conversion, transcription, and summarization successful!",
#             "transcript": transcript,
#             "summary": summary
#         })
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     finally:
#         # Cleanup temporary files
#         if os.path.exists(video_path):
#             os.remove(video_path)
#         if os.path.exists(audio_path):
#             os.remove(audio_path)


# # -------------------- Utility Functions --------------------

# def upload_to_cloudconvert(video_path):
#     """Uploads the video to CloudConvert and returns the file ID."""
#     print(f"\n[Uploading File] Video Path: {video_path}")
#     url = f"{CLOUDCONVERT_URL}/import/upload"
#     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}
    
#     response = requests.post(url, json={"filename": os.path.basename(video_path)}, headers=headers)
#     response.raise_for_status()
    
#     upload_data = response.json()["data"]
#     upload_url = upload_data["result"]["form"]["url"]
#     parameters = upload_data["result"]["form"]["parameters"]

#     with open(video_path, "rb") as file:
#         upload_response = requests.post(upload_url, files={"file": file}, data=parameters)
#     upload_response.raise_for_status()

#     return upload_data["id"]


# def start_conversion(file_id, output_format="mp3"):
#     """Starts a CloudConvert job to convert the file to MP3."""
#     url = f"{CLOUDCONVERT_URL}/jobs"
#     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}", "Content-Type": "application/json"}
#     data = {"tasks": {"convert": {"operation": "convert", "input": [file_id], "output_format": output_format}}}

#     response = requests.post(url, json=data, headers=headers)
#     response.raise_for_status()

#     return response.json()["data"]["id"]


# def get_job_status(job_id):
#     """Checks the status of a CloudConvert job."""
#     url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
#     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

#     response = requests.get(url, headers=headers)
#     response.raise_for_status()

#     return response.json()["data"]


# def create_export_task(file_id):
#     """Creates an export task for the converted audio."""
#     url = f"{CLOUDCONVERT_URL}/jobs"
#     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}", "Content-Type": "application/json"}
#     data = {"tasks": {"export": {"operation": "export/url", "input": [file_id]}}}

#     response = requests.post(url, json=data, headers=headers)
#     response.raise_for_status()

#     return response.json()["data"]["id"]


# def get_export_download_url(job_id):
#     """Gets the download URL for the exported file."""
#     url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
#     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

#     response = requests.get(url, headers=headers)
#     response.raise_for_status()

#     job_data = response.json()["data"]

#     for task in job_data["tasks"]:
#         if task["operation"] == "export/url" and task["status"] == "finished":
#             return task["result"]["files"][0]["url"]

#     raise HTTPException(status_code=400, detail="Export task not completed yet.")


# def download_audio(audio_url, output_path="audio.mp3"):
#     """Downloads the converted MP3 file."""
#     response = requests.get(audio_url)
#     response.raise_for_status()

#     with open(output_path, "wb") as file:
#         file.write(response.content)

#     return output_path


# def transcribe_audio(audio_path):
#     """Transcribes the audio using OpenAI Whisper."""
#     url = f"{OPENAI_URL}/audio/transcriptions"
#     headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

#     with open(audio_path, "rb") as audio_file:
#         response = requests.post(url, headers=headers, files={"file": audio_file, "model": (None, "whisper-1")})

#     response.raise_for_status()
#     return response.json()["text"]


# def summarize_text(text):
#     """Summarizes the transcribed text using OpenAI GPT."""
#     url = f"{OPENAI_URL}/chat/completions"
#     headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
#     data = {"model": "gpt-4", "messages": [{"role": "system", "content": "Summarize this transcript:"}, {"role": "user", "content": text}]}

#     response = requests.post(url, json=data, headers=headers)
#     response.raise_for_status()

#     return response.json()["choices"][0]["message"]["content"]

# if __name__ == "__main__":
#     print("\n================ STARTING PROCESS =================")

#     file_id = upload_to_cloudconvert(VIDEO_PATH)
#     print(f"[File Uploaded] File ID: {file_id}")
    
#     job_id = start_conversion(file_id, "mp3")

#     if job_id:
#         print(f"\n[Job Created Successfully] Job ID: {job_id}")
#     else:
#         print("\n[Failed] Could not start conversion.")

#     time.sleep(10)  

#     job_data = get_job_status(job_id)

#     converted_task_id = None
#     for task in job_data["tasks"]:
#         if task["operation"] == "convert" and task["status"] == "finished":
#             converted_task_id = task["id"]
#             break

#     if not converted_task_id:
#         print("[❌] No finished conversion task found. Exiting export process.")
#         exit(1)  
        
#     export_job_id = create_export_task(converted_task_id)
#     audio_url = get_export_download_url(export_job_id)  
#     audio_path = download_audio(audio_url)
#     transcript = transcribe_audio(audio_path)
#     summary = summarize_text(transcript)
#     print("\n================ FINAL OUTPUT =================")
#     print("\n🔊 **Transcription:**\n", transcript)
#     print("\n📝 **Summary:**\n", summary)


#     print("\n================ PROCESS COMPLETE =================")


# # import requests
# # import time
# # import os

# # CLOUDCONVERT_API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiIxIiwianRpIjoiNWUyM2U3Mjk4ZTY0MTk3MjZkZWZmM2M4MjFiNDA4YmI5NTlkMTcyZmFhMjI2ZGY4NTQ5YzhhOTg2NTA2MDYxMDAyY2RlMWViNmM0ZThmMDYiLCJpYXQiOjE3MzYyNDY0NzMuMjM3ODk0LCJuYmYiOjE3MzYyNDY0NzMuMjM3ODk1LCJleHAiOjQ4OTE5MjAwNzMuMjMwMjI4LCJzdWIiOiI1NDczMjQxNiIsInNjb3BlcyI6WyJ1c2VyLnJlYWQiLCJ1c2VyLndyaXRlIiwidGFzay5yZWFkIiwidGFzay53cml0ZSIsIndlYmhvb2sucmVhZCIsIndlYmhvb2sud3JpdGUiLCJwcmVzZXQucmVhZCIsInByZXNldC53cml0ZSJdfQ.SGIbHe6DG8UOgiHgDsxhoJhEVQQJZX18fvKY-aiPWqvXY-jYHgkjTYa2tQcRxggCO_0zFSxGUEu3z1IFueGudsxpDaphZcrP-3dhFByCdvx6J6MhDooMcGOTavgiB-7sS1-jWKr2TSdtooBbSMFPLqivwRbTaUZjF5x9kHnGQbVtOm-nmGYWgqczG4c1jNj0i5VzgjzpHLTWeVvCOS99ob-LhwRUSAIInEFoVCDGJPKzVi0uCJe4_zFLlqzErQ0YRxqcfAjnzzF5tJYuOXRLdWsikpV7z9FCz79IMkrfAEvdCzF4tIsfzjXN8V7Y5oms0ICifQXDGJr9USKzpQHRKtZNO3pagJqGtVVOeEIhxKTcNEHdj15CY90HWbdPIsl6Kh-QLWMWWUMIO3MMTETK29G1Qq7TyIrsSYP7rPZjcSM---y4bS59g2bNCc6b12gRZwuS0jK695OKF1lpJtyY81AG9_MoNfcJ77qVTtf5lxsYJwOVGY84byHr0xpjlQUZcTjsz2JoM9zi-Hu8B0BhZdILTpzJpVPXrYBuD_wrVc5P04J_9rm_zoAxrRss2k_QwR2rVi8Or1oVvGD1PW8_fQOg8XTcay7iuPC93fSEEuJH_q2isbpCZ6q2VXRliEfvgq-Q2oCm0uE0Sh22kK7Xxqmr4XquRBixOOaeg1gWXiA"
# # OPENAI_API_KEY = "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"
# # VIDEO_PATH = "./07. Checkout Page Sign-Ups.mp4"
# # AUDIO_URL="https://eu-central.storage.cloudconvert.com/tasks/eed084c6-5881-4d13-ae6b-e6c31bb80c76/test2.mp3?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=cloudconvert-production%2F20250129%2Ffra%2Fs3%2Faws4_request&X-Amz-Date=20250129T061118Z&X-Amz-Expires=86400&X-Amz-Signature=03975049d08def70aba591465267f0ff1605d6bdffc3561540896cdf5fadc811&X-Amz-SignedHeaders=host&response-content-disposition=attachment%3B%20filename%3D%22test2.mp3%22&response-content-type=audio%2Fmpeg&x-id=GetObject"
# # AUDIO_PATH = "audio.mp3"
# # CLOUDCONVERT_URL = "https://api.cloudconvert.com/v2"
# # OPENAI_URL = "https://api.openai.com/v1"

# # def upload_to_cloudconvert(video_path):
# #     """Uploads the video to CloudConvert and returns the file ID."""
# #     print(f"\n[Uploading File] Video Path: {video_path}")

# #     url = f"{CLOUDCONVERT_URL}/import/upload"
# #     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

# #     response = requests.post(url, json={"filename": os.path.basename(video_path)}, headers=headers)
# #     response.raise_for_status()

# #     upload_data = response.json()["data"]
# #     print(f"[Debug] API Response: {upload_data}")

# #     upload_url = upload_data["result"]["form"]["url"]
# #     parameters = upload_data["result"]["form"]["parameters"]

# #     print(f"[Signed URL Received] Upload URL: {upload_url}")

# #     with open(video_path, "rb") as file:
# #         files = {"file": file}
# #         upload_response = requests.post(upload_url, files=files, data=parameters)

# #     upload_response.raise_for_status()
# #     print(f"[Upload Successful] File ID: {upload_data['id']}")

# #     return upload_data["id"]

# # def check_file_status(file_id):
# #     """Checks the status of the uploaded file."""
# #     url = f"{CLOUDCONVERT_URL}/tasks/{file_id}"
# #     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

# #     response = requests.get(url, headers=headers)
# #     response.raise_for_status()
    
# #     job_data = response.json()
# #     print(f"\n[File Status] File ID: {file_id}")
# #     print(f"Status: {job_data['data']['status']}")

# # def start_conversion(file_id, output_format="mp3"):
# #     """Starts a CloudConvert job to convert the file."""
# #     url = f"{CLOUDCONVERT_URL}/jobs"

# #     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}", "Content-Type": "application/json"}

# #     data = {
# #         "tasks": {
# #             "convert": {
# #                 "operation": "convert",
# #                 "input": [file_id],  # ✅ FIXED: input should be a list
# #                 "output_format": output_format
# #             }
# #         }
# #     }

# #     response = requests.post(url, json=data, headers=headers)
# #     response.raise_for_status()

# #     job_data = response.json()["data"]
# #     job_id = job_data["id"]
# #     print(f"[Conversion Job Created] Job ID: {job_id}")

# #     return job_id

# # def get_job_status(job_id):
# #     """Checks the status of the conversion job."""
# #     url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"

# #     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

# #     response = requests.get(url, headers=headers)
# #     response.raise_for_status()

# #     return response.json()["data"]

# # def create_export_task(file_id):
# #     """Creates an export task to generate a downloadable URL."""
# #     url = f"{CLOUDCONVERT_URL}/jobs"

# #     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}", "Content-Type": "application/json"}

# #     data = {
# #         "tasks": {
# #             "export": {
# #                 "operation": "export/url",
# #                 "input": [file_id]  # ✅ FIXED: input should be a list
# #             }
# #         }
# #     }

# #     response = requests.post(url, json=data, headers=headers)
# #     response.raise_for_status()

# #     job_data = response.json()["data"]
# #     job_id = job_data["id"]
# #     print(f"\n✅ [Export Job Created] Job ID: {job_id}")

# #     return job_id

# # def get_export_download_url(job_id):
# #     """Finds the export task and extracts the download URL."""
# #     url = f"{CLOUDCONVERT_URL}/jobs/{job_id}"
# #     headers = {"Authorization": f"Bearer {CLOUDCONVERT_API_KEY}"}

# #     response = requests.get(url, headers=headers)
# #     response.raise_for_status()

# #     job_data = response.json()["data"]

# #     for task in job_data["tasks"]:
# #         if task["operation"] == "export/url" and task["status"] == "finished":
# #             download_url = task["result"]["files"][0]["url"]
# #             print(f"\n✅ [Download Ready] MP3 File URL: {download_url}")
# #             return download_url

# #     print("[❌] Export task not finished yet. Please wait and try again.")
# #     return None

# # def download_audio(audio_url, output_path="audio.mp3"):
# #     """Downloads the converted MP3 file from CloudConvert."""
# #     print(f"\n⬇️ [Downloading] {output_path} from URL...")

# #     response = requests.get(audio_url)
# #     response.raise_for_status()

# #     with open(output_path, "wb") as file:
# #         file.write(response.content)

# #     print(f"✅ [Download Complete] File saved as: {output_path}")
# #     return output_path

# # def transcribe_audio(audio_path):
# #     print(audio_path)
# #     """Sends the audio file to OpenAI Whisper for transcription."""
# #     print(f"\n🎙️ [Transcribing Audio] File: {audio_path}")

# #     url = f"{OPENAI_URL}/audio/transcriptions"
# #     headers = {
# #         "Authorization": f"Bearer {OPENAI_API_KEY}"
# #     }
    
# #     with open(audio_path, "rb") as audio_file:
# #         files = {"file": audio_file, "model": (None, "whisper-1")}
# #         response = requests.post(url, headers=headers, files=files)

# #     response.raise_for_status()
    
# #     transcript = response.json()["text"]
# #     print(f"✅ [Transcription Complete] Text: {transcript}...")  # Show first 100 chars

# #     return transcript

# # def summarize_text(text):
# #     """Sends the extracted text to OpenAI GPT for summarization."""
# #     print(f"\n📖 [Summarizing Text] Length: {len(text)} characters")

# #     url = f"{OPENAI_URL}/chat/completions"

# #     headers = {
# #         "Authorization": f"Bearer {OPENAI_API_KEY}",
# #         "Content-Type": "application/json"
# #     }

# #     data = {
# #         "model": "gpt-4",
# #         "messages": [
# #             {"role": "system", "content": "Summarize this transcript:"},
# #             {"role": "user", "content": text}
# #         ]
# #     }

# #     response = requests.post(url, json=data, headers=headers)
# #     response.raise_for_status()

# #     summary = response.json()["choices"][0]["message"]["content"]
# #     print(f"✅ [Summarization Complete] Summary: {summary}..")  # Show first 100 chars

# #     return summary


# # if __name__ == "__main__":
# #     print("\n================ STARTING PROCESS =================")

# #     file_id = upload_to_cloudconvert(VIDEO_PATH)
# #     print(f"[File Uploaded] File ID: {file_id}")
    
# #     job_id = start_conversion(file_id, "mp3")

# #     if job_id:
# #         print(f"\n[Job Created Successfully] Job ID: {job_id}")
# #     else:
# #         print("\n[Failed] Could not start conversion.")

# #     time.sleep(10)  

# #     job_data = get_job_status(job_id)

# #     converted_task_id = None
# #     for task in job_data["tasks"]:
# #         if task["operation"] == "convert" and task["status"] == "finished":
# #             converted_task_id = task["id"]
# #             break

# #     if not converted_task_id:
# #         print("[❌] No finished conversion task found. Exiting export process.")
# #         exit(1)  
        
# #     export_job_id = create_export_task(converted_task_id)
# #     audio_url = get_export_download_url(export_job_id)  
# #     audio_path = download_audio(audio_url)
# #     transcript = transcribe_audio(audio_path)
# #     summary = summarize_text(transcript)
# #     print("\n================ FINAL OUTPUT =================")
# #     print("\n🔊 **Transcription:**\n", transcript)
# #     print("\n📝 **Summary:**\n", summary)


# #     print("\n================ PROCESS COMPLETE =================")

