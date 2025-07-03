import os
import logging
import json
import uuid
import re
import subprocess
import unicodedata
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from flask import Flask, request, jsonify, render_template, session, send_from_directory
from werkzeug.exceptions import BadRequest
from dotenv import load_dotenv
import yt_dlp

# Load environment variables
load_dotenv()

FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'default_secret_key')

# Output folder
OUTPUT_FOLDER = os.path.join(os.path.expanduser("~"), "Desktop", "mySongs")
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

USER_DATA_FILE = 'users.json'

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask app setup
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

def load_users():
    if os.path.isfile(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users(data):
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ... [Your existing helper functions like sanitize_title, download_youtube_audio, etc.] ...

users = load_users()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/service', methods=['POST'])
def run_service():
    try:
        if not request.is_json:
            raise BadRequest("請用 JSON 格式送出請求")

        data = request.get_json()
        url = data.get('input')

        url = normalize_youtube_url(url)
        url = clean_youtube_url(url)

        if not url or not ('youtube.com' in url or 'youtu.be' in url):
            raise BadRequest("請輸入有效的 YouTube 影片網址")

        fmt = data.get('format', 'mp3')
        quality = data.get('quality', '192')

        # Remove payment and usage limit checks entirely
        user_id = session.setdefault('user_id', str(uuid.uuid4()))
        user = users.get(user_id, {"usage": 0})

        links = {}
        files = []

        if fmt == 'mp3':
            mp3_path, title = download_youtube_audio(url, quality)
            links['mp3'] = f"/download/{os.path.basename(mp3_path)}"
            files.append(os.path.basename(mp3_path))
        elif fmt == 'm4a':
            mp3_path, title = download_youtube_audio(url, quality)
            m4a_path = convert_to_m4a(mp3_path)
            links['m4a'] = f"/download/{os.path.basename(m4a_path)}"
            files.append(os.path.basename(m4a_path))
        elif fmt == 'mp4':
            mp4_path, title = download_youtube_video(url, quality)
            links['mp4'] = f"/download/{os.path.basename(mp4_path)}"
            files.append(os.path.basename(mp4_path))
        else:
            raise BadRequest("不支援的格式")

        m3u_path = generate_m3u(title, files)
        links['m3u'] = f"/download/{os.path.basename(m3u_path)}"

        user["usage"] += 1
        users[user_id] = user
        save_users(users)

        return jsonify({'status': 'success', 'message': f"{title} 已完成！", 'download_links': links})

    except BadRequest as e:
        logger.warning(f"Bad request: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        logger.error(f"Service error: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'伺服器發生錯誤: {str(e)}'}), 500

# ... [Other routes like /download] ...

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    logger.info(f"Flask app running on port {port}, saving files to {OUTPUT_FOLDER}")
    app.run(host='0.0.0.0', port=port, debug=False)
