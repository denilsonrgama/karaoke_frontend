# karaoke_frontend/musicas/views.py
from django.utils import timezone as dj_timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import (
    JsonResponse,
    StreamingHttpResponse,
    Http404,
    HttpResponse,
    HttpResponseRedirect,
)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core import signing
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.models import AuditEvent, MusicaEstatistica, SiteConfiguration, UserPlay
from musicas.models import Musica
from .models import Musica
from django.views.decorators.csrf import ensure_csrf_cookie
from .services import buscar_musica_por_codigo, buscar_musicas
import mimetypes
import math
import os
import re
import subprocess
import tempfile
import threading
from urllib.parse import quote
from django.db.models import F
from payments.models import ContributionPayment


# Token válido por 5 minutos
TOKEN_TTL = 300  # segundos
TONE_CACHE_MAX_BYTES = int(getattr(settings, "TONE_CACHE_MAX_BYTES", 2 * 1024 * 1024 * 1024))
TONE_JOBS = {}
TONE_JOBS_LOCK = threading.Lock()
FREE_SONG_LIMIT = int(getattr(settings, "FREE_SONG_LIMIT", 2))


def user_song_limit(user):
    return int(getattr(user, "song_limit", None) or FREE_SONG_LIMIT)


def is_user_released(user):
    paid_until = getattr(user, "access_expires_at", None)
    has_paid_access = bool(paid_until and paid_until > dj_timezone.now())
    return bool(user.is_staff or user.is_superuser or getattr(user, "access_released", False) or has_paid_access)


def user_usage_context(user):
    used = user.song_plays.count()
    limit = user_song_limit(user)
    return {
        "access_released": is_user_released(user),
        "song_limit": limit,
        "songs_used": used,
        "songs_remaining": max(limit - used, 0),
    }


def paid_access_context(user):
    now = dj_timezone.now()
    access_until = getattr(user, "access_expires_at", None)
    last_payment = (
        ContributionPayment.objects
        .filter(user=user, status=ContributionPayment.STATUS_APPROVED)
        .order_by("-approved_at", "-created_at")
        .first()
    )

    context = {
        "paid_access_active": bool(access_until and access_until > now),
        "paid_access_until": access_until,
        "last_paid_package": last_payment,
    }

    if access_until and access_until > now:
        remaining_seconds = max(int((access_until - now).total_seconds()), 0)
        hours, remainder = divmod(remaining_seconds, 3600)
        minutes = remainder // 60
        if hours and minutes:
            remaining_label = f"{hours} hora(s) e {minutes} minuto(s)"
        elif hours:
            remaining_label = f"{hours} hora(s)"
        else:
            remaining_label = f"{minutes} minuto(s)"
        context["paid_access_remaining_label"] = remaining_label

    return context


def user_can_access_music(user, codigo):
    if is_user_released(user):
        return True

    codigo_norm = str(codigo).zfill(5)
    if user.song_plays.filter(codigo=codigo_norm).exists():
        return True

    return user.song_plays.count() < user_song_limit(user)


def limit_reached_response(request, json_response=False):
    message = (
        "Voce ja utilizou todas as musicas do periodo de teste gratuito. "
        "Para continuar, pedimos contribuir com desenvolvimento de nosso site clicando aqui."
    )
    if json_response:
        return JsonResponse(
            {
                "ok": False,
                "requires_release": True,
                "message": message,
                "payment_url": reverse("payments:payment_page"),
            },
            status=403,
        )

    messages.warning(request, message)
    return redirect("payments:payment_page")


def ensure_music_access(request, codigo, json_response=False):
    if user_can_access_music(request.user, codigo):
        return None
    return limit_reached_response(request, json_response=json_response)


def mark_user_play(request, codigo, musica_dict):
    codigo_norm = str(codigo).zfill(5)
    return UserPlay.objects.get_or_create(
        user=request.user,
        codigo=codigo_norm,
        defaults={
            "nome": musica_dict.get("nome") or "",
            "artista": musica_dict.get("artista") or "",
        },
    )


def safe_next_url(request, fallback_url):
    next_url = request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback_url


def validate_stream_token(request, codigo):
    token = request.GET.get("token")
    if not token:
        return JsonResponse({"error": "Token nÃ£o fornecido"}, status=403)

    try:
        token_codigo = signing.loads(token, salt="video-stream", max_age=TOKEN_TTL)
    except signing.SignatureExpired:
        return JsonResponse({"error": "Token expirado"}, status=403)
    except signing.BadSignature:
        return JsonResponse({"error": "Token invÃ¡lido"}, status=403)

    codigo_norm = str(codigo).zfill(5)
    if codigo_norm != token_codigo:
        return JsonResponse({"error": "Token nÃ£o corresponde"}, status=403)

    return None


def video_source_from_musica(musica_dict):
    video_base_url = getattr(settings, "VIDEO_BASE_URL", "").rstrip("/")
    if video_base_url:
        caminho_video = str(musica_dict["caminho_video"]).replace("\\", "/").lstrip("/")
        return f"{video_base_url}/{quote(caminho_video, safe='/')}"

    return os.path.join(settings.MEDIA_ROOT, musica_dict["caminho_video"])


def parse_tom(tom):
    try:
        semitones = int(tom)
    except ValueError:
        return None

    if semitones < -6 or semitones > 6:
        return None
    return semitones


def tone_cache_dir():
    path = os.path.join(tempfile.gettempdir(), "karaoke_tone_cache")
    os.makedirs(path, exist_ok=True)
    return path


def tone_cache_path(codigo, semitones):
    safe_codigo = re.sub(r"[^0-9A-Za-z_-]", "_", str(codigo).zfill(5))
    return os.path.join(tone_cache_dir(), f"{safe_codigo}_{semitones:+d}.mp4")


def prune_tone_cache():
    files = []
    total = 0
    for name in os.listdir(tone_cache_dir()):
        path = os.path.join(tone_cache_dir(), name)
        if not os.path.isfile(path) or not name.endswith(".mp4"):
            continue
        size = os.path.getsize(path)
        total += size
        files.append((os.path.getmtime(path), size, path))

    if total <= TONE_CACHE_MAX_BYTES:
        return

    for _, size, path in sorted(files):
        try:
            os.remove(path)
            total -= size
        except OSError:
            pass
        if total <= TONE_CACHE_MAX_BYTES:
            break


def serve_video_file(request, path):
    file_size = os.path.getsize(path)
    content_type, _ = mimetypes.guess_type(path)
    content_type = content_type or "video/mp4"

    range_header = request.headers.get("Range", "").strip()
    range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)

    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
        end = min(end, file_size - 1)

        if start >= file_size:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{file_size}"
            return response

        length = end - start + 1
        with open(path, "rb") as f:
            f.seek(start)
            data = f.read(length)

        response = HttpResponse(data, status=206, content_type=content_type)
        response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        response["Content-Length"] = str(length)
    else:
        response = StreamingHttpResponse(open(path, "rb"), content_type=content_type)
        response["Content-Length"] = str(file_size)

    response["Accept-Ranges"] = "bytes"
    response["Cache-Control"] = "private, max-age=3600"
    return response


def build_pitch_shift_file(source, output_path, semitones):
    if os.path.exists(output_path):
        return output_path

    factor = math.pow(2, semitones / 12)
    ffmpeg_bin = getattr(settings, "FFMPEG_BIN", "ffmpeg")
    part_path = f"{output_path}.part"

    command = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-reconnect",
        "1",
        "-reconnect_streamed",
        "1",
        "-reconnect_delay_max",
        "5",
        "-i",
        source,
        "-fflags",
        "+genpts",
        "-map",
        "0:v:0",
        "-map",
        "0:a:0",
        "-c:v",
        "copy",
        "-af",
        f"rubberband=pitch={factor:.8f},asetpts=N/SR/TB",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-f",
        "mp4",
        "-y",
        part_path,
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg indisponivel no servidor") from exc
    except subprocess.CalledProcessError as exc:
        error = (exc.stderr or exc.stdout or "").strip().splitlines()
        detail = error[-1] if error else "Falha ao processar tom"
        raise RuntimeError(detail[:180]) from exc

    os.replace(part_path, output_path)
    prune_tone_cache()
    return output_path


def start_tone_job(job_key, source, output_path, semitones):
    def run():
        try:
            build_pitch_shift_file(source, output_path, semitones)
            status = {"status": "ready"}
        except RuntimeError as exc:
            status = {"status": "error", "error": str(exc)}

        with TONE_JOBS_LOCK:
            TONE_JOBS[job_key] = status

    with TONE_JOBS_LOCK:
        current = TONE_JOBS.get(job_key)
        if current and current.get("status") == "pending":
            return
        TONE_JOBS[job_key] = {"status": "pending"}

    thread = threading.Thread(target=run, daemon=True)
    thread.start()


# -----------------------------
# pagina de acesso - home
# -----------------------------


from django.shortcuts import render
from .models import Musica

def home(request):
    top3 = Musica.objects.order_by("-acessos", "-id")[:3]
    site_config = SiteConfiguration.get_solo()
    video_base_url = getattr(settings, "VIDEO_BASE_URL", "").rstrip("/")
    hero_background_url = (
        f"{video_base_url}/thumbs/karaoke-background.jpg"
        if video_base_url
        else f"{settings.STATIC_URL}media/karaoke/karaoke-background.jpg"
    )

    for m in top3:
        codigo = str(getattr(m, "codigo", "")).zfill(5)

        # token (mantido caso você use em outros pontos)
        m.token = signing.dumps(codigo, salt="video-stream")

        if video_base_url:
            m.thumb_url = f"{video_base_url}/thumbs/{quote(codigo)}.jpg"
        else:
            m.thumb_url = f"{settings.STATIC_URL}media/karaoke/{codigo}.jpg"



    return render(
        request,
        "musicas/home.html",
        {
            "top3": top3,
            "site_config": site_config,
            "hero_background_url": hero_background_url,
            "hide_nav": True,        # Home sem menu
            "hide_container": True,  # Home sem container do base
        },
    )
# -----------------------------
# LISTA DE MÚSICAS
# -----------------------------
@login_required
def lista_musicas(request):
    AuditEvent.log_from_request(
        request,
        AuditEvent.LIST_VIEW,
        metadata={
            "codigo": request.GET.get("codigo") or "",
            "artista": request.GET.get("artista") or "",
            "nome": request.GET.get("nome") or "",
            "page": request.GET.get("page") or "1",
        },
    )

    codigo = request.GET.get("codigo")
    artista = request.GET.get("artista")
    nome = request.GET.get("nome")

    try:
        pagina = max(int(request.GET.get("page", 1)), 1)
    except ValueError:
        pagina = 1

    if codigo:
        detalhe_url = reverse("detalhe_musica", kwargs={"codigo": str(codigo).zfill(5)})
        next_url = quote(request.get_full_path(), safe="")
        return redirect(f"{detalhe_url}?next={next_url}")

    contexto = {
        "musicas": [],
        "total": 0,
        "pagina": pagina,
        "tem_proxima": False,
        "tem_anterior": False,
        "artista": artista or "",
        "nome": nome or "",
    }

    try:
        resultado = buscar_musicas(pagina=pagina, artista=artista, nome=nome)
        contexto.update({
            "musicas": resultado.get("lista", []),
            "total": resultado.get("total", 0),
            "tem_proxima": bool(resultado.get("next")),
            "tem_anterior": bool(resultado.get("previous")),
        })
    except Exception as e:
        print(f"[ERRO] Falha ao buscar músicas: {e}")
        contexto["erro"] = "Erro ao carregar músicas"

    contexto.update(user_usage_context(request.user))
    contexto.update(paid_access_context(request.user))
    return render(request, "musicas/lista.html", contexto)


# -----------------------------
# DETALHE DA MÚSICA
# -----------------------------
@ensure_csrf_cookie
@login_required
def detalhe_musica(request, codigo):
    codigo = str(codigo).zfill(5)
    access_response = ensure_music_access(request, codigo)
    if access_response:
        return access_response

    musica = buscar_musica_por_codigo(codigo)

    if not musica:
        return render(
            request,
            "musicas/details.html",
            {"erro": "Música não encontrada"},
            status=404
        )

    token = signing.dumps(codigo, salt="video-stream")
    AuditEvent.log_from_request(
        request,
        AuditEvent.MUSIC_DETAIL,
        codigo=codigo,
        nome=musica.get("nome") or "",
        artista=musica.get("artista") or "",
    )

    next_url = safe_next_url(request, reverse("lista_musicas"))

    context = {
        "musica": musica,
        "token": token,
        "next_url": next_url,
    }
    context.update(user_usage_context(request.user))
    context.update(paid_access_context(request.user))

    return render(
        request,
        "musicas/details.html",
        context,
    )


# -----------------------------
# MODO PALCO (NOVA VIEW HTML)
# -----------------------------
@login_required
def modo_palco(request, codigo):
    codigo = str(codigo).zfill(5)
    access_response = ensure_music_access(request, codigo)
    if access_response:
        return access_response

    musica = buscar_musica_por_codigo(codigo)

    if not musica:
        raise Http404("Música não encontrada")

    # (opcional) estatística: só faz depois que musica existe
    AuditEvent.log_from_request(
        request,
        AuditEvent.MUSIC_DETAIL,
        codigo=codigo,
        nome=musica.get("nome") or "",
        artista=musica.get("artista") or "",
        metadata={"mode": "palco"},
    )

    estat, created = MusicaEstatistica.objects.get_or_create(
        codigo=musica["codigo"],
        defaults={
            "nome": musica.get("nome", ""),
            "artista": musica.get("artista", ""),
        }
    )
    estat.acessos += 1
    estat.save()

    token = signing.dumps(codigo, salt="video-stream")

    fallback_url = reverse("detalhe_musica", kwargs={"codigo": codigo})
    next_url = safe_next_url(request, fallback_url)

    context = {
        "musica": musica,
        "token": token,
        "voltar_url": next_url,
        "hide_nav": True,
        "hide_container": True,
    }
    context.update(user_usage_context(request.user))

    return render(
        request,
        "musicas/Palco.html",
        context,
    )

# -----------------------------
# STREAM DE VÍDEO (SEM CONTAR PLAY)
# -----------------------------
@login_required
def stream_video(request, codigo):
    access_response = ensure_music_access(request, codigo, json_response=True)
    if access_response:
        return access_response

    token = request.GET.get("token")
    if not token:
        return JsonResponse({"error": "Token não fornecido"}, status=403)

    try:
        token_codigo = signing.loads(token, salt="video-stream", max_age=TOKEN_TTL)
    except signing.SignatureExpired:
        return JsonResponse({"error": "Token expirado"}, status=403)
    except signing.BadSignature:
        return JsonResponse({"error": "Token inválido"}, status=403)

    codigo_norm = str(codigo).zfill(5)
    if codigo_norm != token_codigo:
        return JsonResponse({"error": "Token não corresponde"}, status=403)

    musica_dict = buscar_musica_por_codigo(codigo_norm)
    if not musica_dict:
        raise Http404("Música não encontrada")

    video_base_url = getattr(settings, "VIDEO_BASE_URL", "").rstrip("/")
    if video_base_url:
        caminho_video = str(musica_dict["caminho_video"]).replace("\\", "/").lstrip("/")
        video_url = f"{video_base_url}/{quote(caminho_video, safe='/')}"
        return HttpResponseRedirect(video_url)

    path = os.path.join(settings.MEDIA_ROOT, musica_dict["caminho_video"])
    if not os.path.exists(path):
        raise Http404("Vídeo não encontrado")

    file_size = os.path.getsize(path)
    content_type, _ = mimetypes.guess_type(path)
    content_type = content_type or "video/mp4"

    range_header = request.headers.get("Range", "").strip()
    range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)

    if range_match:
        start = int(range_match.group(1))
        end = int(range_match.group(2)) if range_match.group(2) else file_size - 1
        end = min(end, file_size - 1)

        if start >= file_size:
            # Range inválido
            resp = HttpResponse(status=416)
            resp["Content-Range"] = f"bytes */{file_size}"
            return resp

        length = end - start + 1

        with open(path, "rb") as f:
            f.seek(start)
            data = f.read(length)

        response = HttpResponse(data, status=206, content_type=content_type)
        response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        response["Accept-Ranges"] = "bytes"
        response["Content-Length"] = str(length)
    else:
        response = StreamingHttpResponse(open(path, "rb"), content_type=content_type)
        response["Content-Length"] = str(file_size)
        response["Accept-Ranges"] = "bytes"

    return response


@login_required
def stream_video_tom(request, codigo, tom):
    access_response = ensure_music_access(request, codigo, json_response=True)
    if access_response:
        return access_response

    token_error = validate_stream_token(request, codigo)
    if token_error:
        return token_error

    semitones = parse_tom(tom)
    if semitones is None:
        return JsonResponse({"error": "Tom invalido"}, status=400)

    if semitones == 0:
        return stream_video(request, codigo)

    codigo_norm = str(codigo).zfill(5)
    musica_dict = buscar_musica_por_codigo(codigo_norm)
    if not musica_dict:
        raise Http404("Musica nao encontrada")

    source = video_source_from_musica(musica_dict)
    if not source.startswith(("http://", "https://")) and not os.path.exists(source):
        raise Http404("Video nao encontrado")

    output_path = tone_cache_path(codigo_norm, semitones)
    try:
        build_pitch_shift_file(source, output_path, semitones)
    except RuntimeError as exc:
        return JsonResponse({"error": str(exc)}, status=503)

    return serve_video_file(request, output_path)


@login_required
def prepare_video_tom(request, codigo, tom):
    access_response = ensure_music_access(request, codigo, json_response=True)
    if access_response:
        return access_response

    semitones = parse_tom(tom)
    if semitones is None:
        return JsonResponse({"error": "Tom invalido"}, status=400)

    codigo_norm = str(codigo).zfill(5)
    fresh_token = signing.dumps(codigo_norm, salt="video-stream")
    if semitones == 0:
        return JsonResponse({
            "ok": True,
            "url": f"{reverse('stream_video', kwargs={'codigo': codigo_norm})}?token={fresh_token}",
        })

    musica_dict = buscar_musica_por_codigo(codigo_norm)
    if not musica_dict:
        raise Http404("Musica nao encontrada")

    source = video_source_from_musica(musica_dict)
    if not source.startswith(("http://", "https://")) and not os.path.exists(source):
        raise Http404("Video nao encontrado")

    output_path = tone_cache_path(codigo_norm, semitones)
    job_key = f"{codigo_norm}:{semitones}"
    if os.path.exists(output_path):
        return JsonResponse({
            "ok": True,
            "status": "ready",
            "url": f"{reverse('stream_video_tom', kwargs={'codigo': codigo_norm, 'tom': semitones})}?token={fresh_token}",
        })

    with TONE_JOBS_LOCK:
        job = TONE_JOBS.get(job_key)

    if job and job.get("status") == "error":
        with TONE_JOBS_LOCK:
            TONE_JOBS.pop(job_key, None)
        return JsonResponse({"ok": False, "status": "error", "error": job.get("error", "Falha ao preparar tom")}, status=503)

    if job and job.get("status") == "ready":
        return JsonResponse({
            "ok": True,
            "status": "ready",
            "url": f"{reverse('stream_video_tom', kwargs={'codigo': codigo_norm, 'tom': semitones})}?token={fresh_token}",
        })

    start_tone_job(job_key, source, output_path, semitones)

    return JsonResponse({
        "ok": True,
        "status": "pending",
    })


@csrf_exempt
@require_POST
@login_required
def registrar_play(request, codigo):
    raw = str(codigo)
    codigo_norm = raw.zfill(5)
    access_response = ensure_music_access(request, codigo_norm, json_response=True)
    if access_response:
        return access_response

    session_key = f"played_{codigo_norm}"
    WINDOW_SECONDS = 600  # 10 min
    now_ts = int(dj_timezone.now().timestamp())

    last_ts = request.session.get(session_key)
    if last_ts is not None:
        try:
            if (now_ts - int(last_ts)) <= WINDOW_SECONDS:
                return JsonResponse({"ok": True, "counted": False, "reason": "window"})
        except Exception:
            pass

    # pega metadados da fonte (se existir)
    musica_dict = buscar_musica_por_codigo(codigo_norm) or {}
    nome = musica_dict.get("nome") or ""
    artista = musica_dict.get("artista") or ""
    user_play_result = mark_user_play(request, codigo_norm, musica_dict)
    AuditEvent.log_from_request(
        request,
        AuditEvent.MUSIC_PLAY,
        codigo=codigo_norm,
        nome=nome,
        artista=artista,
        metadata={"counted": True},
    )

    # tenta achar registro existente (aceita codigo "1001" e "01001")
    obj = Musica.objects.filter(codigo__in=[raw, codigo_norm]).first()

    if obj is None:
        # cria já com metadados
        obj = Musica.objects.create(
            codigo=codigo_norm,
            nome=nome,
            artista=artista,
            acessos=0,
        )
    else:
        # se existir mas estiver vazio, preenche
        updates = {}
        if (not getattr(obj, "nome", "")) and nome:
            updates["nome"] = nome
        if (not getattr(obj, "artista", "")) and artista:
            updates["artista"] = artista
        if updates:
            for k, v in updates.items():
                setattr(obj, k, v)
            obj.save(update_fields=list(updates.keys()))

    # incrementa
    Musica.objects.filter(pk=obj.pk).update(acessos=F("acessos") + 1)

    request.session[session_key] = now_ts
    payload = {"ok": True, "counted": True}
    if user_play_result:
        payload.update(user_usage_context(request.user))

    return JsonResponse(payload)


@csrf_exempt
@require_POST
@login_required
def registrar_visualizacao(request, codigo):
    codigo_norm = str(codigo).zfill(5)
    access_response = ensure_music_access(request, codigo_norm, json_response=True)
    if access_response:
        return access_response

    duration = request.POST.get("duration_seconds") or request.POST.get("duration") or 0
    current_tone = request.POST.get("tone") or "0"
    try:
        musica_dict = buscar_musica_por_codigo(codigo_norm) or {}
    except Exception:
        local_musica = Musica.objects.filter(codigo=codigo_norm).first()
        musica_dict = {
            "nome": getattr(local_musica, "nome", "") or "",
            "artista": getattr(local_musica, "artista", "") or "",
        }

    event = AuditEvent.log_from_request(
        request,
        AuditEvent.VIDEO_WATCH,
        codigo=codigo_norm,
        nome=musica_dict.get("nome") or "",
        artista=musica_dict.get("artista") or "",
        duration_seconds=duration,
        metadata={"tone": current_tone},
    )
    return JsonResponse({"ok": True, "duration_seconds": event.duration_seconds})
