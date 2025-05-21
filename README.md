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

