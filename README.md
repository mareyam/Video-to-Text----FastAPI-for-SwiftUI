# Video Processing API with CloudConvert and OpenAI

This FastAPI application processes uploaded MP4 videos by converting them to MP3 audio, transcribing the audio using OpenAI Whisper, and then summarizing the transcript using OpenAI GPT-4.

---

## Features

- Upload MP4 video files via `/process_video/` endpoint  
- Converts video to MP3 using CloudConvert API  
- Transcribes audio with OpenAI Whisper API  
- Summarizes transcription using OpenAI GPT-4 API  
- Provides progress logs via `/current_step`  
- Fetches results by filename via `/results/{filename}`  
- Async processing in background thread  

---

## Requirements

- Python 3.8+  
- FastAPI  
- Requests  
- python-dotenv  

---

## Setup

1. Clone the repo

2. Create a `.env` file with the following variables:

```env
CLOUDCONVERT_API_KEY=your_cloudconvert_api_key
CLOUDCONVERT_URL=https://api.cloudconvert.com/v2
OPENAI_API_KEY=your_openai_api_key
OPENAI_URL=https://api.openai.com/v1
```

## Install dependencies

```bash
pip install fastapi requests python-dotenv uvicorn
```
#### Install dependencies
```bash
pip install fastapi requests python-dotenv uvicorn
```


## API Endpoints

### GET /

Returns a welcome message.

### POST /process_video/

Upload an MP4 video file to start processing (conversion, transcription, summary).  
Returns immediately with a message to check progress.

### GET /current_step

Returns current logs and progress steps of the ongoing processing.

### GET /results/{filename}

Returns the processing results including MP3 URL, transcript, and summary for the uploaded video.

---

## How It Works

1. Upload a `.mp4` video file to `/process_video/`.  
2. The file is uploaded to CloudConvert and converted to MP3.  
3. The app polls CloudConvert for job completion.  
4. Once converted, it exports and retrieves the MP3 URL.  
5. The MP3 audio is sent to OpenAI Whisper for transcription.  
6. The transcription text is sent to OpenAI GPT-4 for summarization.  
7. Results are stored and accessible via `/results/{filename}`.  
8. Logs and progress can be tracked at `/current_step`.

---

## Notes

- Only `.mp4` video files are accepted.  
- Processing happens asynchronously; results may take some time.  
- Error logs are stored and available via `/current_step`.  
- Uses environment variables for sensitive keys.
