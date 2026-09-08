import os
import re
import json
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET

# -------------------------------------------------------------
# CONFIGURACIÓN GENERAL Y CANALES DISCOVERY
# -------------------------------------------------------------
RETENTION_DAYS = 15

AUTH_URL = "https://epg.tapkit.warnermedia.com/api/security/oauth/token"
FILES_URL = "https://epg.tapkit.warnermedia.com/api/getepakfiles?networkId={network_id}&format=CSV"
DOWNLOAD_URL = "https://epg.tapkit.warnermedia.com/api/downloadfiles"

# Mapeo de redes Discovery en Tapkit (Network 47 = Discovery Kids)
DISCOVERY_NETWORKS = {
    "DKLA_EPG.xml": {
        "network_id": 47,
        "generator_name": "Guia de Programacion Discovery Kids MultiFeed",
        "referer": "https://epg.tapkit.warnermedia.com/epg/networks/47",
        "feeds": [
            {
                "file_pattern": "Discovery_Kids_Latin",
                "channel_id": "DKLA_PAN.co",
                "channel_name": "Discovery Kids Panregional",
                "lang": "es",
                "tz": timezone(timedelta(hours=-5)),
                "tz_str": "-0500"
            },
            {
                "file_pattern": "Discovery_Kids_Mexico",
                "channel_id": "DKLA_MX.mx",
                "channel_name": "Discovery Kids México",
                "lang": "es",
                "tz": timezone(timedelta(hours=-6)),
                "tz_str": "-0600"
            },
            {
                "file_pattern": "Discovery_Kids_Caribe",
                "channel_id": "DKLA_CAR.co",
                "channel_name": "Discovery Kids Caribe",
                "lang": "es",
                "tz": timezone(timedelta(hours=-5)),
                "tz_str": "-0500"
            },
            {
                "file_pattern": "Discovery_Kids_Brazil",
                "channel_id": "DKLA_BR.br",
                "channel_name": "Discovery Kids Brasil",
                "lang": "pt",
                "tz": timezone(timedelta(hours=-3)),
                "tz_str": "-0300"
            }
        ]
    }
}

COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://epg.tapkit.warnermedia.com",
    "Referer": "https://epg.tapkit.warnermedia.com/login"
}

def login_and_get_token():
    email = os.environ.get("TAPKIT_EMAIL", "").strip()
    password = os.environ.get("TAPKIT_PASSWORD", "").strip()

    if not email or not password:
        raise Exception("Faltan TAPKIT_EMAIL o TAPKIT_PASSWORD en los Secrets de GitHub.")

    payload = {
        "grant_type": "password",
        "scope": "any",
        "username": email,
        "password": password
    }

    res = requests.post(AUTH_URL, data=payload, headers=COMMON_HEADERS, timeout=30)
    if res.status_code != 200:
        raise Exception(f"Error en login HTTP {res.status_code}: {res.text}")

    token = res.json().get("access_token")
    if not token:
        raise Exception("No se obtuvo access_token.")

    print("[OK] Sesión iniciada en Tapkit.")
    return token

def get_latest_csv_path(token, network_id, pattern, referer_url):
    headers = {
        **COMMON_HEADERS,
        "Authorization": f"Bearer {token}",
        "Referer": referer_url
    }
    
    res = requests.get(FILES_URL.format(network_id=network_id), headers=headers, timeout=30)
    res.raise_for_status()
    
    files_data = res.json()
    if isinstance(files_data, dict):
        files_list = files_data.get("files", files_data.get("data", files_data.get("content", [])))
    else:
        files_list = files_data

    matching_files = []
    for f in files_list:
        filename = f.get("name", f.get("filename", f.get("fileName", "")))
        if pattern.lower() in filename.lower() and filename.endswith(".csv"):
            matching_files.append(f)

    if not matching_files:
        raise Exception(f"No se encontró archivo CSV que coincida con el patrón '{pattern}'")

    latest_file = sorted(matching_files, key=lambda x: x.get("lastModified", x.get("id", "")), reverse=True)[0]
    file_id = latest_file.get("id", latest_file.get("fileId"))
    file_name = latest_file.get("name", latest_file.get("filename", latest_file.get("fileName")))

    print(f"[OK] Archivo detectado para {pattern}: {file_name} (ID: {file_id})")

    dl_payload = {"ids": [file_id]} if file_id else {"files": [file_name]}
    dl_res = requests.post(DOWNLOAD_URL, json=dl_payload, headers=headers, timeout=60)
    
    if dl_res.status_code != 200:
        dl_res = requests.get(f"{DOWNLOAD_URL}?id={file_id}", headers=headers, timeout=60)
    
    dl_res.raise_for_status()

    local_path = f"{pattern}_latest.csv"
    with open(local_path, "wb") as f:
        f.write(dl_res.content)

    return local_path

def corregir_texto(texto):
    if not isinstance(texto, str) or texto.lower() == "nan":
        return ""
    reemplazos = {
        'Ã±': 'ñ', 'Ã‘': 'Ñ', 'Ã¡': 'á', 'Ã©': 'é', 'Ã': 'í', 'Ã³': 'ó', 'Ãº': 'ú',
        'Ã': 'Á', 'Ã‰': 'É', 'Ã': 'Í', 'Ã“': 'Ó', 'Ãš': 'Ú', 'â€™': "'", 'â€œ': '"',
        'â€': '"', 'Â': '', 'Ãª': 'e', 'ÃI': 'Í', 'ÃA': 'Á', 'Ãi': 'í'
    }
    for k, v in reemplazos.items():
        texto = texto.replace(k, v)
    return texto.strip()

def sanitize_and_parse_xml(file_path, generator_name):
    if not os.path.exists(file_path):
        return ET.Element("tv", {"generator-info-name": generator_name})
    try:
        tree = ET.parse(file_path)
        return tree.getroot()
    except Exception:
        return ET.Element("tv", {"generator-info-name": generator_name})

def format_xmltv_date(dt, tz_str):
    return dt.strftime(f"%Y%m%d%H%M%S {tz_str}")

def parse_xmltv_date(date_str, tz_info):
    clean_str = re.sub(r"[^\d\s\+\-]", "", str(date_str).strip())
    match = re.match(r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", clean_str)
    if not match:
        return None
    y, m, d, hh, mm, ss = map(int, match.groups())
    return datetime(y, m, d, min(hh, 23), min(mm, 59), min(ss, 59), tzinfo=tz_info)

def parse_time_hhmm(date_str, time_str, tz):
    clean_date = str(date_str).replace("-", "/").strip()
    clean_time = str(time_str).strip().zfill(4)
    
    hh = int(clean_time[:2])
    mm = int(clean_time[2:4])

    base_date = datetime.strptime(clean_date, "%Y/%m/%d")
    
    extra_days = hh // 24
    hh = hh % 24

    dt = base_date + timedelta(days=extra_days, hours=hh, minutes=mm)
    return dt.replace(tzinfo=tz)

def process_discovery_csv(root, feed_cfg, csv_path):
    channel_id = feed_cfg["channel_id"]
    channel_name = feed_cfg["channel_name"]
    lang = feed_cfg["lang"]
    tz = feed_cfg["tz"]
    tz_str = feed_cfg["tz_str"]

    if not [ch for ch in root.findall("channel") if ch.attrib.get("id") == channel_id]:
        ch_node = ET.SubElement(root, "channel", {"id": channel_id})
        disp = ET.SubElement(ch_node, "display-name")
        disp.text = channel_name

    try:
        df = pd.read_csv(csv_path, sep=',', encoding='utf-8', on_bad_lines='skip')
    except Exception:
        df = pd.read_csv(csv_path, sep=',', encoding='latin-1', on_bad_lines='skip')

    df.columns = df.columns.str.strip()

    new_programmes = []
    for _, row in df.iterrows():
        try:
            date_str = str(row.get("SCHEDULE_DATE", "")).strip()
            start_str = str(row.get("START_TIME", "")).strip()
            end_str = str(row.get("END_TIME", "")).strip()

            if not date_str or not start_str or not end_str or date_str.lower() == "nan":
                continue

            dt_start = parse_time_hhmm(date_str, start_str, tz)
            dt_stop = parse_time_hhmm(date_str, end_str, tz)

            if dt_stop <= dt_start:
                dt_stop += timedelta(days=1)

            series_name = corregir_texto(str(row.get("LOCAL_SERIES_NAME", row.get("SERIES_NAME", ""))))
            prog_name = corregir_texto(str(row.get("LOCAL_PROGRAM_NAME", row.get("TITLE_NAME", ""))))
            description = corregir_texto(str(row.get("LOCAL_PROGRAM_DESCRIPTION", row.get("PROGRAMME_DESCRIPTION", ""))))

            title_final = series_name if series_name else prog_name
            subtitle_final = prog_name if series_name and series_name.lower() != prog_name.lower() else ""

            if not title_final:
                continue

            prog = ET.Element("programme", {
                "start": format_xmltv_date(dt_start, tz_str),
                "stop": format_xmltv_date(dt_stop, tz_str),
                "channel": channel_id
            })

            t_elem = ET.SubElement(prog, "title", {"lang": lang})
            t_elem.text = title_final

            if subtitle_final:
                st_elem = ET.SubElement(prog, "sub-title", {"lang": lang})
                st_elem.text = subtitle_final

            if description:
                d_elem = ET.SubElement(prog, "desc", {"lang": lang})
                d_elem.text = description

            new_programmes.append(prog)
        except Exception:
            continue

    existing_starts = {p.attrib.get("start") for p in root.findall("programme") if p.attrib.get("channel") == channel_id}
    added_count = 0
    for np in new_programmes:
        if np.attrib.get("start") not in existing_starts:
            root.append(np)
            added_count += 1

    print(f"[{channel_id}] Eventos procesados desde CSV: {len(new_programmes)} (Nuevos agregados: {added_count})")

def main():
    token = login_and_get_token()

    for xml_filename, net_config in DISCOVERY_NETWORKS.items():
        print(f"\n==========================================")
        print(f"Procesando: {xml_filename}")
        print(f"==========================================")
        
        root = sanitize_and_parse_xml(xml_filename, net_config["generator_name"])
        active_channel_ids = {cfg["channel_id"] for cfg in net_config["feeds"]}

        for feed_cfg in net_config["feeds"]:
            try:
                csv_path = get_latest_csv_path(token, net_config["network_id"], feed_cfg["file_pattern"], net_config["referer"])
                process_discovery_csv(root, feed_cfg, csv_path)
            except Exception as e:
                print(f"[ERROR] No se pudo procesar {feed_cfg['file_pattern']}: {e}")

        # Retención: Eliminar eventos cuya fecha de fin 'stop' tenga más de 15 días de antigüedad
        now_utc = datetime.now(timezone.utc)
        cutoff_date = now_utc - timedelta(days=RETENTION_DAYS)

        for p in list(root.findall("programme")):
            ch_id = p.attrib.get("channel")
            if ch_id not in active_channel_ids:
                root.remove(p)
                continue
            cfg = next((c for c in net_config["feeds"] if c["channel_id"] == ch_id), net_config["feeds"][0])
            stop_dt = parse_xmltv_date(p.attrib.get("stop", ""), cfg["tz"])
            
            if stop_dt and stop_dt < cutoff_date:
                root.remove(p)

        # Ordenar eventos cronológicamente
        sorted_progs = sorted(root.findall("programme"), key=lambda x: x.attrib.get("start", ""))
        for p in list(root.findall("programme")):
            root.remove(p)
        for p in sorted_progs:
            root.append(p)

        ET.indent(root, space="  ", level=0)
        ET.ElementTree(root).write(xml_filename, encoding="utf-8", xml_declaration=True)
        print(f"[OK] Archivo {xml_filename} guardado con éxito. Total programas: {len(sorted_progs)}")

if __name__ == "__main__":
    main()
