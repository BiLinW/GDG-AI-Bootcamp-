import os
from flask import Flask, request, redirect, session, render_template
import google.generativeai as genai
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# 1. Setup & Config
load_dotenv()
app = Flask(__name__)
app.secret_key =os.getenv("FLASK_SECRET_KEY")

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-3-flash-preview')

# 2. Spotify OAuth Helper
def get_spotify_oauth():
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
        scope="playlist-modify-public"
    )

# 3. Routes
@app.route('/')
def index():
    # If we don't have a token, show the login page
    auth_manager = get_spotify_oauth()
    if not auth_manager.validate_token(auth_manager.cache_handler.get_cached_token()):
        auth_url = auth_manager.get_authorize_url()
        return render_template('index.html', auth_url=auth_url, logged_in=False)
    
    return render_template('index.html', logged_in=True)

@app.route('/callback')
def callback():
    # Spotify sends the user back here with a 'code'
    auth_manager = get_spotify_oauth()
    auth_manager.get_access_token(request.args.get("code"))
    return redirect('/')

@app.route('/generate', methods=['POST'])
def generate():
    vibe = request.form.get('vibe')
    
    # --- Step A: Ask Gemini for songs ---
    prompt = f"Act as a professional DJ. Create a list of 10 songs based on this vibe: {vibe}. Return only the list in the format: Artist - Song Title. No intro or outro text."
    ai_response = model.generate_content(prompt)
    song_lines = ai_response.text.strip().split('\n')

    # --- Step B: Initialize Spotify ---
    auth_manager = get_spotify_oauth()
    sp = spotipy.Spotify(auth_manager=auth_manager)
    user_id = sp.current_user()['id']

    # --- Step C: Search for Songs & Get URIs ---
    track_uris = []
    for line in song_lines:
        results = sp.search(q=line, limit=1, type='track')
        tracks = results['tracks']['items']
        if tracks:
            track_uris.append(tracks[0]['uri'])

    # --- Step D: Create Playlist & Add Tracks ---
    playlist = sp.user_playlist_create(user_id, f"Gemini Vibe: {vibe[:20]}", public=True)
    if track_uris:
        sp.playlist_add_items(playlist['id'], track_uris)

    return render_template('success.html', playlist_url=playlist['external_urls']['spotify'])

if __name__ == '__main__':
    app.run(debug=True)