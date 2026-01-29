import os
import subprocess
import json
import csv
import sys
from datetime import datetime

# ==============================
# CONFIGURAÇÕES
# ==============================
VIDEO_DIR = r"K:\musicas\Karaoke"
LOG_FILE = "conversao_log.csv"


# ==============================
# UTILIDADES
# ==============================
def ffprobe_streams(file_path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_streams",
        "-of", "json",
        file_path
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0 or not result.stdout:
        return None

    data = json.loads(result.stdout)
    return data.get("streams", [])


def get_codecs(file_path):
    streams = ffprobe_streams(file_path)

    if not streams:
        return None, None

    video_codec = None
    audio_codec = None

    for s in streams:
        if s.get("codec_type") == "video" and not video_codec:
            video_codec = s.get("codec_name")
        elif s.get("codec_type") == "audio" and not audio_codec:
            audio_codec = s.get("codec_name")

    return video_codec, audio_codec


def is_h264_aac(file_path):
    codecs = get_codecs(file_path)
    if not codecs:
        return False

    video, audio = codecs
    return (
        video and audio and
        video.lower() == "h264" and
        audio.lower() == "aac"
    )


def is_valid_video(file_path):
    cmd = [
        "ffmpeg",
        "-v", "error",
        "-i", file_path,
        "-f", "null",
        "-"
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    return result.returncode == 0


# ==============================
# CONVERSÃO
# ==============================
def convert_video(file_path):
    base, _ = os.path.splitext(file_path)
    temp_file = base + "_temp.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-i", file_path,

        "-map", "0:v:0",
        "-map", "0:a:0",

        "-c:v", "libx264",
        "-profile:v", "main",
        "-level", "3.1",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "23",

        "-c:a", "aac",
        "-b:a", "128k",

        "-movflags", "+faststart",
        temp_file
    ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if result.returncode != 0:
        return False, result.stderr

    os.replace(temp_file, file_path)
    return True, None


# ==============================
# LOG CSV
# ==============================
def init_log():
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "data",
                "arquivo",
                "video_codec",
                "audio_codec",
                "status",
                "mensagem"
            ])


def log(file_name, vcodec, acodec, status, msg=""):
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            file_name,
            vcodec,
            acodec,
            status,
            msg
        ])


# ==============================
# MAIN
# ==============================
def main(target_file=None):
    init_log()

    files = []

    if target_file:
        files.append(os.path.join(VIDEO_DIR, target_file))
    else:
        for f in os.listdir(VIDEO_DIR):
            if f.lower().endswith(".mp4"):
                files.append(os.path.join(VIDEO_DIR, f))

    for file_path in files:
        name = os.path.basename(file_path)

        if not os.path.exists(file_path):
            print(f"[NÃO EXISTE] {name}")
            log(name, "", "", "ERRO", "Arquivo não encontrado")
            continue

        video_codec, audio_codec = get_codecs(file_path)

        if not video_codec or not audio_codec:
            print(f"[INVÁLIDO] {name} (sem streams)")
            log(name, video_codec, audio_codec, "INVÁLIDO", "Sem streams")
            continue

        if is_h264_aac(file_path):
            print(f"[OK] {name} já está em H.264 + AAC — pulando")
            log(name, video_codec, audio_codec, "PULADO", "Já compatível")
            continue

        if not is_valid_video(file_path):
            print(f"[CORROMPIDO] {name}")
            log(name, video_codec, audio_codec, "CORROMPIDO", "FFmpeg não consegue ler")
            continue

        print(f"[CONVERTENDO] {name}")
        success, err = convert_video(file_path)

        if success:
            print(f"[CONVERTIDO] {name}")
            log(name, "h264", "aac", "CONVERTIDO", "Sucesso")
        else:
            print(f"[ERRO FFMPEG] {name}")
            log(name, video_codec, audio_codec, "ERRO", err)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main()
