import os
import csv
import base64
from io import BytesIO
from datetime import datetime, timezone, timedelta
from flask import Flask, request, render_template_string, redirect, url_for, send_file, Response
from groq import Groq
from PIL import Image

app = Flask(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

LOG_FILE = "grades_record.csv"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ScanScore AI</title>
    
    <!-- PWA Settings -->
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#0056b3">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="ScanScore AI">
    <link rel="apple-touch-icon" href="https://cdn-icons-png.flaticon.com/512/3429/3429149.png">

    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f9; color: #333; }
        .container { max-width: 850px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #0056b3; margin-bottom: 5px; }
        .pwa-banner { display: none; background: #e7f3ff; border: 1px solid #b6d4fe; color: #084298; padding: 10px 15px; border-radius: 6px; margin-bottom: 15px; text-align: center; font-weight: bold; }
        .pwa-btn { background-color: #28a745; color: white; border: none; padding: 6px 12px; margin-left: 10px; border-radius: 4px; cursor: pointer; font-size: 14px; }
        form { display: flex; flex-direction: column; gap: 15px; }
        label { font-weight: bold; }
        input[type="text"], input[type="file"], textarea { width: 100%; padding: 8px; box-sizing: border-box; }
        button { background-color: #0056b3; color: white; border: none; padding: 12px; font-size: 16px; border-radius: 4px; cursor: pointer; }
        button:hover { background-color: #003d82; }
        .result { margin-top: 20px; padding: 15px; background: #e9ecef; border-radius: 4px; word-break: break-word; }
        .feedback-box { background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px 15px; margin-top: 10px; border-radius: 4px; font-size: 14px; max-height: 250px; overflow-y: auto; }
        .online-notice { background: #d1e7dd; border: 1px solid #badbcc; color: #0f5132; padding: 10px; border-radius: 4px; margin-top: 10px; font-size: 14px; }
        .history { margin-top: 30px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #0056b3; color: white; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        .action-group { display: flex; gap: 10px; margin-top: 15px; flex-wrap: wrap; }
        .export-btn { background-color: #28a745; padding: 10px 15px; font-size: 14px; text-decoration: none; color: white; border-radius: 4px; text-align: center; display: inline-block; }
        .export-btn:hover { background-color: #218838; }
        .clear-btn { background-color: #dc3545; padding: 10px 15px; font-size: 14px; }
        .clear-btn:hover { background-color: #bd2130; }
        .error { color: red; font-weight: bold; }
        
        #loading-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(255, 255, 255, 0.95);
            z-index: 9999;
            text-align: center;
            padding-top: 35vh;
            font-size: 22px;
            font-weight: bold;
            color: #0056b3;
        }
    </style>
</head>
<body>
    <div id="loading-overlay">
        ⚡ Scanning 50-Item Test Sheet...<br>
        <span style="font-size: 14px; font-weight: normal; color: #666;">Analyzing high-res grid and matching answers...</span>
    </div>

    <div class="container">
        <div id="installBanner" class="pwa-banner">
            📱 Install ScanScore AI on your phone/device!
            <button id="installBtn" class="pwa-btn">Install App</button>
        </div>

        <h1>ScanScore AI</h1>
        <p style="text-align: center; font-size: 13px; color: #666; margin-top: 0;">High-Capacity 50-Item Batch Grading (PHT)</p>

        <form id="grade-form" action="/" method="post" enctype="multipart/form-data">
            <div>
                <label>Subject Name:</label>
                <input type="text" id="subject" name="subject" placeholder="e.g., Midterm Exam - 50 Items" required>
            </div>
            <div>
                <label>Student Name:</label>
                <input type="text" id="student_name" name="student_name" placeholder="Student name">
            </div>
            <div>
                <label>Answer Key (1-50):</label>
                <textarea id="answer_key" name="answer_key" rows="4" required placeholder="Enter answer key (e.g. 1. A 2. C 3. B ... or comma-separated)"></textarea>
            </div>
            <div>
                <label>Max Points:</label>
                <input type="text" id="max_points" name="max_points" value="50" required>
            </div>
            <div>
                <label>Capture / Upload Answer Sheet Image (High-Res):</label>
                <input type="file" id="image_input" accept="image/*" capture="environment" required>
                <input type="hidden" id="compressed_image" name="compressed_image">
            </div>
            <button type="submit" id="submit-btn">Evaluate 50-Item Sheet</button>
        </form>

        {% if result %}
        <div class="result">
            <h2>Evaluation Result</h2>
            <p style="font-size: 18px;"><strong>Score Output:</strong> <span style="color: #28a745;">{{ result }}</span></p>
            {% if feedback %}
            <div class="feedback-box">
                <strong>🔍 Detailed Itemized Mistake Breakdown (1-50):</strong>
                <p style="margin: 5px 0 0 0; white-space: pre-line;">{{ feedback }}</p>
            </div>
            {% endif %}
            <div class="online-notice">
                🚀 <strong>High-Res Vision Active:</strong> Processed 50 items successfully in PHT.
            </div>
        </div>
        {% endif %}

        {% if error %}
        <div class="error">
            <h2>Error</h2>
            <p>{{ error }}</p>
        </div>
        {% endif %}

        <div class="history">
            <h2>Recent Grading Records (PHT)</h2>
            {% if history_rows %}
            <table>
                <tr>
                    <th>Timestamp (PHT)</th>
                    <th>Subject</th>
                    <th>Student</th>
                    <th>Score</th>
                    <th>Mistake Breakdown</th>
                </tr>
                {% for row in history_rows %}
                <tr>
                    <td>{{ row[0] }}</td>
                    <td>{{ row[1] }}</td>
                    <td>{{ row[2] }}</td>
                    <td>{{ row[3] }}</td>
                    <td>{{ row[4] if row|length > 4 else 'N/A' }}</td>
                </tr>
                {% endfor %}
            </table>
            <div class="action-group">
                <a href="/download" class="export-btn">📥 Save Records to File (CSV)</a>
                <form action="/clear" method="post" style="display:inline;">
                    <button type="submit" class="clear-btn" onclick="return confirm('Are you sure you want to clear all history records?');">Clear History</button>
                </form>
            </div>
            {% else %}
            <p>No records found yet.</p>
            {% endif %}
        </div>
    </div>

    <canvas id="canvas" style="display:none;"></canvas>

    <script>
        const subjectInput = document.getElementById('subject');
        const answerKeyInput = document.getElementById('answer_key');
        const maxPointsInput = document.getElementById('max_points');

        if (localStorage.getItem('saved_subject')) subjectInput.value = localStorage.getItem('saved_subject');
        if (localStorage.getItem('saved_answer_key')) answerKeyInput.value = localStorage.getItem('saved_answer_key');
        if (localStorage.getItem('saved_max_points')) maxPointsInput.value = localStorage.getItem('saved_max_points');

        const imageInput = document.getElementById('image_input');
        const compressedImageField = document.getElementById('compressed_image');

        imageInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = function(event) {
                const img = new Image();
                img.onload = function() {
                    const canvas = document.getElementById('canvas');
                    const ctx = canvas.getContext('2d');
                    
                    // Increased to 1400px so 50-item text is crystal clear for the AI
                    const MAX_WIDTH = 1400;
                    let width = img.width;
                    let height = img.height;
                    
                    if (width > MAX_WIDTH) {
                        height *= MAX_WIDTH / width;
                        width = MAX_WIDTH;
                    }
                    
                    canvas.width = width;
                    canvas.height = height;
                    ctx.drawImage(img, 0, 0, width, height);
                    
                    // Higher quality (85%) for dense 50-item sheets
                    const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
                    compressedImageField.value = dataUrl;
                }
                img.src = event.target.result;
            }
            reader.readAsDataURL(file);
        });

        document.getElementById('grade-form').addEventListener('submit', function(e) {
            if (!compressedImageField.value) {
                e.preventDefault();
                alert('Please select or capture an image first!');
                return;
            }
            localStorage.setItem('saved_subject', subjectInput.value);
            localStorage.setItem('saved_answer_key', answerKeyInput.value);
            localStorage.setItem('saved_max_points', maxPointsInput.value);
            document.getElementById('loading-overlay').style.display = 'block';
        });

        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js').catch(err => console.log('SW registration failed', err));
        }

        let deferredPrompt;
        const installBanner = document.getElementById('installBanner');
        const installBtn = document.getElementById('installBtn');

        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            deferredPrompt = e;
            installBanner.style.display = 'block';
        });

        installBtn.addEventListener('click', () => {
            installBanner.style.display = 'none';
            if (deferredPrompt) {
                deferredPrompt.prompt();
                deferredPrompt.userChoice.then(() => { deferredPrompt = null; });
            }
        });
    </script>
</body>
</html>
"""

MANIFEST_JSON = """{
  "short_name": "ScanScore AI",
  "name": "ScanScore AI Automated Grading",
  "icons": [
    {
      "src": "https://cdn-icons-png.flaticon.com/512/3429/3429149.png",
      "type": "image/png",
      "sizes": "512x512"
    }
  ],
  "start_url": "/",
  "background_color": "#f4f4f9",
  "theme_color": "#0056b3",
  "display": "standalone",
  "orientation": "portrait"
}"""

SW_JS = """
const CACHE_NAME = 'scanscore-v10';
const urlsToCache = ['/'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request).catch(() => caches.match('/'));
    })
  );
});
"""

def load_history():
    rows = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if len(row) >= 4:
                        rows.append(row)
        except Exception:
            pass
    return rows[::-1]

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template_string(HTML_TEMPLATE, history_rows=load_history())

    subject = request.form.get("subject", "General").strip() or "General"
    student_name = request.form.get("student_name", "Unidentified").strip() or "Unidentified"
    answer_key = request.form.get("answer_key", "").strip()
    max_points = request.form.get("max_points", "50").strip()
    compressed_image = request.form.get("compressed_image")

    if not compressed_image:
        return render_template_string(HTML_TEMPLATE, error="Please capture or select an image.", history_rows=load_history())

    try:
        header, encoded = compressed_image.split(",", 1)
        image_data = base64.b64decode(encoded)
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"Image decoding failed: {str(e)}", history_rows=load_history())

    grading_result = f"0/{max_points}"
    feedback_text = "Evaluation completed."

    # Groq API Request tuned for high-density 50-item sheets with extended output tokens
    if client:
        try:
            prompt = f"""
You are an expert automated grading assistant grading a high-density test paper with up to 50 items. Carefully compare the student's written answers in the image against the provided answer key.

### Subject:
{subject}

### Answer Key (1 to {max_points}):
{answer_key}

### Maximum Score:
{max_points} Points

### Output Format Requirement:
Return your response in two parts separated strictly by a vertical pipe symbol (`|`):
Part 1: The final score only (e.g., 42/50 or 50/50).
Part 2: A list of specifically which item numbers the student got wrong and brief notes on the incorrect answers.

Example format:
45/50 | Incorrect items: #12 (answered B, correct is A), #28 (blank), #41 (miscalculated).
"""
            img_url = f"data:image/jpeg;base64,{encoded}"
            response = client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": img_url}}
                        ]
                    }
                ],
                temperature=0.1,
                max_tokens=1500  # Allows enough output length for 50 items breakdown
            )
            raw_output = response.choices[0].message.content.strip()
            
            if "|" in raw_output:
                parts = raw_output.split("|", 1)
                grading_result = parts[0].strip()
                feedback_text = parts[1].strip()
            else:
                grading_result = raw_output
                feedback_text = "50-item evaluation completed."
        except Exception as e:
            grading_result = f"Error"
            feedback_text = f"AI grading failed: {str(e)}"

    # Philippine Standard Time (PHT: UTC+8)
    ph_timezone = timezone(timedelta(hours=8))
    timestamp = datetime.now(ph_timezone).strftime("%Y-%m-%d %H:%M:%S")

    file_exists = os.path.exists(LOG_FILE)
    os.makedirs(os.path.dirname(os.path.abspath(LOG_FILE)), exist_ok=True)
    
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Timestamp (PHT)", "Subject", "Student Name", "Score", "Mistake Breakdown"])
        writer.writerow([timestamp, subject, student_name, grading_result, feedback_text])
        f.flush()
        os.fsync(f.fileno())

    return render_template_string(HTML_TEMPLATE, result=grading_result, feedback=feedback_text, history_rows=load_history())

@app.route("/manifest.json")
def manifest():
    return Response(MANIFEST_JSON, mimetype="application/json")

@app.route("/sw.js")
def service_worker():
    return Response(SW_JS, mimetype="application/javascript")

@app.route("/download", methods=["GET"])
def download_records():
    if os.path.exists(LOG_FILE):
        return send_file(LOG_FILE, as_attachment=True, download_name="grades_export_pht.csv")
    return redirect(url_for('index'))

@app.route("/clear", methods=["POST"])
def clear_history():
    if os.path.exists(LOG_FILE):
        try:
            os.remove(LOG_FILE)
        except Exception:
            pass
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
