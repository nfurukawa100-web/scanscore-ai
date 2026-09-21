import os
import base64
from io import BytesIO
from datetime import datetime
from flask import Flask, request, render_template_string
from groq import Groq
from PIL import Image

app = Flask(__name__)

# Initialize Groq client using environment variable
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

LOG_FILE = "grades_record.txt"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ScanScore AI</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f9; color: #333; }
        .container { max-width: 800px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        h1 { text-align: center; color: #0056b3; }
        form { display: flex; flex-direction: column; gap: 15px; }
        label { font-weight: bold; }
        input[type="text"], input[type="file"], textarea { width: 100%; padding: 8px; box-sizing: border-box; }
        button { background-color: #0056b3; color: white; border: none; padding: 12px; font-size: 16px; border-radius: 4px; cursor: pointer; }
        button:hover { background-color: #003d82; }
        .result, .history { margin-top: 20px; padding: 15px; background: #e9ecef; border-radius: 4px; white-space: pre-wrap; word-break: break-word; }
        .error { color: red; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>ScanScore AI Automated Grading</h1>
        <form action="/" method="post" enctype="multipart/form-data">
            <div>
                <label>Student Name:</label>
                <input type="text" name="student_name" placeholder="Optional">
            </div>
            <div>
                <label>Rubric / Rules:</label>
                <textarea name="rubric" rows="4" required placeholder="Enter rubric criteria..."></textarea>
            </div>
            <div>
                <label>Max Points:</label>
                <input type="text" name="max_points" value="100" required>
            </div>
            <div>
                <label>Upload Student Answer Sheet Image:</label>
                <input type="file" name="image" accept="image/*" required>
            </div>
            <button type="submit">Evaluate Answer Sheet</button>
        </form>

        {% if result %}
        <div class="result">
            <h2>Evaluation Result</h2>
            <p>{{ result }}</p>
        </div>
        {% endif %}

        {% if error %}
        <div class="error">
            <h2>Error</h2>
            <p>{{ error }}</p>
        </div>
        {% endif %}

        {% if history %}
        <div class="history">
            <h2>Recent Grading Records</h2>
            <pre>{{ history }}</pre>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        history_data = ""
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    history_data = f.read()
            except Exception:
                history_data = ""
        return render_template_string(HTML_TEMPLATE, history=history_data)

    if not client:
        return render_template_string(HTML_TEMPLATE, error="GROQ_API_KEY environment variable is missing on server.")

    student_name = request.form.get("student_name", "Unidentified").strip() or "Unidentified"
    rubric = request.form.get("rubric", "").strip()
    max_points = request.form.get("max_points", "100").strip()
    file = request.files.get("image")

    if not file:
        return render_template_string(HTML_TEMPLATE, error="Please upload an image file.")

    try:
        image = Image.open(file.stream).convert("RGB")
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")
    except Exception as e:
        return render_template_string(HTML_TEMPLATE, error=f"Image processing failed: {str(e)}")

    prompt = f"""
You are an expert automated grading assistant. Evaluate the provided student response against the rubric.

### Rubric / Rules:
{rubric}

### Maximum Score:
{max_points} Points

### Output Format Requirement:
Return ONLY a raw JSON object with no explanations, markdown code blocks, or extra text.

The JSON must follow this exact structure:
{{
  "student_name": "{student_name}",
  "subject": "Subject Name (or General)",
  "date": "YYYY-MM-DD",
  "final_score": "Total Score (e.g. 18/20)"
}}
"""

    try:
        img_url = f"data:image/jpeg;base64,{base64_image}"

        response = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
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

        grading_result = response.choices[0].message.content
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        os.makedirs(os.path.dirname(os.path.abspath(LOG_FILE)), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n========================================\n")
            f.write(f"TIMESTAMP: {timestamp}\n")
            f.write(f"STUDENT: {student_name}\n")
            f.write(f"----------------------------------------\n")
            f.write(f"RECORD: {grading_result}\n")
            f.write(f"========================================\n")
            f.flush()
            os.fsync(f.fileno())

        with open(LOG_FILE, "r", encoding="utf-8") as f:
            history_data = f.read()

        return render_template_string(HTML_TEMPLATE, result=grading_result, history=history_data)

    except Exception as e:
        history_data = "No records found yet."
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    history_data = f.read()
            except Exception:
                pass
        return render_template_string(HTML_TEMPLATE, error=str(e), history=history_data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
