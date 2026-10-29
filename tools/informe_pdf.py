"""Genera el informe PDF del Termómetro y el contexto histórico de una contienda.

Uso:
  python3 tools/informe_pdf.py SALIDA.pdf "28 de octubre de 2026"

Lee termometro.json e historico.json de la raíz del repositorio.
"""
import html
import json
import os
import re
import sys
import unicodedata

from playwright.sync_api import sync_playwright

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = json.load(open(os.path.join(RAIZ, "termometro.json"), encoding="utf-8"))
H = json.load(open(os.path.join(RAIZ, "historico.json"), encoding="utf-8"))

TCOMP = [("conv", "Conversación", 35, "#2c8466"), ("tasa", "Tasa de interacción", 20, "#2e5d8c"),
         ("const", "Constancia", 15, "#b0732a"), ("video", "Alcance en video", 15, "#8f4ba6"),
         ("aud", "Audiencia", 15, "#4a7d9a")]
COLS = ["#2e5d8c", "#c0462f", "#2c8466", "#b0732a", "#8f4ba6", "#4a7d9a", "#7d7a2a", "#a3456b", "#3f6f5a"]
HNOM = {"A": "Alcaldía", "C": "Concejo", "G": "Gobernación", "S": "Asamblea"}
DNAME = {"VALLE": "Valle del Cauca", "RISARALDA": "Risaralda", "QUINDIO": "Quindío", "CHOCO": "Chocó"}
SMALL = {"de", "del", "la", "las", "el", "los", "y", "por", "para", "en", "con", "a", "al", "e"}
KEEP = {"mira", "asi", "aico", "mais", "ada", "pre", "cd", "cr", "u", "up"}

e = html.escape


def nrm(s):
    s = unicodedata.normalize("NFD", str(s))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").upper()


def tc(s):
    out = []
    for i, w in enumerate(str(s).lower().split(" ")):
        core = re.sub(r"[^a-záéíóúñü]", "", w)
        if core in KEEP:
            out.append(w.upper())
        elif i > 0 and w in SMALL:
            out.append(w)
        else:
            out.append(re.sub(r"[a-záéíóúñü]", lambda m: m.group(0).upper(), w, count=1))
    return " ".join(out)


def num(v, d=0):
    if v is None:
        return "—"
    s = f"{v:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v, d=1):
    return "—" if v is None else num(v * 100, d) + " %"


def g(d, k):
    return (d or {}).get(k) or 0


def metr(m):
    fb, ig, tt = m.get("fb"), m.get("ig"), m.get("tt")
    tasas = [g(x, "inter") / g(x, "pubs") / g(x, "seg") for x in (fb, ig) if x and g(x, "pubs") > 0 and g(x, "seg") > 0]
    return {"aud": g(fb, "seg") + g(ig, "seg") + g(tt, "seg"), "inter": g(fb, "inter") + g(ig, "inter"),
            "pubs": g(fb, "pubs") + g(ig, "pubs") + g(tt, "videos"), "vistas": g(tt, "vistas"),
            "tasa": sum(tasas) / len(tasas) if tasas else 0, "redes": sum(1 for x in (fb, ig, tt) if x)}


def indice(meds):
    R = [(m["cand"], metr(m)) for m in meds]
    key = {"conv": "inter", "tasa": "tasa", "const": "pubs", "video": "vistas", "aud": "aud"}
    mx = {k: max([x[v] for _, x in R] + [0]) for k, v in key.items()}
    tot = sum(x["inter"] for _, x in R) or 1
    out = []
    for c, x in R:
        contrib = {k: (x[key[k]] / mx[k] if mx[k] else 0) * w for k, _, w, _ in TCOMP}
        out.append({"id": c, "x": x, "contrib": contrib, "total": sum(contrib.values()), "share": x["inter"] / tot})
    return sorted(out, key=lambda r: -r["total"])


# ---------- historia electoral ----------
pl = {int(k): v for k, v in H["pl"].items()}
NAMEIDX = {}
for key, o in H["c"].items():
    y, code, terr = key.split("|")
    el = set()
    if o.get("rep"):
        for L in o["rep"]["lists"]:
            el.update(L[3])
    val = sum(r[2] for r in o["k"]) + o["s"][0]
    rank = 0
    for p, n, v in o["k"]:
        if pl.get(p) == n:
            continue
        rank += 1
        win = rank == 1 if code in "AG" else n in el
        NAMEIDX.setdefault(n, []).append(dict(y=y, code=code, terr=terr, p=p, v=v, win=win,
                                               pct=v / val if code in "AG" and val else None, rank=rank))
NIDX = {nrm(s): i for i, s in enumerate(H["names"])}


def terr(code, t):
    return H["munis"][int(t)][1] if code in "AC" else DNAME[t]


def historia(nombre):
    n = NIDX.get(nrm(nombre)) if nombre else None
    if n is None or n not in NAMEIDX:
        return []
    return sorted(NAMEIDX[n], key=lambda x: (x["y"], "GASC".index(x["code"])))


def fam(p):
    return H["fams"][H["pfam"][p]]


def pname(p):
    return re.sub(r"^Coalicion o Grupo Significativo \d+$", "Coalición o grupo significativo", tc(H["parties"][p]), flags=re.I)


# ---------- gráficos SVG ----------
def svg_ranking(idx, seg):
    W, rowh, L = 660, 34, 190
    hgt = rowh * len(idx) + 10
    s = [f'<svg viewBox="0 0 {W} {hgt}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    for i, r in enumerate(idx):
        y = 6 + i * rowh
        s.append(f'<text x="0" y="{y+16}" font-size="12" fill="#1c2332">{e(seg[r["id"]]["nombre"])}</text>')
        x = L
        for k, n, w, c in TCOMP:
            ww = r["contrib"][k] / 100 * (W - L - 60)
            if ww > 0:
                s.append(f'<rect x="{x:.1f}" y="{y+4}" width="{ww:.1f}" height="16" fill="{c}"/>')
            x += ww
        s.append(f'<text x="{x+6:.1f}" y="{y+16}" font-size="12" font-weight="700" fill="#1c2332">{num(r["total"],1)}</text>')
    s.append("</svg>")
    return "".join(s)


def svg_share(idx, seg, colof):
    W, rowh, L = 660, 24, 190
    hgt = rowh * len(idx) + 6
    mx = max(r["share"] for r in idx) or 1
    s = [f'<svg viewBox="0 0 {W} {hgt}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    for i, r in enumerate(idx):
        y = 4 + i * rowh
        ww = r["share"] / mx * (W - L - 70)
        s.append(f'<text x="0" y="{y+13}" font-size="11.5" fill="#1c2332">{e(seg[r["id"]]["nombre"])}</text>'
                 f'<rect x="{L}" y="{y+2}" width="{max(ww,1):.1f}" height="13" fill="{colof[r["id"]]}"/>'
                 f'<text x="{L+ww+6:.1f}" y="{y+13}" font-size="11.5" fill="#1c2332">{pct(r["share"],0)}</text>')
    s.append("</svg>")
    return "".join(s)


def svg_evol(fechas, series):
    W, Ht, L, R, Tp, B = 660, 230, 40, 170, 12, 28
    X = (lambda i: L + (W - L - R) / 2) if len(fechas) < 2 else (lambda i: L + i * (W - L - R) / (len(fechas) - 1))
    Y = lambda v: Tp + (1 - v / 100) * (Ht - Tp - B)
    s = [f'<svg viewBox="0 0 {W} {Ht}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    for v in range(0, 101, 20):
        s.append(f'<line x1="{L}" x2="{W-R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#dfe5db"/><text x="{L-6}" y="{Y(v)+3:.1f}" font-size="10" text-anchor="end" fill="#5b6474">{v}</text>')
    for i, f in enumerate(fechas):
        s.append(f'<text x="{X(i):.1f}" y="{Ht-8}" font-size="10" text-anchor="middle" fill="#5b6474">{f}</text>')
    ends = []
    for nm, c, vals in series:
        pts = [(X(i), Y(v)) for i, v in enumerate(vals) if v is not None]
        if len(pts) > 1:
            s.append('<path d="' + " ".join(("M" if j == 0 else "L") + f"{x:.1f} {y:.1f}" for j, (x, y) in enumerate(pts)) + f'" fill="none" stroke="{c}" stroke-width="2.2"/>')
        for x, y in pts:
            s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{c}"/>')
        if pts:
            ends.append([pts[-1][1], pts[-1][0], f"{nm} · {num([v for v in vals if v is not None][-1])}", c])
    ends.sort()
    for i in range(1, len(ends)):
        if ends[i][0] - ends[i - 1][0] < 12:
            ends[i][0] = ends[i - 1][0] + 12
    for y, x, t, c in ends:
        s.append(f'<text x="{x+8:.1f}" y="{y+3:.1f}" font-size="10.5" fill="#1c2332">{e(t)}</text>')
    s.append("</svg>")
    return "".join(s)


# ---------- armado del informe ----------
def construir(fecha_txt):
    seg = {s["id"]: s for s in T["seguimiento"]}
    meds = T["mediciones"]
    fechas = sorted({m["fecha"] for m in meds})
    ult = fechas[-1]
    idx = indice([m for m in meds if m["fecha"] == ult])
    colof = {r["id"]: COLS[i % len(COLS)] for i, r in enumerate(idx)}
    m_ult = {m["cand"]: m for m in meds if m["fecha"] == ult}
    s0 = seg[idx[0]["id"]]
    contienda = f'{ {"alcaldia":"Alcaldía","concejo":"Concejo","gobernacion":"Gobernación","asamblea":"Asamblea"}[s0["cargo"]] } de {s0["municipio"] or s0["depto"]}'
    lectura = next((a for a in T.get("analisis", [])), None)
    series = []
    for r in idx:
        vals = []
        for f in fechas:
            ix = {z["id"]: z for z in indice([m for m in meds if m["fecha"] == f])}
            vals.append(ix[r["id"]]["total"] if r["id"] in ix else None)
        series.append((" ".join(seg[r["id"]]["nombre"].split(" ")[-2:]), colof[r["id"]], vals))
    RAW = {"conv": lambda x: f'{num(x["inter"])} interacciones', "tasa": lambda x: f'{pct(x["tasa"])} de tasa',
           "const": lambda x: f'{num(x["pubs"])} publicaciones', "video": lambda x: f'{num(x["vistas"])} vistas TikTok',
           "aud": lambda x: f'{num(x["aud"])} seguidores'}

    P = []
    # Portada
    P.append(f'''<section class="portada">
      <div class="marca">RADAR <span>ELECTORAL</span> 2027</div>
      <h1>Informe de seguimiento<br>{e(contienda)}</h1>
      <p class="sub">Termómetro digital de aspirantes y contexto electoral 2003–2023</p>
      <p class="fecha">Corte: {e(fecha_txt)} · Ventana de medición: 14 días</p>
      <div class="autor"><b>William Andrés Muriel</b><br>Gobierno | Territorio | Tecnología<br>
      Administrador de Empresas · Especialista en Finanzas Públicas<br>williamandresm@gmail.com · linkedin.com/in/willi-muriel</div>
      <p class="aviso">Documento de análisis basado en información pública. Mide presencia y conversación digital; no es una encuesta ni mide intención de voto (Ley 2494 de 2025).</p>
    </section>''')
    # Resumen
    P.append('<section><h2>1. Resumen ejecutivo</h2>')
    if lectura:
        P.append("".join(f"<p>{e(p)}</p>" for p in lectura["texto"].split("\n\n")))
    P.append('<table class="t"><thead><tr><th>#</th><th>Aspirante</th><th>Puntaje</th><th>Participación en la conversación</th><th>Audiencia</th><th>Redes medidas</th></tr></thead><tbody>')
    for i, r in enumerate(idx):
        P.append(f'<tr><td>{i+1}</td><td class="l"><span class="dot" style="background:{colof[r["id"]]}"></span>{e(seg[r["id"]]["nombre"])}</td><td><b>{num(r["total"],1)}</b></td><td>{pct(r["share"])}</td><td>{num(r["x"]["aud"])}</td><td>{r["x"]["redes"]} de 3</td></tr>')
    P.append("</tbody></table></section>")
    # Termómetro
    P.append('<section><h2>2. Termómetro digital</h2><h3>Puntaje por componente</h3>')
    P.append('<div class="leyenda">' + "".join(f'<span><i style="background:{c}"></i>{n} ({w})</span>' for k, n, w, c in TCOMP) + "</div>")
    P.append(svg_ranking(idx, seg))
    P.append('<h3>Evolución del puntaje</h3>' + svg_evol(fechas, series))
    if len(fechas) < 2:
        P.append('<p class="nota">Primera revisión. Desde la próxima medición semanal la gráfica mostrará quién sube y quién baja.</p>')
    P.append('<h3>Participación en la conversación (Facebook + Instagram)</h3>' + svg_share(idx, seg, colof))
    P.append('<h3>Cómo se obtiene cada puntaje</h3><p>El puntaje va de 0 a 100 y se reparte en cinco componentes. En cada uno, el aspirante con el mejor dato de la contienda recibe el puntaje completo del componente y los demás reciben una parte proporcional. Por ejemplo, en conversación (35 puntos) el que más interacciones generó recibe 35 y quien generó la tercera parte recibe cerca de 12.</p>')
    P.append('<table class="t"><thead><tr><th>Aspirante</th>' + "".join(f"<th>{n} ({w})</th>" for k, n, w, c in TCOMP) + '<th>Total</th></tr></thead><tbody>')
    for r in idx:
        P.append(f'<tr><td class="l">{e(seg[r["id"]]["nombre"])}</td>' + "".join(f'<td><b>{num(r["contrib"][k],1)}</b><br><small>{RAW[k](r["x"])}</small></td>' for k, n, w, c in TCOMP) + f'<td><b>{num(r["total"],1)}</b></td></tr>')
    P.append("</tbody></table>")
    P.append('<table class="t"><thead><tr><th>Componente</th><th class="l">Qué mide</th><th>Máx.</th></tr></thead><tbody>'
             '<tr><td class="l">Conversación</td><td class="l">Reacciones, comentarios y compartidos en Facebook e Instagram en la ventana</td><td>35</td></tr>'
             '<tr><td class="l">Tasa de interacción</td><td class="l">Interacciones por publicación ÷ seguidores (promedio de Facebook e Instagram)</td><td>20</td></tr>'
             '<tr><td class="l">Constancia</td><td class="l">Publicaciones en las tres redes en la ventana</td><td>15</td></tr>'
             '<tr><td class="l">Alcance en video</td><td class="l">Reproducciones en TikTok en la ventana</td><td>15</td></tr>'
             '<tr><td class="l">Audiencia</td><td class="l">Seguidores sumados en las tres redes</td><td>15</td></tr></tbody></table></section>')
    # Fichas
    P.append('<section><h2>3. Fichas por aspirante</h2>')
    for i, r in enumerate(idx):
        s, m = seg[r["id"]], m_ult[r["id"]]
        hist = historia(s.get("histNombre"))
        an = sorted(s.get("analisis", []), key=lambda a: a["fecha"])
        P.append(f'<div class="ficha"><div class="fh"><span class="pos">{i+1}</span><div><h3 style="margin:0">{e(s["nombre"])}</h3><span class="muted">{e(s.get("partido") or "")}{" · " + e(s["rol"]) if s.get("rol") else ""}</span></div><span class="pt">{num(r["total"],1)}<small> pts</small></span></div>')
        if an:
            P.append(f'<p class="analisis"><b>Análisis ({e(an[-1]["fecha"])}).</b> {e(an[-1]["texto"])}</p>')
        P.append('<table class="t mini"><thead><tr><th>Red</th><th>Seguidores</th><th>Publicaciones</th><th>Interacciones / vistas</th></tr></thead><tbody>')
        for k, n in (("fb", "Facebook"), ("ig", "Instagram"), ("tt", "TikTok")):
            d = m.get(k)
            if d:
                P.append(f'<tr><td class="l">{n}</td><td>{num(g(d,"seg"))}</td><td>{num(g(d,"pubs") or g(d,"videos"))}</td><td>{num(g(d,"inter") or g(d,"vistas"))}</td></tr>')
            else:
                P.append(f'<tr><td class="l">{n}</td><td colspan="3" class="muted">Sin cuenta encontrada</td></tr>')
        P.append("</tbody></table>")
        if hist:
            P.append('<p class="lbl">Trayectoria electoral 2003–2023</p><table class="t mini"><thead><tr><th>Año</th><th>Cargo</th><th>Territorio</th><th class="l">Partido</th><th>Votos</th><th>Resultado</th></tr></thead><tbody>')
            for h in hist:
                res = ("Ganó" if h["win"] else f'Puesto {h["rank"]}') if h["code"] in "AG" else ("Elegido" if h["win"] else "No elegido")
                P.append(f'<tr><td>{h["y"]}</td><td>{HNOM[h["code"]]}</td><td>{e(terr(h["code"],h["terr"]))}</td><td class="l">{e(pname(h["p"]))}</td><td>{num(h["v"])}</td><td>{res}</td></tr>')
            P.append("</tbody></table>")
        else:
            P.append('<p class="muted">Sin historial electoral entre 2003 y 2023.</p>')
        if s.get("apoyos"):
            P.append('<p class="lbl">Apoyos registrados</p><ul>' + "".join(f'<li>{e(a["nombre"])}{" — " + e(a["nota"]) if a.get("nota") else ""}</li>' for a in s["apoyos"]) + "</ul>")
        if s.get("senales"):
            P.append('<p class="lbl">Señales</p><ul>' + "".join(f"<li>{e(x)}</li>" for x in s["senales"]) + "</ul>")
        if m.get("notas"):
            P.append(f'<p class="nota">{e(m["notas"])}</p>')
        P.append("</div>")
    P.append("</section>")
    # Contexto histórico
    mi = next((i for i, x in enumerate(H["munis"]) if x[1] == s0["municipio"]), None)
    if mi is not None:
        P.append(f'<section><h2>4. Contexto electoral: {e(contienda)} 2003–2023</h2><table class="t"><thead><tr><th>Año</th><th class="l">Ganador</th><th class="l">Partido</th><th>%</th><th>Segundo</th><th>Ventaja</th></tr></thead><tbody>')
        for y in H["years"]:
            o = H["c"].get(f"{y}|A|{mi}")
            if not o:
                continue
            val = sum(r[2] for r in o["k"]) + o["s"][0]
            w, s2 = o["k"][0], o["k"][1] if len(o["k"]) > 1 else None
            P.append(f'<tr><td>{y}</td><td class="l">{e(tc(H["names"][w[1]]))}</td><td class="l">{e(pname(w[0]))}</td><td>{pct(w[2]/val)}</td><td>{e(tc(H["names"][s2[1]])) if s2 else "—"}</td><td>{num((w[2]-s2[2])/val*100,1) + " pts" if s2 else "—"}</td></tr>')
        P.append("</tbody></table>")
        o = H["c"].get(f"2023|C|{mi}")
        if o and o.get("rep"):
            P.append('<h3>Concejo 2023: listas que obtuvieron curul (estimado)</h3><table class="t"><thead><tr><th class="l">Lista</th><th>Votos</th><th>%</th><th>Curules</th></tr></thead><tbody>')
            for L in o["rep"]["lists"]:
                if L[2]:
                    P.append(f'<tr><td class="l">{e(pname(L[0]))}</td><td>{num(L[1])}</td><td>{pct(L[1]/o["rep"]["validos"])}</td><td>{L[2]}</td></tr>')
            P.append("</tbody></table>")
        P.append("</section>")
    # Método
    P.append('''<section><h2>5. Metodología y fuentes</h2>
      <p><b>Mediciones digitales.</b> Revisión manual asistida de los perfiles públicos de cada aspirante en Facebook, Instagram y TikTok, en una ventana de 14 días. Se cuentan solo publicaciones propias (sin colaboraciones de terceros). La pauta se verifica en la Biblioteca de Anuncios de Meta (anuncios políticos, Colombia). Las señales provienen de prensa regional y de las publicaciones públicas de los aspirantes.</p>
      <p><b>Datos electorales.</b> Registraduría Nacional del Estado Civil, Observatorio: resultados mesa a mesa de las elecciones territoriales de 2019 y 2023. CEDAE (Universidad de los Andes con Datasketch): resultados de 2003, 2007, 2011 y 2015, con curules oficiales y censo electoral. Las curules de 2019 y 2023 son una estimación (umbral del 50 % del cociente electoral y cifra repartidora).</p>
      <p><b>Limitaciones.</b> Una publicación viral puede inflar un periodo; por eso el valor está en la tendencia de varias semanas. Un aspirante sin cuenta en una red obtiene cero en ese componente. Nombres iguales en territorios distintos pueden corresponder a personas diferentes.</p>
      <p><b>Alcance legal.</b> Este documento es un análisis de presencia digital e información pública para uso interno. No es una encuesta ni un sondeo de intención de voto y no debe divulgarse como tal (Ley 2494 de 2025).</p></section>''')
    css = '''
    @page{size:A4;margin:16mm 15mm 18mm}
    body{font-family:Inter,"DejaVu Sans",sans-serif;color:#1c2332;font-size:10.5pt;line-height:1.45}
    h1,h2,h3,.marca{font-family:"DejaVu Sans Condensed","DejaVu Sans",sans-serif}
    h2{font-size:16pt;text-transform:uppercase;letter-spacing:.02em;border-bottom:2px solid #7a2e8e;padding-bottom:4px;margin:0 0 10px}
    h3{font-size:12pt;margin:14px 0 6px}
    section{page-break-before:always}
    .portada{page-break-before:avoid;height:250mm;display:flex;flex-direction:column;justify-content:center;gap:10px}
    .marca{font-weight:700;font-size:15pt;letter-spacing:.05em}.marca span{color:#7a2e8e}
    .portada h1{font-size:30pt;line-height:1.1;margin:10px 0}
    .sub{font-size:13pt;color:#5b6474;margin:0}.fecha{margin:0}
    .autor{margin-top:40px;border-left:4px solid #7a2e8e;padding-left:12px}
    .aviso{margin-top:auto;font-size:9pt;color:#5b6474}
    table.t{width:100%;border-collapse:collapse;margin:8px 0 12px;font-size:9pt;page-break-inside:auto}
    table.t th{background:#eef1ea;font-size:8pt;text-transform:uppercase;letter-spacing:.04em;color:#5b6474;text-align:right;padding:5px 6px}
    table.t td{border-bottom:1px solid #dfe5db;padding:5px 6px;text-align:right;font-variant-numeric:tabular-nums;vertical-align:top}
    table.t tr{page-break-inside:avoid}
    table.t .l,table.t th.l{text-align:left}table.t td:first-child,table.t th:first-child{text-align:left}
    table.mini{font-size:8.5pt}
    small{color:#5b6474;font-size:7.5pt}
    .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
    .leyenda{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:8.5pt;color:#5b6474;margin-bottom:6px}.leyenda i{display:inline-block;width:9px;height:9px;margin-right:4px}
    .ficha{border:1px solid #cdd5c9;border-radius:6px;padding:10px 12px;margin:0 0 12px;page-break-inside:avoid}
    .fh{display:flex;align-items:center;gap:12px}.pos{font-size:20pt;font-weight:700;color:#7a2e8e;width:24px}
    .pt{margin-left:auto;font-size:18pt;font-weight:700}.pt small{font-size:9pt}
    .analisis{background:#f1e4f4;padding:8px 10px;border-radius:4px;margin:8px 0}
    .lbl{font-size:8pt;text-transform:uppercase;letter-spacing:.06em;color:#5b6474;margin:8px 0 2px;font-weight:700}
    ul{margin:2px 0 6px;padding-left:16px}.muted{color:#5b6474}.nota{font-size:9pt;color:#5b6474}
    '''
    return f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Radar Electoral — {e(contienda)}</title><style>{css}</style></head><body>{"".join(P)}</body></html>', contienda


def main(salida, fecha_txt):
    doc, contienda = construir(fecha_txt)
    pie = ('<div style="width:100%;font-size:7.5pt;color:#5b6474;padding:0 15mm;display:flex;justify-content:space-between;font-family:sans-serif">'
           f'<span>Radar Electoral · {e(contienda)} · William Andrés Muriel</span><span>Página <span class="pageNumber"></span> de <span class="totalPages"></span></span></div>')
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.set_content(doc, wait_until="load")
        pg.pdf(path=salida, format="A4", print_background=True, display_header_footer=True,
               header_template="<span></span>", footer_template=pie,
               margin={"top": "16mm", "bottom": "18mm", "left": "15mm", "right": "15mm"})
        b.close()
    print("PDF:", salida)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
