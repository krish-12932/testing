import os
import uuid
import glob
import time
from flask import Flask, render_template, request, send_file, after_this_request, flash, redirect, url_for
import yt_dlp

app = Flask(__name__)
app.secret_key = str(uuid.uuid4())  # Random secret key for flash messages
DOWNLOAD_FOLDER = 'downloads'

# Ensure download folder exists
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

def cleanup_old_files():
    """Cleanup files older than 5 minutes to prevent storage buildup"""
    try:
        now = time.time()
        for f in glob.glob(os.path.join(DOWNLOAD_FOLDER, '*')):
            if os.stat(f).st_mtime < now - 300: # 5 minutes
                os.remove(f)
    except Exception as e:
        print(f"Error cleaning up: {e}")

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    cleanup_old_files()
    
    url = request.form.get('url')
    if not url:
        flash("Please enter a URL", "error")
        return redirect(url_for('index'))

    # Generate unique ID for this download
    download_id = str(uuid.uuid4())
    
    # yt-dlp options
    ydl_opts = {
        'format': 'best[ext=mp4]/best',  # Download best MP4 available
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{download_id}.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'extractor_args':{
            'youtube':{
                'player_client':['android', 'web']
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info_dict)
            
            # If format was not mp4, it might have merged or changed ext, fix filename check
            if not os.path.exists(filename):
                # Try to find the file if extension differs (yt-dlp sometimes merges to mkv/webm if best is not mp4)
                # But we requested ext=mp4, so it should be fine or use ffmpeg to merge. 
                # If ffmpeg is missing, it might download webm.
                # Let's glob for the download_id
                files = glob.glob(os.path.join(DOWNLOAD_FOLDER, f'{download_id}.*'))
                if files:
                    filename = files[0]
                else:
                    raise Exception("File not found after download.")

            # Schedule file deletion after request is finished
            @after_this_request
            def remove_file(response):
                try:
                    os.remove(filename)
                except Exception as e:
                    print(f"Error deleting file: {e}")
                return response

            # Get the original title for the download filename
            download_name = info_dict.get('title', 'video') + os.path.splitext(filename)[1]
            # Sanitize filename somewhat for browser download
            download_name = "".join([c for c in download_name if c.isalpha() or c.isdigit() or c==' ' or c=='.']).rstrip()
            
            return send_file(filename, as_attachment=True, download_name=download_name)
            
    except Exception as e:
        flash(f"Error: {str(e).split(';')[0]}", "error") # Simple error message
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)

