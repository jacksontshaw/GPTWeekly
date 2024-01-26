import time
import openai
import spotipy
import requests
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from flask import Flask, request, url_for, session, redirect

openai.api_key = 'key'

app = Flask(__name__)
app.config['SESSION_COOKIE_NAME'] = 'Spotify Cookie'
app.secret_key = 'key'
TOKEN_INFO = 'token_info'

@app.route('/')
def login():
    auth_url = create_spotify_oauth().get_authorize_url()
    return redirect(auth_url)

@app.route('/redirect')
def redirect_page():
    session.clear()
    code = request.args.get('code')
    token_info = create_spotify_oauth().get_access_token(code)
    session[TOKEN_INFO] = token_info
    return redirect(url_for('save_discover_weekly', _external=True))

@app.route('/save_discover_weekly')
def save_discover_weekly():
    try:
        token_info = get_token()
        sp = spotipy.Spotify(auth=token_info['access_token'])
        user_id = sp.current_user()['id']

        current_playlists = sp.current_user_playlists()['items']

        # Debug: Print names of all playlists
        for playlist in current_playlists:
            print(f"Playlist Name: {playlist['name']}")

        discover_weekly_playlist_id = None
        saved_weekly_playlist_id = None

        for playlist in current_playlists:
            if playlist['name'] == 'Discover Weekly':
                discover_weekly_playlist_id = playlist['id']
            if playlist['name'] == 'GPT Weekly':
                saved_weekly_playlist_id = playlist['id']

        if not discover_weekly_playlist_id:
            return 'Discover Weekly not found'

        if not saved_weekly_playlist_id:
            new_playlist = sp.user_playlist_create(user_id, 'GPT Weekly', True)
            saved_weekly_playlist_id = new_playlist['id']

        discover_weekly_playlist = sp.playlist_items(discover_weekly_playlist_id)
        song_uris = []
        for song in discover_weekly_playlist['items']:
            song_uri = song['track']['uri']
            song_uris.append(song_uri)

        user_id = sp.current_user()['id']

        # Get 2 unique song recommendations for each seed from Discover Weekly songs
        try:
            recommended_songs = get_recommendations_from_chatgpt(song_uris)
        except SpotifyException as e:
            print(f"SpotifyException: {e}")
            return 'An error occurred. Please check logs for details.'
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return 'An unexpected error occurred. Please check logs for details.'

        # Convert recommended_songs to a list of URIs
        recommended_song_uris = [f"spotify:track:{song_id}" for song_id in recommended_songs]

        # Add the tracks to the Saved Weekly playlist
        try:
            sp.user_playlist_add_tracks(user_id, saved_weekly_playlist_id, recommended_song_uris, position=None)
        except SpotifyException as e:
            print(f"SpotifyException while adding tracks: {e}")
            return 'An error occurred while adding tracks to the playlist. Please check logs for details.'
        except Exception as e:
            print(f"An unexpected error occurred while adding tracks: {e}")
            return 'An unexpected error occurred while adding tracks to the playlist. Please check logs for details.'

        return 'Discover Weekly songs added successfully'
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return 'An unexpected error occurred. Please check logs for details.'

def get_token():
    token_info = session.get(TOKEN_INFO, None)
    if not token_info:
        redirect(url_for('login', _external=False))

    now = int(time.time())
    is_expired = token_info['expires_at'] - now < 60
    if is_expired:
        spotify_oauth = create_spotify_oauth()
        token_info = spotify_oauth.refresh_access_token(token_info['refresh_token'])

    return token_info

def create_spotify_oauth():
    return SpotifyOAuth(
        client_id='b942c298187743ac9f57452d7c166b28',
        client_secret='886a6305ad23464a85d49bfefc99e307',
        redirect_uri=url_for('redirect_page', _external=True),
        scope='user-library-read playlist-modify-public playlist-modify-private'
    )

def get_recommendations_from_chatgpt(seed_songs):
    chatgpt_url = 'https://api.openai.com/v1/engines/davinci/generate'
    chatgpt_api_key = 'your_chatgpt_api_key'

    recommended_songs = []

    for seed_song in seed_songs:
        prompt = f'Recommend 2 songs similar to {seed_song}'

        response = requests.post(
            chatgpt_url,
            headers={'Authorization': f'Bearer {chatgpt_api_key}'},
            json={
                'prompt': prompt,
                'max_tokens': 100  # Increase max_tokens to get more output
            },
            timeout=10
        )

        if response.status_code == 200:
            response_json = response.json()
            for choice in response_json['choices']:
                recommended_song = choice['text']
                recommended_songs.append(recommended_song)

    return recommended_songs

if __name__ == "__main__":
    app.run(debug=True)
