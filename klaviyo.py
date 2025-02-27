from flask import Flask, render_template, jsonify
import requests
from pyngrok import ngrok
from datetime import datetime
import os
import logging
import time
from urllib3.util import Retry
from requests.adapters import HTTPAdapter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

API_KEY = "pk_de1627559b26ddb83f99657d651e36bb0a"
BASE_URL = "https://a.klaviyo.com/api"
HEADERS = {
    "accept": "application/vnd.api+json",
    "revision": "2025-01-15",
    "content-type": "application/vnd.api+json",
    "Authorization": f"Klaviyo-API-Key {API_KEY}"
}

# Configure retry strategy
retry_strategy = Retry(
    total=3,  # number of retries
    backoff_factor=1,  # wait 1, 2, 4 seconds between retries
    status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
)

# Create session with retry strategy
session = requests.Session()
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("https://", adapter)
session.mount("http://", adapter)

def fetch_campaign_details(campaign_id):
    """Fetch details of a specific campaign using its ID with retry logic"""
    try:
        response = session.get(
            f"{BASE_URL}/campaigns/{campaign_id}",
            headers=HEADERS,
            timeout=10
        )
        response.raise_for_status()
        campaign_data = response.json()
        return campaign_data['data']['attributes']['name']
    except Exception as e:
        logger.error(f"Error fetching campaign details: {str(e)}")
        return None

def fetch_campaign_data():
    """
    Fetches campaign data from Klaviyo API with rate limiting and retry logic
    """
    payload = {
        "data": {
            "type": "campaign-values-report",
            "attributes": {
                "timeframe": {"key": "last_7_days"},
                "statistics": [
                    "recipients",
                    "open_rate",
                    "click_rate",
                    "revenue_per_recipient",
                    "conversion_rate",
                    "delivery_rate",
                    "bounce_rate",
                    "opens",
                    "clicks",
                    "conversions",
                    "conversion_value",
                    "bounced",
                    "spam_complaints",
                    "unsubscribes",
                    "failed"
                ],
                "conversion_metric_id": "WieLr4"
            }
        }
    }

    try:
        logger.info("Fetching campaign data from Klaviyo API")
        
        # Use session instead of requests directly
        response = session.post(
            f"{BASE_URL}/campaign-values-reports", 
            json=payload, 
            headers=HEADERS,
            timeout=10
        )
        
        # If we hit rate limit, wait and retry
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            logger.info(f"Rate limited. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            response = session.post(
                f"{BASE_URL}/campaign-values-reports", 
                json=payload, 
                headers=HEADERS,
                timeout=10
            )

        response.raise_for_status()
        data = response.json()

        # Separate email and SMS campaigns
        email_campaigns = {
            "data": {
                "type": "campaign-values-report",
                "attributes": {
                    "results": [
                        result for result in data['data']['attributes']['results'] 
                        if result['groupings']['send_channel'] == 'email'
                    ]
                }
            }
        }
        sms_campaigns = {
            "data": {
                "type": "campaign-values-report",
                "attributes": {
                    "results": [
                        result for result in data['data']['attributes']['results'] 
                        if result['groupings']['send_channel'] == 'sms'
                    ]
                }
            }
        }

        # Add campaign names
        for campaigns in [email_campaigns, sms_campaigns]:
            for result in campaigns['data']['attributes']['results']:
                campaign_id = result['groupings']['campaign_id']
                # Add delay between campaign name requests to avoid rate limits
                time.sleep(0.5)  # 500ms delay
                campaign_name = fetch_campaign_details(campaign_id)
                result['campaign_name'] = campaign_name

        return {"email": email_campaigns, "sms": sms_campaigns}

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching campaign data: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return None

def fetch_flow_details(flow_id):
    """Fetch details of a specific flow using its ID with retry logic"""
    try:
        logger.info(f"Fetching details for flow ID: {flow_id}")
        response = session.get(
            f"{BASE_URL}/flows/{flow_id}",
            headers=HEADERS,
            timeout=10
        )
        response.raise_for_status()
        flow_data = response.json()
        logger.info(f"Successfully fetched flow details for ID: {flow_id}")
        return flow_data['data']['attributes']['name']
    except Exception as e:
        logger.error(f"Error fetching flow details: {str(e)}")
        return None

def fetch_flow_data():
    """
    Fetches flow data from Klaviyo API with rate limiting and retry logic
    """
    payload = {
        "data": {
            "type": "flow-values-report",
            "attributes": {
                "timeframe": {"key": "last_7_days"},
                "statistics": [
                    "recipients",
                    "open_rate",
                    "click_rate",
                    "revenue_per_recipient",
                    "conversion_rate",
                    "delivery_rate",
                    "bounce_rate",
                    "opens",
                    "clicks",
                    "conversions",
                    "conversion_value",
                    "bounced",
                    "spam_complaints",
                    "unsubscribes",
                    "failed"
                ],
                "conversion_metric_id": "WieLr4"  # Make sure to use your correct metric ID
            }
        }
    }

    try:
        logger.info("Fetching flow data from Klaviyo API")
        
        response = session.post(
            f"{BASE_URL}/flow-values-reports", 
            json=payload, 
            headers=HEADERS,
            timeout=10
        )
        
        # Log response status and headers for debugging
        logger.info(f"Flow API Response Status: {response.status_code}")
        logger.info(f"Flow API Response Headers: {dict(response.headers)}")
        
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            response = session.post(
                f"{BASE_URL}/flow-values-reports", 
                json=payload, 
                headers=HEADERS,
                timeout=10
            )

        response.raise_for_status()
        data = response.json()
        logger.info("Successfully received flow data")

        # Separate email and SMS flows
        email_flows = {
            "data": {
                "type": "flow-values-report",
                "attributes": {
                    "results": [
                        result for result in data['data']['attributes']['results'] 
                        if result['groupings']['send_channel'] == 'email'
                    ]
                }
            }
        }
        sms_flows = {
            "data": {
                "type": "flow-values-report",
                "attributes": {
                    "results": [
                        result for result in data['data']['attributes']['results'] 
                        if result['groupings']['send_channel'] == 'sms'
                    ]
                }
            }
        }

        # Add flow names
        for flows in [email_flows, sms_flows]:
            for result in flows['data']['attributes']['results']:
                flow_id = result['groupings']['flow_id']
                time.sleep(0.5)  # 500ms delay to avoid rate limits
                flow_name = fetch_flow_details(flow_id)
                result['flow_name'] = flow_name

        logger.info("Successfully processed flow data")
        return {"email": email_flows, "sms": sms_flows}

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching flow data: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in fetch_flow_data: {str(e)}")
        logger.exception("Full traceback:")
        return None

@app.route('/')
def dashboard():
    """Renders the dashboard template"""
    return render_template('dashboard.html')

@app.route('/api/campaign-data')
def get_campaign_data():
    """API endpoint to fetch campaign data with error handling"""
    try:
        data = fetch_campaign_data()
        if data:
            return jsonify(data)
        return jsonify({"error": "Failed to fetch data"}), 500
    except Exception as e:
        logger.error(f"Error in get_campaign_data: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/api/flow-data')
def get_flow_data():
    """API endpoint to fetch flow data with error handling"""
    try:
        data = fetch_flow_data()
        if data:
            return jsonify(data)
        return jsonify({"error": "Failed to fetch flow data"}), 500
    except Exception as e:
        logger.error(f"Error in get_flow_data: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

def cleanup_ngrok():
    """Cleanup function to kill existing ngrok processes"""
    try:
        os.system('taskkill /f /im ngrok.exe')
        logger.info("Successfully killed existing ngrok processes")
    except Exception as e:
        logger.error(f"Error killing ngrok processes: {str(e)}")

if __name__ == '_main_':
    try:
        # Run Flask app
        app.run(debug=True, port=5000)
    except Exception as e:
        logger.error(f"Error starting server: {str(e)}")
        # Cleanup on error
        try:
            ngrok.kill()
        except:
            pass