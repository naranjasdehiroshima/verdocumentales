#!/usr/bin/env python3
"""
NdH Catalog Builder — desde Blogger API directamente, sin Excel.
Genera catalog.json completo con paginación para traer todos los posts.
"""
import json, time, re, requests, os
from datetime import datetime

API_KEY = os.environ.get("BLOGGER_API_KEY", "AIzaSyBNi9OQO8rmQ6Ytqkn_B-hN4eVYXDtsbQg")
BLOG_ID = "2607698793900837848"
OUTPUT  = "catalog.json"

def find_all_embeds(html):
    h = html or ""
    return {
        "youtube":     re.findall(r'youtube\.com/(?:embed/|watch\?v=|v/)([A-Za-z0-9_-]{11})', h),
        "vimeo":       re.findall(r'vimeo\.com/(?:video/)?(\d{5,12})(?:[^0-9]|$)', h),
        "okru":        re.findall(r'ok\.ru/video(?:embed)?/(\d+)', h),
        "dailymotion": re.findall(r'dailymotion\.com/embed/video/([A-Za-z0-9]+)', h),
    }

def pick_best_embed(embeds):
    # Prioridad: ok.ru > Vimeo > Dailymotion > YouTube (último suele ser trailer)
    if embeds["okru"]:        return "okru",        embeds["okru"][-1]
    if embeds["vimeo"]:       return "vimeo",       embeds["vimeo"][-1]
    if embeds["dailymotion"]: return "dailymotion", embeds["dailymotion"][-1]
    if embeds["youtube"]:     return "youtube",     embeds["youtube"][-1]
    return None, None

def extract_first_image(html):
    imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html or "")
    for img in imgs:
        if 'googleusercontent.com' in img or 'bp.blogspot.com' in img:
            return img
    return None

def extract_tags(post):
    return post.get("labels", [])

def fetch_all_posts(session):
    """Pagina por la Blogger API hasta traer todos los posts."""
    posts = []
    url = f"https://www.googleapis.com/blogger/v3/blogs/{BLOG_ID}/posts"
    params = {
        "key": API_KEY,
        "maxResults": 500,
        "fields": "items(id,title,url,published,labels,content),nextPageToken",
        "fetchBodies": "true",
        "status": "live",
    }
    page = 1
    while True:
        print(f"  Página {page}...", flush=True)
        r = session.get(url, params=params, timeout=30)
        data = r.json()
        items = data.get("items", [])
        posts.extend(items)
        print(f"  Posts acumulados: {len(posts)}", flush=True)
        token = data.get("nextPageToken")
        if not token:
            break
        params["pageToken"] = token
        page += 1
        time.sleep(0.3)
    return posts

def main():
    print("Conectando con Blogger API...", flush=True)
    session = requests.Session()
    session.headers["User-Agent"] = "NdH-Catalog-Builder/2.0"

    posts = fetch_all_posts(session)
    print(f"Total posts obtenidos: {len(posts)}", flush=True)

    catalog = []
    for i, post in enumerate(posts, 1):
        content = post.get("content", "")
        tags    = extract_tags(post)
        embeds  = find_all_embeds(content)
        embed_type, embed_id = pick_best_embed(embeds)
        img     = extract_first_image(content)
        yt_ids  = embeds["youtube"]
        yt_thumb = yt_ids[0] if yt_ids else None

        entry = {
            "id":           i,
            "titulo":       post.get("title", "").strip(),
            "url_ndh":      post.get("url", ""),
            "fecha_pub":    post.get("published", "")[:10],
            "tags":         tags,
            "caratula_ndh": any(t in tags for t in ["Carteles Naranjas","Caratulas Naranjas","Documentales Naranjas"]),
            "embed_type":   embed_type,
            "embed_id":     embed_id,
            "youtube_id":   yt_thumb,
            "reproducible": embed_id is not None,
            "imagen":       img or (f"https://img.youtube.com/vi/{yt_thumb}/maxresdefault.jpg" if yt_thumb else None),
            # Campos que antes venían del Excel — quedan vacíos, editables a mano
            "titulo_original": "",
            "direccion":       "",
            "pais":            "",
            "anio":            "",
            "duracion":        "",
            "sinopsis":        "",
            "autor":           "",
        }
        catalog.append(entry)

        if i % 100 == 0:
            r_ = sum(1 for e in catalog if e["reproducible"])
            print(f"  [{i}/{len(posts)}] reproducibles={r_}", flush=True)

    total = len(catalog)
    by_type = {}
    for e in catalog:
        if e["embed_type"]: by_type[e["embed_type"]] = by_type.get(e["embed_type"],0)+1

    meta = {
        "total": total,
        "reproducibles": sum(1 for e in catalog if e["reproducible"]),
        "con_imagen": sum(1 for e in catalog if e["imagen"]),
        "por_tipo": by_type,
        "caratulas_ndh": sum(1 for e in catalog if e["caratula_ndh"]),
        "generado": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "fuente": "Blogger API v3",
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "docs": catalog}, f, ensure_ascii=False, indent=2)

    print(f"\n✓ {OUTPUT}")
    print(f"  Total={meta['total']} | Reproducibles={meta['reproducibles']} | Imágenes={meta['con_imagen']}")
    print(f"  Por tipo: {by_type}")

main()
