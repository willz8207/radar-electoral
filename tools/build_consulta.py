"""Genera la versión de consulta (sitio estático) a partir del código de la app y
las mediciones exportadas del almacenamiento de la app.

Uso:
  python3 tools/build_consulta.py APP_HTML DBEXPORT_DIR "28 de octubre de 2026"

APP_HTML      archivo HTML de la app (tools/app.html)
DBEXPORT_DIR  carpeta con subcarpetas seguimiento/ y mediciones/ (un JSON por documento)
fecha         texto que se muestra como "mediciones al ..."

Escribe index.html y termometro.json en la raíz del repositorio. historico.json y
puestos/ no cambian entre revisiones.
"""
import glob
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REEMPLAZOS = [
    ('<meta name="claude:viewport-fit-sides" content="cover">\n', ''),
    ("Lectura de Claude", "Lectura asistida"),
    ("Analizar con Claude", "Analizar"),
    ("Claude clasifica", "El asistente clasifica"),
    ("Claude revisa", "El asistente revisa"),
    ("El análisis con Claude", "El análisis"),
    ("La lectura con Claude", "La lectura asistida"),
    ("usar Claude", "usar el asistente"),
    ("Abre la app desde claude.ai con tu cuenta para ver las mediciones guardadas.", "Recarga la página."),
]


def cargar(carpeta):
    docs = []
    for f in sorted(glob.glob(os.path.join(carpeta, "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        cuerpo = dict(d.get("data", d))
        cuerpo["id"] = os.path.basename(f)[:-5]
        docs.append(cuerpo)
    return docs


def main(app_html, dbexport, fecha):
    t = {
        "actualizado": fecha,
        "seguimiento": cargar(os.path.join(dbexport, "seguimiento")),
        "mediciones": cargar(os.path.join(dbexport, "mediciones")),
    }
    with open(os.path.join(RAIZ, "termometro.json"), "w", encoding="utf-8") as f:
        json.dump(t, f, ensure_ascii=False)

    page = open(app_html, encoding="utf-8").read()
    corte = page.index("</style>") + len("</style>")
    head = (
        '<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        '<meta name="robots" content="noindex,nofollow">\n'
        "<script>window.RADAR_ESTATICO=true;</script>\n"
    )
    base = ("\n<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);"
            "padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0;font-size:14px}"
            "img{max-width:100%}</style>\n</head>\n<body>\n")
    html = head + page[:corte] + base + page[corte:] + "\n</body>\n</html>\n"
    for a, b in REEMPLAZOS:
        html = html.replace(a, b)
    with open(os.path.join(RAIZ, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{len(t['seguimiento'])} aspirantes, {len(t['mediciones'])} mediciones")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
