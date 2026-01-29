# karaoke_frontend/musicas/views.py

from django.conf import settings
from django.http import (
    JsonResponse,
    StreamingHttpResponse,
    Http404,
    HttpResponse,
)
from django.core import signing
from django.shortcuts import render, redirect

from .services import buscar_musica_por_codigo, buscar_musicas

import mimetypes
import os
import re

# Token válido por 5 minutos
TOKEN_TTL = 300  # segundos


# -----------------------------
# LISTA DE MÚSICAS
# -----------------------------
def lista_musicas(request):
    codigo = request.GET.get("codigo")
    artista = request.GET.get("artista")
    nome = request.GET.get("nome")

    try:
        pagina = max(int(request.GET.get("page", 1)), 1)
    except ValueError:
        pagina = 1

    if codigo:
        return redirect("detalhe_musica", codigo=str(codigo).zfill(5))

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

    next_url = request.GET.get("next")

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
def modo_palco(request, codigo):
    codigo = str(codigo).zfill(5)
    musica = buscar_musica_por_codigo(codigo)

    if not musica:
        raise Http404("Música não encontrada")

    token = signing.dumps(codigo, salt="video-stream")

    next_url = request.GET.get("next")

    return render(
        request,
        "musicas/palco.html",
        {
            "musica": musica,
            "token": token,
            "voltar_url": next_url,
        }
    )


# -----------------------------
# STREAM DE VÍDEO (NÃO MEXER)
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

    if str(codigo).zfill(5) != token_codigo:
        return JsonResponse({"error": "Token não corresponde"}, status=403)

    musica = buscar_musica_por_codigo(str(codigo).zfill(5))
    if not musica:
        raise Http404("Música não encontrada")

    path = os.path.join(settings.MEDIA_ROOT, musica["caminho_video"])
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

        length = end - start + 1

        with open(path, "rb") as f:
            f.seek(start)
            data = f.read(length)

        response = HttpResponse(data, status=206, content_type=content_type)
        response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        response["Accept-Ranges"] = "bytes"
        response["Content-Length"] = str(length)
    else:
        response = StreamingHttpResponse(
            open(path, "rb"),
            content_type=content_type
        )
        response["Content-Length"] = str(file_size)
        response["Accept-Ranges"] = "bytes"

    return response
