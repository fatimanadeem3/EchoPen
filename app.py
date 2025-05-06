import os
import uuid
import requests
import whisper
from flask import Flask, render_template, request, redirect, send_from_directory, url_for
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
BOOKS_FOLDER = "books"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['BOOKS_FOLDER'] = BOOKS_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BOOKS_FOLDER, exist_ok=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
STABILITY_API_KEY = os.getenv("STABILITY_API_KEY")

def transcribe_audio(file_path):
    model = whisper.load_model("base")
    result = model.transcribe(file_path)
    return result["text"]

def generate_story_text(prompt):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=data)
    result = response.json()
    return result["choices"][0]["message"]["content"] if "choices" in result else "Error generating story."

def generate_image(prompt):
    url = "https://api.stability.ai/v2beta/stable-image/generate/core"
    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}",
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

def extract_title(story_text):
    lines = [line.strip() for line in story_text.split('\n') if line.strip()]
    first_line = lines[0] if lines else "Untitled_Story"
    title_base = first_line.split('.')[0][:50]
    title_clean = "".join(c if c.isalnum() or c in ['_', '-'] else '_' for c in title_base).strip()
    return title_clean or f"Story_{uuid.uuid4().hex[:8]}"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    voice_file = request.files.get("voice")
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

    story = generate_story_text(prompt)
    title = extract_title(story)
    filename = f"{title}.txt"

    with open(os.path.join(BOOKS_FOLDER, filename), "w", encoding="utf-8") as f:
        f.write(story)

    image = generate_image(prompt)
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

@app.route("/books/read/<filename>")
def read_story(filename):
    try:
        file_path = os.path.join(BOOKS_FOLDER, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            story_text = f.read()

        # Try to find associated image (same base name)
        base_name = os.path.splitext(filename)[0]
        image_filename = f"{base_name}.png"
        image_path = os.path.join(BOOKS_FOLDER, image_filename)
        image_url = url_for('book_image', filename=image_filename) if os.path.exists(image_path) else None

        return render_template("read_story.html", title=filename, story=story_text, image_url=image_url)
    except Exception as e:
        return f"Error reading story: {e}", 500


@app.route("/home")
def go_home():
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(debug=True)
