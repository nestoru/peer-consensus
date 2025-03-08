#!/usr/bin/env python3
"""
review_opinions.py

Starts a Flask web server that allows users to review the converged discussion
responses stored in per-model SQLite databases for a given session folder.
Each model’s responses are displayed in reverse chronological order with a preview,
and a button to expand the full response.
"""

import os
import sqlite3
import click
import webbrowser
from flask import Flask, render_template_string, request, redirect, url_for

app = Flask(__name__)

# HTML template using render_template_string for simplicity.
HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Peer Consensus - Review Opinions</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2em; }
    .model-section { margin-bottom: 2em; }
    .response { border: 1px solid #ccc; padding: 1em; margin-bottom: 1em; }
    .header { font-weight: bold; margin-bottom: 0.5em; }
    .preview { cursor: pointer; color: blue; text-decoration: underline; }
    .full { display: none; white-space: pre-wrap; background: #f9f9f9; padding: 0.5em; margin-top: 0.5em; }
  </style>
  <script>
    function toggleResponse(id) {
      var x = document.getElementById(id);
      if (x.style.display === "none") {
        x.style.display = "block";
      } else {
        x.style.display = "none";
      }
    }
  </script>
</head>
<body>
  <h1>Review Opinions for Session: {{ session_folder }}</h1>
  {% for model_name, responses in data.items() %}
    <div class="model-section">
      <h2>Model: {{ model_name }}</h2>
      {% for resp in responses %}
        <div class="response">
          <div class="header">
            Response #{{ resp.response_number }} | Convergence: {{ resp.convergence }}% | Timestamp: {{ resp.timestamp }}
          </div>
          <div class="preview" onclick="toggleResponse('resp-{{ model_name }}-{{ resp.response_number }}')">
            {{ resp.preview }}
            [ + ]
          </div>
          <div class="full" id="resp-{{ model_name }}-{{ resp.response_number }}">
            {{ resp.response }}
          </div>
        </div>
      {% endfor %}
    </div>
  {% endfor %}
</body>
</html>
"""

def fetch_responses_from_db(db_path: str):
    """Fetch responses from a SQLite DB and return them as a list of dicts in descending order."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT response_number, response, convergence, timestamp FROM responses ORDER BY response_number DESC")
    rows = cursor.fetchall()
    conn.close()
    responses = []
    for row in rows:
        response_number, response, convergence, timestamp = row
        # Create a preview: take the first two non-empty lines (or first 100 characters if less than two lines)
        lines = [line.strip() for line in response.splitlines() if line.strip()]
        if len(lines) >= 2:
            preview = "\n".join(lines[:2])
        else:
            preview = response[:100] + ("..." if len(response) > 100 else "")
        responses.append({
            "response_number": response_number,
            "response": response,
            "convergence": convergence,
            "timestamp": timestamp,
            "preview": preview
        })
    return responses

def load_session_data(session_folder: str):
    """
    Scans the session_folder for *.db files.
    Returns a dict: {model_name: responses_list}
    where model_name is derived from the file name (without extension).
    """
    data = {}
    for file in os.listdir(session_folder):
        if file.endswith(".db"):
            model_name = os.path.splitext(file)[0]
            db_path = os.path.join(session_folder, file)
            responses = fetch_responses_from_db(db_path)
            data[model_name] = responses
    return data

@app.route("/")
def index():
    session_folder = app.config.get("SESSION_FOLDER")
    if not session_folder or not os.path.exists(session_folder):
        return "Invalid session folder configuration.", 400
    data = load_session_data(session_folder)
    return render_template_string(HTML_TEMPLATE, data=data, session_folder=os.path.basename(session_folder))

@click.command()
@click.option("--session-folder", required=True, type=click.Path(exists=True), help="Path to the session folder containing model DB files.")
@click.option("--port", default=5000, type=int, help="Port to run the review server on.")
def review_opinions(session_folder, port):
    """Launches the review-opinions web UI for a given session folder."""
    app.config["SESSION_FOLDER"] = session_folder
    url = f"http://127.0.0.1:{port}/"
    # Open the browser after a slight delay
    import threading, time
    def open_browser():
        time.sleep(1)
        webbrowser.open(url)
    threading.Thread(target=open_browser).start()
    app.run(host="127.0.0.1", port=port)

if __name__ == "__main__":
    review_opinions()

