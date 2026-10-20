import os
import base64
from io import BytesIO
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, url_for, send_file
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
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f9; color: #333; }
        .container { max-width: 850px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #0056b3; }
        form { display: flex; flex-direction: column; gap: 15px; }
        label { font-weight: bold; }
        input[type="text"], input[type="file"], textarea { width: 100%; padding: 8px; box-sizing: border-box; }
        button { background-color: #0056b3; color: white; border: none; padding: 12px; font-size: 16px; border-radius: 4px; cursor: pointer; }
        button:hover { background-color: #003d82; }
        .result { margin-top: 20px; padding: 15px; background: #e9ecef; border-radius: 4px; word-break: break-word; }
        .history { margin-top: 30px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; }
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
            background: rgba(255, 255, 255, 0.9);
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
        ⏳ Evaluating Answer Sheet...<br>
        <span style="font-size: 14px; font-weight: normal; color: #666;">Please wait, AI is scanning the image...</span>
    </div>

    <div class="container">
        <h1>ScanScore AI Automated Grading</h1>
        <form id="grade-form" action="/" method="post" enctype="multipart/form-data">
            <div>
                <label>Subject Name:</label>
                <input type="text" id="subject" name="subject" placeholder="e.g., Mathematics 10" required>
            </div>
            <div>
                <label>Student Name:</label>
                <input type="text" id="student_name" name="student_name" placeholder="Optional student name">
            </div>
            <div>
                <label>Answer Key / Correct Answers:</label>
                <textarea id="answer_key" name="answer_key" rows="4" required placeholder="Enter correct answers or key criteria..."></textarea>
            </div>
            <div>
                <label>Max Points:</label>
                <input type="text" id="max_points" name="max_points" value="100" required>
            </div>
            <div>
                <label>Capture / Upload Answer Sheet Image:</label>
                <input type="file" name="image" accept="image/*" capture="environment" required>
            </div>
            <button type="submit">Evaluate Answer Sheet</button>
        </form>

        {% if result %}
        <div class="result">
            <h2>Evaluation Result</h2>
            <p><strong>Score Output:</strong> {{ result }}</p>
        </div>
        {% endif %}

        {% if error %}
        <div class="error">
            <h2>Error</h2>
            <p>{{ error }}</p>
        </div>
        {% endif %}

        <div class="history">
            <h2>Recent Grading Records</h2>
            {% if history_rows %}
            <table>
                <tr>
                    <th>Timestamp</th>
                    <th>Subject</th>
                    <th>Student</th>
                    <th>Score</th>
                </tr>
                {% for row in history_rows %}
                <tr>
                    <td>{{ row[0] }}</td>
                    <td>{{ row[1] }}</td>
                    <td>{{ row[2] }}</td>
                    <td>{{ row[3] }}</td>
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

    <script>
        const subjectInput = document.getElementById('subject');
        const answerKeyInput = document.getElementById('answer_key');
        const maxPointsInput = document.getElementById('max_points');

        if (localStorage.getItem('saved_subject')) subjectInput.value = localStorage.getItem('saved_subject');
        if (localStorage.getItem('saved_answer_key')) answerKeyInput.value = localStorage.getItem('saved_answer_key');
        if (localStorage.getItem('saved_max_points')) maxPointsInput.value = localStorage.getItem('saved_max_points');

        document.getElementById('grade-form').addEventListener('submit', function() {
            localStorage.setItem('saved_subject', subjectInput.value);
            localStorage.setItem('saved_answer_key', answerKeyInput.value);
            localStorage.setItem('saved_max_points', maxPointsInput.value);
            document.getElementById('loading-overlay').style.display = 'block';
        });
    </script>
</body>
</html>
"""

def load_history():
    rows = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split(";")
                    if len(parts) == 4:
                        rows.append(parts)
        except Exception:
            pass
    return rows[::-1]

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template_string(HTML_TEMPLATE, history_rows=load_history())

    if not client:
        return render_template_string(HTML_TEMPLATE, error="GROQ_API_KEY environment variable is missing on server.", history_rows=load_history())

    subject = request.form.get("subject", "General").strip() or "General"
    student_name = request.form.get("student_name", "Unidentified").strip() or "Unidentified"
    answer_key = request.form.get("answer_key", "").strip()
    max_points = request.form.get("max_points", "100").strip()
    file = request.files.get("image")

    if not file:
        return render_template_string(HTML_TEMPLATE, error="Please upload or capture an image file.", history_rows=load_history())

    try:
        image = Image.open(file.stream).convert("RGB")
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"Image processing failed: {str(e)}", history_rows=load_history())

    prompt = f"""
You are an expert automated grading assistant. Evaluate the provided student response against the answer key.

### Subject:
{subject}

### Answer Key / Correct Answers:
{answer_key}

### Maximum Score:
{max_points} Points

### Output Format Requirement:
Return ONLY the final score format (e.g. 18/20 or 95/100) with no explanations, markdown code blocks, or extra text.
"""

    try:
        img_url = f"data:image/jpeg;base64,{base64_image}"

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
            temperature=0.2
        )

        grading_result = response.choices[0].message.content.strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        os.makedirs(os.path.dirname(os.path.abspath(LOG_FILE)), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{timestamp};{subject};{student_name};{grading_result}\n")
            f.flush()
            os.fsync(f.fileno())

        return render_template_string(HTML_TEMPLATE, result=grading_result, history_rows=load_history())

    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=str(e), history_rows=load_history())

@app.route("/download", methods=["GET"])
def download_records():
    if os.path.exists(LOG_FILE):
        return send_file(LOG_FILE, as_attachment=True, download_name="grades_export.csv")
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
