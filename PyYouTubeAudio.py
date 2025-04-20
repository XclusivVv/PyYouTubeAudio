import os
import sys
import subprocess
import json
import time
import threading
import random
import itertools
import msvcrt  # Windows-only
import pafy
import vlc
from colorama import Fore, Style, init

init(autoreset=True)

HISTORY_FILE = "history.json"
DARK_MODE = [False]  # toggle with 'd'

# ────────────────────────────────────────────────────────────────
# ── THEME UTILS ─────────────────────────────────────────────────

def color(text, role):
    if DARK_MODE[0]:
        colors = {
            "info": Fore.CYAN,
            "error": Fore.LIGHTRED_EX,
            "warn": Fore.LIGHTYELLOW_EX,
            "play": Fore.LIGHTGREEN_EX,
            "title": Fore.LIGHTBLUE_EX,
        }
    else:
        colors = {
            "info": Fore.BLUE,
            "error": Fore.RED,
            "warn": Fore.YELLOW,
            "play": Fore.GREEN,
            "title": Fore.CYAN,
        }
    return f"{colors.get(role, '')}{text}{Style.RESET_ALL}"

# ────────────────────────────────────────────────────────────────
# ── HISTORY SUPPORT ─────────────────────────────────────────────

def save_to_history(title, url):
    history = load_history()
    history.insert(0, {"title": title, "url": url})
    history = history[:10]
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def prompt_history():
    history = load_history()
    if not history:
        return None
    print(color("[HISTORY] Previously played:", "info"))
    for i, item in enumerate(history, 1):
        print(color(f"[{i}] {item['title']}", "play"))
    try:
        choice = int(input(color(f"Enter number (1-{len(history)}) to replay, or 0 to skip: ", "info")))
        if 1 <= choice <= len(history):
            return history[choice - 1]['url']
    except ValueError:
        pass
    return None

# ────────────────────────────────────────────────────────────────
# ── YOUTUBE SEARCH ──────────────────────────────────────────────

def search_youtube(query):
    print(color("[SEARCHING] Searching YouTube for:", "info") + f" {query}")
    try:
        cmd = ['yt-dlp', f'ytsearch5:{query}', '--flat-playlist', '--dump-json', '--no-warnings']
        result = subprocess.run(cmd, capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        return [{"title": json.loads(line)['title'], "url": f"https://www.youtube.com/watch?v={json.loads(line)['id']}"} for line in lines]
    except Exception as e:
        print(color(f"[EXCEPTION] Search failed: {e}", "error"))
        return []

# ────────────────────────────────────────────────────────────────
# ── PLAYBACK ────────────────────────────────────────────────────

def play_audio(youtube_url):
    try:
        loop_enabled = [False]
        paused = [False]

        cmd = ['yt-dlp', '-f', 'bestaudio', '-g', youtube_url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        stream_url = result.stdout.strip()

        title_cmd = ['yt-dlp', '--get-title', youtube_url]
        title_result = subprocess.run(title_cmd, capture_output=True, text=True)
        video_title = title_result.stdout.strip()

        print(color("[PLAYING]", "play") + f" {video_title}")
        print(color("[CONTROLS]", "info") + " Press P=Pause, L=Loop, D=DarkMode, Q=Quit\n")

        player = vlc.MediaPlayer(stream_url)
        player.play()
        save_to_history(video_title, youtube_url)

        def keyboard_listener():
            while True:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8').lower()
                    if key == 'p':
                        player.pause()
                        paused[0] = not paused[0]
                        print(color(f"[{'Paused' if paused[0] else 'Resumed'}]", "warn"))
                    elif key == 'l':
                        loop_enabled[0] = not loop_enabled[0]
                        print(color(f"[Loop {'On' if loop_enabled[0] else 'Off'}]", "warn"))
                    elif key == 'd':
                        DARK_MODE[0] = not DARK_MODE[0]
                        print(color(f"[Dark Mode {'Enabled' if DARK_MODE[0] else 'Disabled'}]", "warn"))
                    elif key == 'q':
                        print(color("[STOPPING] Quitting playback...", "error"))
                        player.stop()
                        break
                time.sleep(0.1)

        def visualizer():
            frames = itertools.cycle([
                "|▁▂▃▄▅▆▇█▇▆▅▄▃▂▁|",
                "|▁▃▅▇█▇▅▃▁|",
                "|█▇▆▅▄▃▂▁|",
                "|▇▇▇▇▇▇▇▇|",
                "|▁▁▁▁▁▁▁▁|"
            ])
            while True:
                if player.get_state() in [vlc.State.Ended, vlc.State.Stopped, vlc.State.Error]:
                    break
                if not paused[0]:
                    print(color(next(frames), "title"), end='\r')
                time.sleep(0.15)

        threading.Thread(target=keyboard_listener, daemon=True).start()
        threading.Thread(target=visualizer, daemon=True).start()

        while True:
            state = player.get_state()
            if state == vlc.State.Ended:
                if loop_enabled[0]:
                    player.stop()
                    player = vlc.MediaPlayer(stream_url)
                    player.play()
                    continue
                else:
                    print(color("\n[DONE] Playback ended.", "warn"))
                    break
            elif state in [vlc.State.Stopped, vlc.State.Error]:
                break
            time.sleep(1)

    except Exception as e:
        print(color(f"[EXCEPTION] Failed to play: {e}", "error"))
        print(color("Tip:", "warn") + " Try searching again or using a different video.")

# ────────────────────────────────────────────────────────────────
# ── MAIN FLOW ───────────────────────────────────────────────────

def main():
    os.system("title PyYouTubeAudio")
    os.system('cls' if os.name == 'nt' else 'clear')
    print(color("YouTube Audio Streamer - Python Edition", "title"))

    reuse = prompt_history()
    if reuse:
        play_audio(reuse)
        return

    query = input(color("Enter search query: ", "info"))
    videos = search_youtube(query)
    if not videos:
        return

    print(color("[RESULTS] Choose a video to stream:", "warn"))
    for idx, vid in enumerate(videos, 1):
        print(color(f"[{idx}] {vid['title']}", "play"))
    try:
        choice = int(input(color(f"Enter number (1-{len(videos)}): ", "info")))
        if 1 <= choice <= len(videos):
            play_audio(videos[choice - 1]['url'])
    except ValueError:
        print(color("[ERROR] Invalid input.", "error"))

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(color("\n[EXIT] Interrupted by user.", "warn"))
        sys.exit(0)
