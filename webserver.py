from flask import Flask, render_template, request, send_from_directory, jsonify
import os
import threading

app = Flask('')
FILES_DIRECTORY = 'db'

@app.route("/")
def main():
    return 'Discord bot running.'

@app.route("/dashboard")
def render_dashboard():
    return render_template("index.html")

@app.route("/upload", methods=['POST'])
def upload():
    if request.method == 'POST': 

        # Get the list of files from webpage 
        files = request.files.getlist("file") 

        # Iterate for each file in the files List, and Save them 
        for file in files: 
            file.save(f'db/{file.filename}')

    return render_template("uploaded.html")

@app.route('/files')
def list_files():
    """Endpoint to list all files in the directory."""
    files = os.listdir(FILES_DIRECTORY)
    return jsonify(files)

@app.route('/files/<filename>')
def download_file(filename):
    """Endpoint to serve a specific file."""
    return send_from_directory(FILES_DIRECTORY, filename)

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run)
    t.start()