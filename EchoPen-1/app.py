import os
import uuid
import requests
import whisper
from flask import Flask, render_template, request, redirect, send_from_directory, url_for, session
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Folder setup
UPLOAD_FOLDER = "uploads"
BOOKS_FOLDER = "books"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BOOKS_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['BOOKS_FOLDER'] = BOOKS_FOLDER

# Whisper transcription
def transcribe_audio(file_path):
    model = whisper.load_model("base")
    result = model.transcribe(file_path)
    return result["text"]

# Story generation (Groq or fallback)
def generate_story_text(prompt, groq_api_key):
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
    result = response.json()
    return result["choices"][0]["message"]["content"] if "choices" in result else "Error generating story."

# Image generation (Stability AI)
def generate_image(prompt, stability_api_key):
    url = "https://api.stability.ai/v2beta/stable-image/generate/core"
    headers = {
        "Authorization": f"Bearer {stability_api_key}",
        "Accept": "image/*"
    }
    files = {
        "prompt": (None, prompt),
        "output_format": (None, "png")
    }
    response = requests.post(url, headers=headers, files=files)

    if response.status_code == 200:
        image_name = f"{uuid.uuid4()}.png"
        image_path = os.path.join(BOOKS_FOLDER, image_name)
        with open(image_path, "wb") as f:
            f.write(response.content)
        return image_name
    else:
        print("Image generation failed:", response.status_code, response.text)
        return None

@app.route("/", methods=["GET", "POST"])
def enter_keys():
    if request.method == "POST":
        session['GROQ_API_KEY'] = request.form['groq_key']
        session['STABILITY_API_KEY'] = request.form['stability_key']
        return redirect(url_for('home'))
    return render_template("enter_keys.html")

@app.route("/home")
def home():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    groq_key = session.get("GROQ_API_KEY")
    stability_key = session.get("STABILITY_API_KEY")

    if not groq_key or not stability_key:
        return redirect(url_for('enter_keys'))

    voice_file = request.files.get("voice")
    prompt = ""

    if voice_file and voice_file.filename:
        filename = str(uuid.uuid4()) + os.path.splitext(voice_file.filename)[-1]
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        voice_file.save(file_path)
        prompt = transcribe_audio(file_path)
    else:
        hero = request.form.get("hero")
        villain = request.form.get("villain")
        nature = request.form.get("nature")
        side = request.form.get("side")
        prompt = f"Write a children's story with hero: {hero}, villain: {villain}, theme: {nature}, side characters: {side}."

    story = generate_story_text(prompt, groq_key)

    # Create safe filename
    title = story.strip().split('\n')[0].strip().split('.')[0][:50]
    safe_title = "".join(c if c.isalnum() or c in [' ', '-', '_'] else '_' for c in title).strip().replace(" ", "_")
    story_filename = f"{safe_title}.txt"

    with open(os.path.join(BOOKS_FOLDER, story_filename), "w") as f:
        f.write(story)

    image = generate_image(prompt, stability_key)
    image_url = url_for('book_image', filename=image) if image else None

    return render_template("book.html", story=story, image=image, image_url=image_url)

@app.route("/books/image/<filename>")
def book_image(filename):
    return send_from_directory(BOOKS_FOLDER, filename)

@app.route("/books/view")
def view_saved():
    books = [f for f in os.listdir(BOOKS_FOLDER) if f.endswith(".txt")]
    return render_template("saved.html", books=books)

@app.route("/books/download/<filename>")
def download(filename):
    return send_from_directory(BOOKS_FOLDER, filename, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
