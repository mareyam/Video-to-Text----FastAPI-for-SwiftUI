import requests
import io

def transcribe_audio_from_url(audio_url, api_key):
    try:
        # Step 1: Stream the audio file from the URL
        audio_response = requests.get(audio_url, stream=True)
        if audio_response.status_code != 200:
            print("Error downloading audio file:", audio_response.status_code)
            return
        
        # Step 2: Wrap the streamed content in a file-like object
        audio_file = io.BytesIO(audio_response.content)

        # Step 3: Prepare form-data for OpenAI API
        files = {
            'file': ('audio.mp3', audio_file, 'audio/mpeg')  # Send file-like object
        }
        data = {
            'model': 'whisper-1'
        }
        headers = {
            'Authorization': f'Bearer {api_key}'
        }

        # Step 4: Send request to OpenAI API
        response = requests.post("https://api.openai.com/v1/audio/transcriptions", files=files, data=data, headers=headers)

        # Step 5: Print response
        if response.status_code == 200:
            print("Transcription:", response.json().get('text'))
        else:
            print("Error:", response.json())

    except Exception as e:
        print("An error occurred:", str(e))

AUDIO_URL = "https://eu-central.storage.cloudconvert.com/tasks/f682b608-53d6-4f95-9ee3-0213afdf0bc3/test4.mp3?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=cloudconvert-production%2F20250205%2Ffra%2Fs3%2Faws4_request&X-Amz-Date=20250205T072217Z&X-Amz-Expires=86400&X-Amz-Signature=cf4d20713c3338553c2ce22ee65f4f30011e2c39a4ce89c8ea15e8d05c8b2c76&X-Amz-SignedHeaders=host&response-content-disposition=attachment%3B%20filename%3D%22test4.mp3%22&response-content-type=audio%2Fmpeg&x-id=GetObject"
API_KEY = "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"
transcribe_audio_from_url(AUDIO_URL, API_KEY)
