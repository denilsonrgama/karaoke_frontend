# karaoke_frontend/musicas/views.py
from django.utils import timezone as dj_timezone
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

from accounts.models import MusicaEstatistica
from musicas.models import Musica
from .models import Musica
from django.views.decorators.csrf import ensure_csrf_cookie
from .services import buscar_musica_por_codigo, buscar_musicas
import mimetypes
import os
import re
from urllib.parse import quote
from django.db.models import F


# Token válido por 5 minutos
TOKEN_TTL = 300  # segundos


def safe_next_url(request, fallback_url):
    next_url = request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback_url


# -----------------------------
# pagina de acesso - home
# -----------------------------


from django.shortcuts import render
from .models import Musica

def home(request):
    top3 = Musica.objects.order_by("-acessos", "-id")[:3]
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

    return render(request, "musicas/lista.html", contexto)


# -----------------------------
# DETALHE DA MÚSICA
# -----------------------------
@ensure_csrf_cookie
@login_required
def detalhe_musica(request, codigo):
    codigo = str(codigo).zfill(5)
    musica = buscar_musica_por_codigo(codigo)

    if not musica:
        return render(
            request,
            "musicas/details.html",
            {"erro": "Música não encontrada"},
            status=404
        )

    token = signing.dumps(codigo, salt="video-stream")

    next_url = safe_next_url(request, reverse("lista_musicas"))

    return render(
        request,
        "musicas/details.html",
        {
            "musica": musica,
            "token": token,
            "next_url": next_url,
        }
    )


# -----------------------------
# MODO PALCO (NOVA VIEW HTML)
# -----------------------------
@login_required
def modo_palco(request, codigo):
    codigo = str(codigo).zfill(5)
    musica = buscar_musica_por_codigo(codigo)

    if not musica:
        raise Http404("Música não encontrada")

    # (opcional) estatística: só faz depois que musica existe
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

    return render(
        request,
        "musicas/palco.html",
        {
            "musica": musica,
            "token": token,
            "voltar_url": next_url,
            "hide_nav": True,        # ✅ Palco sem menu
            "hide_container": True,  # ✅ Palco fullscreen real
        }
    )

# -----------------------------
# STREAM DE VÍDEO (SEM CONTAR PLAY)
# -----------------------------
def stream_video(request, codigo):
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


@csrf_exempt
@require_POST
@login_required
def registrar_play(request, codigo):
    raw = str(codigo)
    codigo_norm = raw.zfill(5)

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
    return JsonResponse({"ok": True, "counted": True})
