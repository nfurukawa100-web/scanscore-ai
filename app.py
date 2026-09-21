import os
import base64
from datetime import datetime
from flask import Flask, request, render_template_string, jsonify
from groq import Groq
from io import BytesIO
from PIL import Image

app = Flask(__name__)

# Initialize Groq client
client = Groq()

# Storage path for local archival ledger on Android/Termux
LOG_FILE = os.path.join(os.getcwd(), "grades_record.txt")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>ScanScore AI</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    
    <!-- PWA & Mobile App Settings -->
    <meta name="theme-color" content="#0f172a">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="ScanScore AI">
    <link rel="manifest" href="/manifest.json">
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📝</text></svg>">
    
    <style>
        :root {
            --bg-gradient: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            --card-bg: rgba(30, 41, 59, 0.75);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #10b981;
            --accent-hover: #059669;
            --border: rgba(255, 255, 255, 0.08);
            --input-bg: rgba(15, 23, 42, 0.6);
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            background: var(--bg-gradient); 
            color: var(--text-main); 
            padding: 20px; 
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: flex-start;
            -webkit-tap-highlight-color: transparent;
        }
        
        .dashboard {
            max-width: 1100px;
            width: 100%;
            display: grid;
            grid-template-columns: 1.2fr 1fr;
            gap: 24px;
            margin-top: 10px;
        }
        
        @media (max-width: 900px) {
            .dashboard { grid-template-columns: 1fr; }
        }
        
        .card { 
            background: var(--card-bg); 
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            padding: 24px; 
            border-radius: 20px; 
            box-shadow: 0 20px 40px rgba(0,0,0,0.4); 
            border: 1px solid var(--border);
            height: fit-content;
        }
        
        .header { text-align: center; margin-bottom: 20px; }
        .header .logo { font-size: 28px; font-weight: 800; background: linear-gradient(to right, #10b981, #3b82f6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .subtitle { font-size: 12px; color: var(--text-muted); margin-top: 4px; font-weight: 500; letter-spacing: 0.5px; }
        
        label { display: block; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; color: #10b981; }
        
        input[type="text"], input[type="file"], input[type="number"], textarea { 
            width: 100%; 
            background: var(--input-bg); 
            color: var(--text-main); 
            padding: 12px 16px; 
            margin-bottom: 16px; 
            border: 1px solid var(--border); 
            border-radius: 10px; 
            font-size: 14px; 
            outline: none; 
        }
        
        .row { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; }
        
        button { 
            width: 100%; 
            background: linear-gradient(135deg, var(--accent) 0%, #059669 100%); 
            color: white; 
            padding: 14px; 
            border: none; 
            border-radius: 10px; 
            font-size: 15px; 
            font-weight: 700; 
            cursor: pointer; 
            box-shadow: 0 8px 20px rgba(16, 185, 129, 0.25);
            transition: transform 0.1s active;
        }

        button:active { transform: scale(0.98); }
        
        .loader-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(15, 23, 42, 0.95);
            z-index: 9999;
            justify-content: center;
            align-items: center;
            flex-direction: column;
        }
        .spinner {
            width: 50px; height: 50px;
            border: 5px solid rgba(255,255,255,0.1);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 1s infinite linear;
            margin-bottom: 20px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        .result-panel { 
            background: rgba(15, 23, 42, 0.5); 
            padding: 20px; 
            border-radius: 12px; 
            margin-top: 20px; 
            border-left: 4px solid var(--accent);
            border-top: 1px solid var(--border);
            border-right: 1px solid var(--border);
            border-bottom: 1px solid var(--border);
        }
        .result-panel h3 { font-size: 14px; font-weight: 700; margin-bottom: 10px; color: var(--accent); text-transform: uppercase; }
        .result-body { font-size: 14px; line-height: 1.6; white-space: pre-wrap; color: #e2e8f0; }
        
        .ledger-card {
            background: var(--card-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-radius: 20px;
            border: 1px solid var(--border);
            padding: 24px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
            height: fit-content;
        }
        .ledger-header { font-size: 15px; font-weight: 700; color: #60a5fa; margin-bottom: 16px; }
        .ledger-content { 
            font-family: monospace; 
            font-size: 12px; 
            background: rgba(15, 23, 42, 0.8); 
            padding: 16px; 
            border-radius: 10px; 
            max-height: 500px;
            overflow-y: auto; 
            white-space: pre-wrap; 
            color: #cbd5e1; 
            border: 1px solid var(--border);
            line-height: 1.5;
        }
    </style>
</head>
<body>
    <div id="loader" class="loader-overlay">
        <div class="spinner"></div>
        <h3 style="color: white; font-weight: 600;">AI is evaluating paper...</h3>
        <p style="color: var(--text-muted); margin-top: 8px; font-size: 13px;">Transcribing & saving to ledger</p>
    </div>

    <div class="dashboard">
        <div class="card">
            <div class="header">
                <div class="logo">ScanScore AI</div>
                <div class="subtitle">AUTOMATED GRADING & ARCHIVAL LEDGER</div>
            </div>
            
            <form method="POST" enctype="multipart/form-data" onsubmit="showLoader()">
                <label>Student Reference / ID</label>
                <input type="text" name="student_name" placeholder="e.g., John Doe - Quiz 1" required>

                <label>Capture / Upload Answer Sheet</label>
                <input type="file" name="image" accept="image/*" capture="environment" required>
                
                <div class="row">
                    <div>
                        <label>Grading Rubric / Answer Key</label>
                        <textarea name="rubric" rows="3" placeholder="Provide correct answers or evaluation criteria..." required></textarea>
                    </div>
                    <div>
                        <label>Max Scale</label>
                        <input type="number" name="max_points" value="10" min="1" required>
                    </div>
                </div>
                
                <button type="submit">Analyze Paper & Save</button>
            </form>
            
            {% if result %}
            <div class="result-panel">
                <h3>Latest System Output (Archived ✅)</h3>
                <div class="result-body">{{ result }}</div>
            </div>
            {% endif %}
        </div>

        <div class="ledger-card">
            <div class="ledger-header">📂 Permanent Archival Ledger</div>
            <div class="ledger-content">{{ history_data }}</div>
        </div>
    </div>

    <script>
        function showLoader() {
            document.getElementById('loader').style.display = 'flex';
        }
    </script>
</body>
</html>
"""

# Dynamic JSON App Manifest endpoint
@app.route("/manifest.json")
def manifest():
    return jsonify({
        "short_name": "ScanScore",
        "name": "ScanScore AI Grader",
        "start_url": "/",
        "background_color": "#0f172a",
        "theme_color": "#0f172a",
        "display": "standalone",
        "icons": [
            {
                "src": "data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📝</text></svg>",
                "sizes": "192x192 512x512",
                "type": "image/svg+xml"
            }
        ]
    })

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        student_name = request.form.get("student_name")
        file = request.files.get("image")
        rubric = request.form.get("rubric")
        max_points = request.form.get("max_points")
        
        if file:
            img = Image.open(file.stream)
            img.thumbnail((900, 900))
            
            buffered = BytesIO()
            img.save(buffered, format="JPEG", quality=85)
            base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            prompt = f"""
You are an expert automated grading assistant. Evaluate the handwritten text provided in the image.

### Rubric / Rules:
{rubric}

### Maximum Score:
{max_points} Points

### Output Format Requirement:
Return ONLY a raw JSON object with no explanations, markdown code blocks, or extra text.

The JSON must follow this exact structure:
{
  "student_name": "Student Full Name (or Unidentified)",
  "subject": "Subject Name (or General)",
  "date": "YYYY-MM-DD (or current date)",
  "final_score": "Total Score (e.g. 18/20)"
}
""
          try:
                response = client.chat.completions.create(
                    model="qwen/qwen3.6-27b",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                img_url = f"data:image/jpeg;base64,{base64_image}"
{"type": "image_url", "image_url": {"url": img_url}}
                            ]
                        }
                    ],
                    temperature=0.2
                )
                
                grading_result = response.choices[0].message.content
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(f"\n=========================================\n")
                    f.write(f"TIMESTAMP: {timestamp}\n")
                    f.write(f"STUDENT: {student_name}\n")
                    f.write(f"-----------------------------------------\n")
                    f.write(f"RECORD: {grading_result}\n")
                    f.write(f"=========================================\n")
                    f.flush()
                    os.fsync(f.fileno())
                
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    history_data = f.read()
                    
                return render_template_string(HTML_TEMPLATE, result=grading_result, history_data=history_data)
                
            except Exception as e:
                history_data = "No records found yet."
                if os.path.exists(LOG_FILE):
                    with open(LOG_FILE, "r", encoding="utf-8") as f:
                        history_data = f.read()
                return render_template_string(HTML_TEMPLATE, result=f"Error processing evaluation: {str(e)}", history_data=history_data)
                
    history_data = "No records found yet."
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            history_data = f.read()
    return render_template_string(HTML_TEMPLATE, result=None, history_data=history_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

