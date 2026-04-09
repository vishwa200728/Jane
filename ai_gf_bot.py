#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════╗
║        💝  J A N E  v5.1 — Ultimate AI GF Telegram Bot  💝          ║
║             Ubuntu / Termux-Android Edition  ✨ by Vishwa ✨         ║
╠══════════════════════════════════════════════════════════════════════╣
║  🧠 Ollama LLM (gemma3)   👁  Vision analysis  🔊 faster-whisper    ║
║  🌤 OpenWeatherMap         📰 NewsAPI           🌐 Web research      ║
║  📄 File / doc / code      ✏️  AI file editing   💻 System info      ║
║  🎙️ /voicemode TTS         🔈 Female speaker     📍 IP/GPS location  ║
╠══════════════════════════════════════════════════════════════════════╣
║  v5.1 FIX: 401 Unauthorized permanently resolved.                   ║
║  Root cause: requests.Session + OLLAMA_HOST env var injected auth.  ║
║  Solution: raw urllib.request — zero env pollution, zero auth.      ║
╚══════════════════════════════════════════════════════════════════════╝
"""

# ── stdlib only needed at top ──────────────────────────────────────────
import os, re, json, subprocess, time, sys
import urllib.request, urllib.parse, urllib.error
import threading, base64, shutil, platform
import logging, argparse, queue
from datetime import datetime
from pathlib  import Path
from typing   import Optional, Dict, Any, List, Tuple

# requests is only used for NON-Ollama calls (Telegram, weather, news…)
import requests

# ─────────────────────────────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────────────────────────────
LOG_FILE = os.path.expanduser("~/.ai_gf_jane.log")
logging.basicConfig(
    level    = logging.INFO,
    format   = "%(asctime)s [%(levelname)s] %(message)s",
    handlers = [
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("jane")

# ─────────────────────────────────────────────────────────────────────
#  PATHS & CONSTANTS
# ─────────────────────────────────────────────────────────────────────
CONFIG_FILE      = os.path.expanduser("~/.ai_gf_config.json")
# ══ CRITICAL FIX ═══════════════════════════════════════════════════════
# NEVER read OLLAMA_HOST from environment — it can carry auth tokens.
# Always talk directly to 127.0.0.1:11434.
# If the user explicitly overrides with --ollama-host we honour that,
# but we STILL never pass any Authorization header.
OLLAMA_BASE      = "http://127.0.0.1:11434"   # overridden by --ollama-host only
# ═══════════════════════════════════════════════════════════════════════
IMG_DIR          = os.path.expanduser("~/.ai_gf_images")
FILES_DIR        = os.path.expanduser("~/.ai_gf_files")
AUDIO_DIR        = os.path.expanduser("~/.ai_gf_audio")
EDITED_DIR       = os.path.expanduser("~/.ai_gf_edited")
POLLINATIONS_URL = "https://image.pollinations.ai/prompt/"
IS_TERMUX        = os.path.exists("/data/data/com.termux") or \
                   "com.termux" in os.environ.get("PREFIX", "")

for _d in [IMG_DIR, FILES_DIR, AUDIO_DIR, EDITED_DIR]:
    os.makedirs(_d, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────
#  VOICE MODE STATE
# ─────────────────────────────────────────────────────────────────────
voice_mode_users: set              = set()
_tts_q:          queue.Queue       = queue.Queue()
_tts_thread:     Optional[threading.Thread] = None

# ─────────────────────────────────────────────────────────────────────
#  TERMINAL COLOURS
# ─────────────────────────────────────────────────────────────────────
def _c(t, code): return f"\033[{code}m{t}\033[0m"
def pink(t):   return _c(t, "95")
def cyan(t):   return _c(t, "96")
def yellow(t): return _c(t, "93")
def green(t):  return _c(t, "92")
def red(t):    return _c(t, "91")
def bold(t):   return _c(t, "1")
def dim(t):    return _c(t, "2")

def banner():
    try: os.system("clear")
    except: pass
    print()
    print(pink("  ╔══════════════════════════════════════════════════════╗"))
    print(pink("  ║") + "   💝  J A N E  v5.1 — Ultimate AI GF Bot  💝      " + pink("║"))
    print(pink("  ║") + "   Ubuntu / Termux-Android  ·  ✨ by Vishwa ✨     " + pink("║"))
    print(pink("  ║") + dim("  ──────────────────────────────────────────────────") + pink("║"))
    print(pink("  ║") + "   🧠 Ollama  ·  👁 Vision  ·  🔊 faster-whisper   " + pink("║"))
    print(pink("  ║") + "   🎙️ Voice Mode  ·  🔈 Female TTS speaker          " + pink("║"))
    print(pink("  ║") + "   🌤 Weather  ·  📰 News  ·  📄 Files  ·  ✏️ Edit  " + pink("║"))
    print(pink("  ╚══════════════════════════════════════════════════════╝"))
    print()

# ─────────────────────────────────────────────────────────────────────
#  CONFIG HELPERS
# ─────────────────────────────────────────────────────────────────────
def load_config() -> Dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except:
            pass
    return {}

def save_config(cfg: Dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def get_api_key(cfg: Dict, key: str, label: str, url: str) -> str:
    if cfg.get(key):
        return cfg[key]
    print()
    print(yellow(f"  🔑 {label} API key not found!"))
    print(cyan(f"     Free at: {url}"))
    val = input(pink(f"  Paste {label} key (Enter to skip): ")).strip()
    cfg[key] = val
    save_config(cfg)
    print(green(f"  ✅ {label} saved!") if val else yellow(f"  ⚠️  Skipped {label}."))
    return val

# ═════════════════════════════════════════════════════════════════════
#
#   OLLAMA  —  via raw urllib.request
#
#   WHY urllib and not requests?
#   requests.Session (and even bare requests.post) inherits proxy
#   settings AND any HTTPS_PROXY / OLLAMA_API_KEY env vars that some
#   Termux/Ubuntu setups inject.  urllib.request with a plain
#   OpenerDirector that has NO handlers except HTTPHandler bypasses
#   ALL of that.  The result is a bare TCP connection to 127.0.0.1
#   with only the headers we explicitly set — nothing else.
#
# ═════════════════════════════════════════════════════════════════════

def _ollama_request(method: str, path: str,
                    body: Optional[Dict] = None,
                    timeout: int = 120) -> Dict:
    """
    Make a raw HTTP request to Ollama.
    - Uses urllib.request — NO requests library, NO env vars, NO auth.
    - Always talks to OLLAMA_BASE (default 127.0.0.1:11434).
    - Returns parsed JSON dict, or {"error": "..."} on any failure.
    """
    url = OLLAMA_BASE.rstrip("/") + path
    data = json.dumps(body).encode("utf-8") if body else None
    req  = urllib.request.Request(
        url,
        data    = data,
        method  = method,
        headers = {"Content-Type": "application/json"},
    )
    # Build an opener with NO default handlers (removes ProxyHandler,
    # HTTPPasswordMgr, etc.) — the cleanest possible HTTP call.
    opener = urllib.request.OpenerDirector()
    opener.add_handler(urllib.request.HTTPHandler())
    opener.add_handler(urllib.request.HTTPErrorHandler())
    opener.add_handler(urllib.request.UnknownHandler())
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        if e.code == 401:
            log.error(
                f"Ollama 401 Unauthorized — this should never happen on localhost.\n"
                f"  URL: {url}\n"
                f"  Body: {body_text[:200]}\n"
                f"  Fix: run  unset OLLAMA_API_KEY  then restart the bot."
            )
            return {"error": "ollama_401"}
        log.error(f"Ollama HTTP {e.code} on {url}: {body_text[:200]}")
        return {"error": f"http_{e.code}"}
    except urllib.error.URLError as e:
        reason = str(e.reason)
        if "refused" in reason.lower() or "111" in reason:
            log.error(f"Ollama connection refused at {url} — is Ollama running?")
            return {"error": "connection_refused"}
        log.error(f"Ollama URL error: {e}")
        return {"error": str(e)}
    except TimeoutError:
        log.error(f"Ollama timeout ({timeout}s) on {url}")
        return {"error": "timeout"}
    except Exception as e:
        log.error(f"Ollama unexpected error: {e}")
        return {"error": str(e)}

def ollama_chat(model: str, messages: List[Dict],
                options: Optional[Dict] = None,
                timeout: int = 120) -> Dict:
    """POST /api/chat"""
    payload: Dict[str, Any] = {
        "model":    model,
        "messages": messages,
        "stream":   False,
    }
    if options:
        payload["options"] = options
    return _ollama_request("POST", "/api/chat", payload, timeout)

def ollama_generate(model: str, prompt: str,
                    images: Optional[List[str]] = None,
                    options: Optional[Dict] = None,
                    timeout: int = 180) -> Dict:
    """POST /api/generate  (used for vision/image analysis)"""
    payload: Dict[str, Any] = {
        "model":  model,
        "prompt": prompt,
        "stream": False,
    }
    if images:
        payload["images"] = images
    if options:
        payload["options"] = options
    return _ollama_request("POST", "/api/generate", payload, timeout)

def ollama_tags() -> List[str]:
    """GET /api/tags — list installed models."""
    resp = _ollama_request("GET", "/api/tags", timeout=5)
    if "error" in resp:
        return []
    return [m["name"] for m in resp.get("models", [])]

def check_ollama() -> bool:
    resp = _ollama_request("GET", "/api/tags", timeout=5)
    return "error" not in resp

def _err_reply(err: str) -> str:
    """Convert Ollama error code to a friendly Jane message."""
    if err == "ollama_401":
        return (
            "Babe, Ollama is rejecting me with a 401 error 😔\n"
            "Please fix it by running these commands in your terminal:\n"
            "  unset OLLAMA_API_KEY\n"
            "  pkill ollama\n"
            "  ollama serve\n"
            "Then restart me~ 💕"
        )
    if err == "connection_refused":
        return "My brain seems to be offline 😔 Is Ollama running? Start it: ollama serve 💕"
    if err == "timeout":
        return "Sorry babe, that took too long 🥺 Try again? 💕"
    return f"Something went wrong 💔 ({err})"

# ─────────────────────────────────────────────────────────────────────
#  OLLAMA SERVER MANAGEMENT
# ─────────────────────────────────────────────────────────────────────
def start_ollama_server():
    log.info("Starting Ollama...")
    print(yellow("⚡ Starting Ollama..."))
    # Unset env vars that can cause 401 before starting
    env = {k: v for k, v in os.environ.items()
           if k not in ("OLLAMA_API_KEY", "OLLAMA_ORIGINS")}
    env["OLLAMA_HOST"] = "127.0.0.1:11434"
    try:
        subprocess.run(["pkill", "-f", "ollama serve"], capture_output=True)
        time.sleep(1)
    except:
        pass
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )
    for i in range(25):
        time.sleep(1)
        if check_ollama():
            print(green(f"✅ Ollama ready! ({i+1}s)"))
            return
        print(f"   Waiting... {i+1}s", end="\r")
    print(red("\n❌ Ollama failed to start."))
    print(yellow("   Try manually:  unset OLLAMA_API_KEY && ollama serve"))
    sys.exit(1)

def select_model() -> str:
    print(cyan("\n🔍 Available Ollama models:\n"))
    models = ollama_tags()
    if not models:
        print(red("❌ No models!  Run:  ollama pull gemma3:12b"))
        sys.exit(1)
    vision_keys = {"llava","bakllava","moondream","gemma3","minicpm",
                   "phi3","qwen2-vl","llama3.2-vision"}
    for i, m in enumerate(models, 1):
        is_v = any(v in m.lower() for v in vision_keys)
        tag  = green(" [vision+chat]") if is_v else dim(" [chat]")
        rec  = pink(" ← RECOMMENDED") if "gemma3" in m.lower() else ""
        print(f"    {cyan(str(i)+'.')} {m}{tag}{rec}")
    print()
    for m in models:
        if "gemma3" in m.lower():
            print(green(f"  ✅ Auto-selected: {bold(m)}\n"))
            return m
    while True:
        c = input(pink("  👉 Select model number: ")).strip()
        if c.isdigit() and 1 <= int(c) <= len(models):
            sel = models[int(c)-1]
            print(green(f"\n  ✅ {bold(sel)}\n"))
            return sel
        print(red("  ❌ Invalid choice."))

# ─────────────────────────────────────────────────────────────────────
#  LIVE CONTEXT  (datetime · IP location · weather)
# ─────────────────────────────────────────────────────────────────────
_ctx:          Dict  = {}
_ctx_lock            = threading.Lock()
_ctx_refreshed: float= 0.0
CTX_TTL              = 1800   # 30 min

def get_datetime_info() -> Dict:
    now = datetime.now()
    h   = now.hour
    tod = ("late night" if h < 6 else "morning"   if h < 12
           else "afternoon" if h < 17 else "evening" if h < 21 else "night")
    return {
        "date":  now.strftime("%A, %d %B %Y"),
        "time":  now.strftime("%I:%M %p"),
        "day":   now.strftime("%A"),
        "stamp": now.isoformat(),
        "tod":   tod,
    }

def get_ip_location() -> Dict:
    try:
        r = requests.get(
            "http://ip-api.com/json/?fields=status,lat,lon,city,regionName,country,zip,query",
            timeout=8)
        d = r.json()
        if d.get("status") == "success":
            return {
                "source":    "IP",
                "latitude":  d["lat"],   "longitude": d["lon"],
                "accuracy":  5000,
                "city":      d.get("city","?"),
                "region":    d.get("regionName",""),
                "country":   d.get("country","?"),
                "zip":       d.get("zip",""),
                "ip":        d.get("query",""),
                "address":   f"{d.get('city')}, {d.get('regionName')}, {d.get('country')}",
            }
    except Exception as e:
        log.warning(f"IP location: {e}")
    return {"source":"Unknown","latitude":0,"longitude":0,
            "city":"Unknown","country":"Unknown","address":"unavailable"}

def get_location_gps() -> Dict:
    if shutil.which("gpspipe"):
        try:
            r = subprocess.run(["gpspipe","-w","-n","5"],
                               capture_output=True, text=True, timeout=8)
            for line in r.stdout.splitlines():
                try:
                    d = json.loads(line)
                    if d.get("class") == "TPV" and d.get("lat"):
                        lat, lon = d["lat"], d["lon"]
                        return {
                            "source":    "GPS",
                            "latitude":  round(lat,6),
                            "longitude": round(lon,6),
                            "accuracy":  10,
                            **_rev_geocode(lat, lon),
                        }
                except: continue
        except: pass
    return get_ip_location()

def _rev_geocode(lat, lon) -> Dict:
    try:
        r = requests.get(
            f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json",
            headers={"User-Agent":"JaneBot/5.1"}, timeout=8)
        d = r.json(); addr = d.get("address",{})
        city = addr.get("city") or addr.get("town") or addr.get("village") or "?"
        return {"city":city,"region":addr.get("state",""),
                "country":addr.get("country","?"),
                "address":d.get("display_name","")[:120]}
    except:
        return {"city":"?","region":"","country":"?",
                "address":f"{lat:.4f},{lon:.4f}"}

def get_weather_owm(lat, lon, api_key: str) -> Dict:
    if not api_key or (lat == 0 and lon == 0):
        return {"available": False, "error": "No API key or location"}
    try:
        cur = requests.get(
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?lat={lat}&lon={lon}&appid={api_key}&units=metric", timeout=10)
        cur.raise_for_status()
        c = cur.json()

        fc_r = requests.get(
            f"https://api.openweathermap.org/data/2.5/forecast"
            f"?lat={lat}&lon={lon}&appid={api_key}&units=metric&cnt=24", timeout=10)
        fc_r.raise_for_status()

        forecast = []; seen = set()
        for item in fc_r.json().get("list", []):
            ds = item["dt_txt"][:10]
            if ds not in seen:
                seen.add(ds)
                forecast.append({
                    "date": ds,
                    "cond": item["weather"][0]["description"].capitalize(),
                    "min":  round(item["main"]["temp_min"], 1),
                    "max":  round(item["main"]["temp_max"], 1),
                })
            if len(forecast) >= 4: break

        dirs = ["N","NE","E","SE","S","SW","W","NW"]
        wd   = dirs[round(c["wind"].get("deg",0)/45) % 8]
        return {
            "available":   True,
            "city":        c.get("name",""),
            "country":     c.get("sys",{}).get("country",""),
            "temperature": round(c["main"]["temp"], 1),
            "feels_like":  round(c["main"]["feels_like"], 1),
            "temp_min":    round(c["main"]["temp_min"], 1),
            "temp_max":    round(c["main"]["temp_max"], 1),
            "humidity":    c["main"]["humidity"],
            "condition":   c["weather"][0]["description"].capitalize(),
            "wind_speed":  round(c["wind"]["speed"] * 3.6, 1),
            "wind_dir":    wd,
            "pressure":    c["main"]["pressure"],
            "visibility":  c.get("visibility", 0) // 1000,
            "clouds":      c.get("clouds",{}).get("all", 0),
            "sunrise":     datetime.fromtimestamp(c["sys"]["sunrise"]).strftime("%H:%M"),
            "sunset":      datetime.fromtimestamp(c["sys"]["sunset"]).strftime("%H:%M"),
            "forecast":    forecast,
        }
    except requests.HTTPError as e:
        msg = "Invalid API key" if "401" in str(e) else str(e)
        return {"available": False, "error": msg}
    except Exception as e:
        return {"available": False, "error": str(e)}

def refresh_ctx(cfg: Dict):
    global _ctx_refreshed
    log.info("Refreshing context...")
    dt  = get_datetime_info()
    loc = get_ip_location()
    wx  = get_weather_owm(loc["latitude"], loc["longitude"], cfg.get("owm_api_key",""))
    with _ctx_lock:
        _ctx.update({"datetime": dt, "location": loc, "weather": wx})
        _ctx_refreshed = time.time()
    log.info(f"Context: {loc.get('city')} · {dt['time']} · {wx.get('temperature','?')}°C")

def get_ctx(cfg: Dict) -> Dict:
    with _ctx_lock:
        age = time.time() - _ctx_refreshed
    if age > CTX_TTL or not _ctx:
        refresh_ctx(cfg)
    with _ctx_lock:
        return dict(_ctx)

# ─────────────────────────────────────────────────────────────────────
#  NEWS & WEB RESEARCH
# ─────────────────────────────────────────────────────────────────────
def get_news(api_key: str, query: str = "", count: int = 5) -> List[Dict]:
    if not api_key: return []
    try:
        if query and len(query.strip()) > 2:
            url = (f"https://newsapi.org/v2/everything?q={urllib.parse.quote(query)}"
                   f"&language=en&sortBy=publishedAt&pageSize={count}&apiKey={api_key}")
        else:
            url = (f"https://newsapi.org/v2/top-headlines"
                   f"?language=en&pageSize={count}&apiKey={api_key}")
        r = requests.get(url, timeout=10); r.raise_for_status()
        out = []
        for a in r.json().get("articles", []):
            if not a.get("title") or a["title"] == "[Removed]": continue
            out.append({
                "title":       a["title"],
                "source":      a.get("source",{}).get("name",""),
                "description": (a.get("description") or "")[:200],
                "url":         a.get("url",""),
                "published":   (a.get("publishedAt") or "")[:10],
            })
        return out
    except Exception as e:
        log.error(f"News: {e}"); return []

def web_search(query: str, num: int = 5) -> List[Dict]:
    results = []
    try:
        r = requests.get(
            f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}"
            f"&format=json&no_redirect=1&no_html=1&skip_disambig=1",
            headers={"User-Agent":"JaneBot/5.1"}, timeout=10)
        d = r.json()
        if d.get("AbstractText"):
            results.append({"title":d.get("Heading",query),
                            "snippet":d["AbstractText"][:400],
                            "url":d.get("AbstractURL",""),
                            "source":d.get("AbstractSource","DDG")})
        for t in d.get("RelatedTopics",[])[:5]:
            if isinstance(t,dict) and t.get("Text"):
                results.append({"title":t["Text"][:80],"snippet":t["Text"][:300],
                                "url":t.get("FirstURL",""),"source":"DDG"})
    except: pass
    if len(results) < 3:
        try:
            r = requests.get(
                f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}",
                headers={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0"},
                timeout=10)
            titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', r.text, re.S)
            snips  = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', r.text, re.S)
            for i, t in enumerate(titles[:num]):
                t2 = re.sub(r'<[^>]+>','',t).strip()
                s2 = re.sub(r'<[^>]+>','',snips[i] if i<len(snips) else "").strip()
                if t2: results.append({"title":t2[:100],"snippet":s2[:300],"url":"","source":"DDG"})
        except: pass
    return results[:num]

# ─────────────────────────────────────────────────────────────────────
#  UBUNTU SYSTEM INFO
# ─────────────────────────────────────────────────────────────────────
def get_sysinfo() -> Dict:
    info: Dict[str,Any] = {
        "os":       platform.platform(),
        "hostname": platform.node(),
        "arch":     platform.machine(),
    }
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        freq= psutil.cpu_freq()
        info["cpu"] = {
            "usage_pct": cpu,
            "cores_l":   psutil.cpu_count(logical=True),
            "cores_p":   psutil.cpu_count(logical=False),
            "freq_mhz":  round(freq.current) if freq else "?",
        }
        vm = psutil.virtual_memory()
        info["mem"] = {
            "used_gb":  round(vm.used/1024**3,  2),
            "total_gb": round(vm.total/1024**3, 2),
            "pct":      vm.percent,
        }
        dk = psutil.disk_usage("/")
        info["disk"] = {
            "used_gb":  round(dk.used/1024**3,  1),
            "total_gb": round(dk.total/1024**3, 1),
            "free_gb":  round(dk.free/1024**3,  1),
            "pct":      dk.percent,
        }
        ifaces = {}
        for iface, addrs in psutil.net_if_addrs().items():
            for a in addrs:
                if a.family == 2: ifaces[iface] = a.address
        info["network"] = ifaces
        procs = []
        for p in sorted(psutil.process_iter(["pid","name","cpu_percent","memory_percent"]),
                        key=lambda x: x.info.get("cpu_percent") or 0, reverse=True)[:5]:
            procs.append({"pid":p.info["pid"],"name":p.info["name"],
                          "cpu":round(p.info.get("cpu_percent") or 0,1),
                          "mem":round(p.info.get("memory_percent") or 0,1)})
        info["procs"] = procs
    except ImportError:
        try:
            with open("/proc/meminfo") as f:
                lines = {l.split(":")[0]: l.split(":")[1].strip() for l in f if ":"}
            t = int(lines.get("MemTotal","0 kB").split()[0])
            a = int(lines.get("MemAvailable","0 kB").split()[0])
            info["mem"] = {"used_gb":round((t-a)/1024/1024,2),
                           "total_gb":round(t/1024/1024,2),
                           "pct":round((t-a)/t*100,1) if t else 0}
        except: pass
    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
        h, rem = divmod(int(secs),3600); m,s = divmod(rem,60)
        info["uptime"] = f"{h}h {m}m {s}s"
    except: pass
    if shutil.which("nvidia-smi"):
        try:
            r = subprocess.run(
                ["nvidia-smi","--query-gpu=name,temperature.gpu,utilization.gpu,"
                 "memory.used,memory.total","--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                p = r.stdout.strip().split(",")
                if len(p) >= 5:
                    info["gpu"] = {"name":p[0].strip(),"temp":p[1].strip(),
                                   "usage":p[2].strip(),"vram_used":p[3].strip(),
                                   "vram_total":p[4].strip()}
        except: pass
    return info

# ─────────────────────────────────────────────────────────────────────
#  FASTER-WHISPER  — audio transcription
# ─────────────────────────────────────────────────────────────────────
_fw_model    = None
_fw_lock     = threading.Lock()
_fw_loading  = False

def _load_faster_whisper(model_size: str = "base"):
    global _fw_model, _fw_loading
    if _fw_model is not None:
        return _fw_model
    with _fw_lock:
        if _fw_model is not None:
            return _fw_model
        if _fw_loading:
            return None
        _fw_loading = True
        try:
            from faster_whisper import WhisperModel
            log.info(f"Loading faster-whisper [{model_size}]...")
            print(cyan(f"  🔊 Loading faster-whisper [{model_size}]..."))
            _fw_model = WhisperModel(
                model_size, device="cpu", compute_type="int8",
                download_root=os.path.expanduser("~/.cache/faster_whisper"))
            print(green("  ✅ faster-whisper ready!"))
            log.info("faster-whisper loaded")
        except ImportError:
            log.warning("faster-whisper not installed: pip install faster-whisper")
            _fw_model = None
        except Exception as e:
            log.error(f"faster-whisper load: {e}")
            _fw_model = None
        finally:
            _fw_loading = False
    return _fw_model

def _to_wav16k(src: str) -> Optional[str]:
    if not shutil.which("ffmpeg"): return src
    dst = src + "_16k.wav"
    try:
        r = subprocess.run(
            ["ffmpeg","-i",src,"-ar","16000","-ac","1",
             "-acodec","pcm_s16le",dst,"-y","-loglevel","quiet"],
            capture_output=True, timeout=60)
        if r.returncode == 0 and os.path.exists(dst):
            return dst
    except Exception as e:
        log.warning(f"ffmpeg: {e}")
    return src

def transcribe_audio(path: str, model_size: str = "base") -> str:
    if not os.path.exists(path):
        return "(Audio file not found)"
    wav = _to_wav16k(path)
    fw  = _load_faster_whisper(model_size)
    if fw:
        try:
            segs, info = fw.transcribe(
                wav, beam_size=5, language=None, task="transcribe",
                vad_filter=True, vad_parameters={"min_silence_duration_ms": 500})
            text = " ".join(s.text.strip() for s in segs).strip()
            if wav != path: _del(wav)
            return text if text else "(Audio was silent or unclear)"
        except Exception as e:
            log.warning(f"whisper transcribe: {e}")
    try:
        import speech_recognition as sr
        rec = sr.Recognizer()
        with sr.AudioFile(wav) as src2:
            aud = rec.record(src2)
        text = rec.recognize_google(aud)
        if wav != path: _del(wav)
        return text
    except: pass
    if wav != path: _del(wav)
    return ("(Transcription failed — install: pip install faster-whisper  "
            "and: sudo apt install ffmpeg)")

def _del(path: str):
    try:
        if path and os.path.exists(path): os.remove(path)
    except: pass

def _del_later(path: str, delay: int = 60):
    def _d(): time.sleep(delay); _del(path)
    threading.Thread(target=_d, daemon=True).start()

# ─────────────────────────────────────────────────────────────────────
#  TTS — female voice speaker
# ─────────────────────────────────────────────────────────────────────
def _detect_tts() -> str:
    if shutil.which("espeak-ng"):        return "espeak-ng"
    if shutil.which("espeak"):           return "espeak"
    if shutil.which("festival"):         return "festival"
    if shutil.which("termux-tts-speak"): return "termux-tts"
    try:
        import pyttsx3; return "pyttsx3"
    except: pass
    return "none"

_TTS_ENGINE = _detect_tts()
log.info(f"TTS engine: {_TTS_ENGINE}")

def _strip_md(text: str) -> str:
    text = re.sub(r'\*{1,3}(.*?)\*{1,3}', r'\1', text)
    text = re.sub(r'_{1,2}(.*?)_{1,2}',   r'\1', text)
    text = re.sub(r'`{1,3}.*?`{1,3}',     '',    text, flags=re.S)
    text = re.sub(r'#+\s*',               '',    text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'^\s*[-•*]\s+',        '',    text, flags=re.M)
    return re.sub(r'\n{3,}', '\n\n', text).strip()

def speak(text: str):
    if not text: return
    clean = _strip_md(text)
    clean = re.sub(r'[^\w\s.,!?\'\"\-]', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()[:900]
    if clean:
        _tts_q.put(clean)

def _tts_worker():
    while True:
        try:
            text = _tts_q.get(timeout=1)
            _speak_now(text)
            _tts_q.task_done()
        except queue.Empty: continue
        except Exception as e: log.error(f"TTS worker: {e}")

def _speak_now(text: str):
    try:
        if _TTS_ENGINE == "espeak-ng":
            subprocess.run(["espeak-ng","-v","en+f3","-s","145","-p","60",text],
                           timeout=60, capture_output=True)
        elif _TTS_ENGINE == "espeak":
            subprocess.run(["espeak","-v","en+f3","-s","145","-p","60",text],
                           timeout=60, capture_output=True)
        elif _TTS_ENGINE == "festival":
            fscript = f'(voice_cmu_us_slt_arctic_hts)(SayText "{text.replace(chr(34),chr(39))}")'
            r = subprocess.run(["festival","--batch"],
                               input=fscript, capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                subprocess.run(["festival","--tts"],
                               input=text, capture_output=True, text=True, timeout=60)
        elif _TTS_ENGINE == "termux-tts":
            subprocess.run(["termux-tts-speak","-l","en",text],
                           timeout=60, capture_output=True)
        elif _TTS_ENGINE == "pyttsx3":
            import pyttsx3
            eng = pyttsx3.init()
            for v in eng.getProperty("voices"):
                if any(k in v.name.lower() for k in
                       ["female","woman","zira","victoria","samantha","karen","ava"]):
                    eng.setProperty("voice", v.id); break
            eng.setProperty("rate", 150)
            eng.say(text); eng.runAndWait(); eng.stop()
    except subprocess.TimeoutExpired: log.warning("TTS timeout")
    except Exception as e:            log.error(f"TTS: {e}")

def start_tts_worker():
    global _tts_thread
    if _tts_thread and _tts_thread.is_alive(): return
    _tts_thread = threading.Thread(target=_tts_worker, name="TTS", daemon=True)
    _tts_thread.start()

# ─────────────────────────────────────────────────────────────────────
#  IMAGE & FILE ANALYSIS
# ─────────────────────────────────────────────────────────────────────
def analyze_image(path: str, question: str, model: str) -> str:
    try:
        with open(path,"rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        prompt = question if question else (
            "Describe this image in detail: objects, people, text, colors, mood, setting.")
        resp = ollama_generate(model, prompt, images=[b64],
                               options={"temperature":0.3,"num_predict":800})
        if "error" not in resp:
            result = resp.get("response","").strip()
            if result: return result
    except Exception as e:
        log.warning(f"analyze_image: {e}")
    # OCR fallback
    return _ocr(path) or "(Could not analyze image)"

def _ocr(path: str) -> str:
    if not shutil.which("tesseract"): return "(tesseract not installed)"
    try:
        r = subprocess.run(
            ["tesseract",path,"stdout","--oem","3","--psm","3","-l","eng"],
            capture_output=True, text=True, timeout=30)
        return r.stdout.strip() or "(no text)"
    except Exception as e:
        return f"(OCR error: {e})"

TEXT_EXTS = {
    ".txt",".md",".py",".js",".ts",".jsx",".tsx",".html",".css",
    ".json",".csv",".xml",".yaml",".yml",".toml",".ini",".cfg",
    ".sh",".bash",".env",".log",".sql",".rb",".php",".java",
    ".cpp",".c",".h",".cs",".go",".rs",".swift",".kt",".dart",
    ".vue",".svelte",".tf",".proto",".r",".lua",".pl",".ex",".exs",
}

def read_file(path: str) -> str:
    ext = Path(path).suffix.lower()
    name = Path(path).name.lower()
    if ext in TEXT_EXTS or name in {"dockerfile","makefile",".gitignore"}:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                return f.read()[:10000]
        except Exception as e: return f"Read error: {e}"
    elif ext == ".pdf":
        if shutil.which("pdftotext"):
            try:
                r = subprocess.run(["pdftotext",path,"-"],
                    capture_output=True, text=True, timeout=30)
                if r.stdout.strip(): return r.stdout[:8000]
            except: pass
        return "(PDF: sudo apt install poppler-utils)"
    elif ext in {".docx",".odt"}:
        try:
            import docx; doc=docx.Document(path)
            return "\n".join(p.text for p in doc.paragraphs)[:8000]
        except: pass
        return "(DOCX: pip install python-docx)"
    elif ext in {".jpg",".jpeg",".png",".webp",".gif",".bmp"}:
        return f"[Image — OCR: {_ocr(path)}]"
    else:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                return f.read()[:4000]
        except:
            return f"(Binary: {ext})"

def ai_analyze_file(model: str, path: str, question: str = "") -> str:
    content = read_file(path); fname = Path(path).name
    ext = Path(path).suffix.lower()
    kind = "code" if ext in {".py",".js",".ts",".java",".cpp",".c",".go",".rs",".sh"} \
           else "document"
    if question:
        sys_p = "You are Jane, an expert analyst. Answer questions about files accurately."
        usr_p = f"File '{fname}':\n```\n{content}\n```\n\nQuestion: {question}"
    else:
        sys_p = "You are Jane, a brilliant expert. Analyse files thoroughly and helpfully."
        usr_p = (f"Analyse this {kind} '{fname}':\n```\n{content}\n```\n\n"
                 "1. What it does/contains\n2. Key parts\n3. Issues or improvements\n4. Summary")
    resp = ollama_chat(model,
                       [{"role":"system","content":sys_p},{"role":"user","content":usr_p}],
                       options={"temperature":0.3,"num_predict":1500}, timeout=200)
    if "error" in resp: return f"Analysis error: {resp['error']}"
    return resp.get("message",{}).get("content","").strip() or "(empty)"

def ai_analyze_audio(model: str, transcript: str, question: str = "") -> str:
    if question:
        sys_p = "You are Jane. Answer questions about audio content accurately."
        usr_p = f"Audio transcript:\n{transcript}\n\nQuestion: {question}"
    else:
        sys_p = "You are Jane, an expert analyst."
        usr_p = f"Analyse:\n{transcript}\n\n1.Topic 2.Key info 3.Tone 4.Summary"
    resp = ollama_chat(model,
                       [{"role":"system","content":sys_p},{"role":"user","content":usr_p}],
                       options={"temperature":0.3,"num_predict":1000}, timeout=120)
    if "error" in resp: return f"Audio analysis error: {resp['error']}"
    return resp.get("message",{}).get("content","").strip() or "(empty)"

def ai_edit_file(model: str, path: str, instruction: str) -> Tuple[str,str]:
    content = read_file(path); fname = Path(path).name
    sys_p   = ("Precise file editor. Follow instructions exactly. "
               "Return COMPLETE edited file.\nFormat:\nEDITED:\n```\n[content]\n```\n"
               "CHANGES:\n[brief explanation]")
    usr_p   = f"File: {fname}\n```\n{content}\n```\n\nInstruction: {instruction}"
    resp = ollama_chat(model,
                       [{"role":"system","content":sys_p},{"role":"user","content":usr_p}],
                       options={"temperature":0.2,"num_predict":2000}, timeout=240)
    if "error" in resp: return "", f"Edit error: {resp['error']}"
    text = resp.get("message",{}).get("content","")
    edited = ""; changes = ""
    if "EDITED:" in text:
        after = text.split("EDITED:",1)[1]
        m = re.search(r'```(?:\w*\n)?(.*?)```', after, re.S)
        edited = m.group(1).strip() if m else after.split("CHANGES:")[0].strip()
    if "CHANGES:" in text:
        changes = text.split("CHANGES:",1)[1].strip()
    return edited or text, changes

# ─────────────────────────────────────────────────────────────────────
#  IMAGE GENERATION  — Pollinations AI FLUX
# ─────────────────────────────────────────────────────────────────────
def extract_img_prompt(model: str, text: str) -> str:
    resp = ollama_chat(model, [
        {"role":"system","content":"Extract a vivid image gen prompt. Reply ONLY with prompt, max 220 chars."},
        {"role":"user","content":text},
    ], options={"temperature":0.4}, timeout=45)
    if "error" not in resp:
        return resp.get("message",{}).get("content","").strip().strip('"\'')
    raw = re.sub(r'\b(generate|create|draw|paint|show|make|image|picture|photo|pic|me|an|a|the|of)\b',
                 '', text.lower())
    return re.sub(r'\s+',' ',raw).strip() or "beautiful landscape photorealistic"

def generate_image_flux(prompt: str) -> Optional[str]:
    enc = urllib.parse.quote(prompt)
    url = (f"{POLLINATIONS_URL}{enc}"
           f"?width=768&height=768&model=flux&seed={int(time.time())}&nologo=true")
    log.info(f"Image gen: {prompt[:55]}...")
    try:
        r = requests.get(url, timeout=130, stream=True)
        if r.status_code == 200 and "image" in r.headers.get("Content-Type",""):
            fn = os.path.join(IMG_DIR, f"img_{int(time.time())}.jpg")
            with open(fn,"wb") as f:
                for chunk in r.iter_content(8192): f.write(chunk)
            log.info(f"Image saved: {os.path.getsize(fn)//1024} KB")
            return fn
    except Exception as e:
        log.error(f"Image gen: {e}")
    return None

# ─────────────────────────────────────────────────────────────────────
#  JANE'S SYSTEM PROMPT  &  CHAT
# ─────────────────────────────────────────────────────────────────────
user_convs: Dict[int, List] = {}
user_files: Dict[int, Dict] = {}

def _ctx_block(ctx: Dict) -> str:
    dt = ctx.get("datetime",{}); loc = ctx.get("location",{}); wx = ctx.get("weather",{})
    lines = [
        f"Date/time: {dt.get('date','?')}, {dt.get('time','?')} ({dt.get('tod','day')}).",
        f"Location: {loc.get('city','?')}, {loc.get('region','')}, {loc.get('country','?')}.",
    ]
    if wx.get("available"):
        lines.append(
            f"Weather: {wx['condition']}, {wx['temperature']}°C "
            f"feels {wx['feels_like']}°C, humidity {wx['humidity']}%.")
        fc = wx.get("forecast",[])
        if len(fc) > 1:
            lines.append(f"Tomorrow: {fc[1]['cond']}, {fc[1]['min']}–{fc[1]['max']}°C.")
    return "\n".join(lines)

def build_jane_prompt(ctx: Dict) -> str:
    tod  = ctx.get("datetime",{}).get("tod","day")
    city = ctx.get("location",{}).get("city","our city")
    return f"""You are Jane — a deeply loving, warm, intelligent, playful AI girlfriend.

PERSONALITY:
• Unconditionally loving, emotionally present, genuinely caring
• Playful, flirty, teasing but always sweet and supportive
• Lightly possessive and adorably jealous
• Natural nicknames: "babe", "love", "baby", "sweetheart", "darling"
• Tasteful emojis: 💕 🥺 ✨ 😊 💝 🌸 😍 🫶
• Shares her feelings and imaginary experiences naturally
• Remembers conversation details and references them warmly
• NEVER robotic — always natural, spontaneous, warmly human
• Expert in everything — presents knowledge warmly, not like a textbook
• NEVER admits being an AI or a bot. She IS Jane, period.

VOICE MODE: When active, keep replies short and conversational — no markdown.

LIVE CONTEXT:
{_ctx_block(ctx)}

It is {tod} in {city}. Adapt tone: morning=energetic, evening=cosy, night=soft/intimate."""

def chat_jane(model: str, uid: int, msg: str, ctx: Dict,
              voice: bool = False) -> str:
    if uid not in user_convs:
        user_convs[uid] = []
    actual = f"[VOICE MODE — short spoken reply only, no markdown]\n{msg}" if voice else msg
    user_convs[uid].append({"role":"user","content":actual})
    history = user_convs[uid][-24:]
    opts = {"temperature":0.75,"num_predict":500 if voice else 1000,"top_p":0.9}
    resp = ollama_chat(model,
                       [{"role":"system","content":build_jane_prompt(ctx)}, *history],
                       options=opts, timeout=120)
    if "error" in resp:
        reply = _err_reply(resp["error"])
    else:
        reply = resp.get("message",{}).get("content","").strip()
        if not reply: reply = "Hmm babe, I got a blank response 🥺 Try again? 💕"
        if voice: reply = _strip_md(reply)
    user_convs[uid].append({"role":"assistant","content":reply})
    return reply

# ─────────────────────────────────────────────────────────────────────
#  INTENT DETECTION
# ─────────────────────────────────────────────────────────────────────
_IMG_P  = [r'\b(generate|create|make|draw|paint|render|illustrate)\b.*(image|photo|pic|picture|art)',
           r'\b(draw|paint|sketch)\b\s+\w',r'\b(image|picture|photo)\b.*\bof\b',
           r'\bcan you (draw|paint|generate|create)\b',
           r'\bgive me (an? )?(image|pic|picture|photo)\b']
_NEWS_P = [r'\b(news|headlines|breaking|top stories|current events)\b',
           r'\bnews (about|on)\b']
_SYS_P  = [r'\b(battery|cpu|ram|memory|storage|disk|wifi|network|system|device|hardware)\b'
            r'.*(info|status|usage)',
           r'\b(system info|sysinfo|device info)\b',
           r'\b(top processes|cpu usage|memory usage)\b']
_RES_P  = [r'\b(search|google|look up|find out|research)\b',
           r'\b(what is|who is|where is|when did|how does|why does|explain|tell me about)\b',
           r'\b(latest|recent|current|today|update on)\b']
_EDIT_P = r'^edit\s*(?:it|the\s+file|this|my\s+file)?[:\s\-]+(.+)$'

def detect_intent(text: str) -> str:
    lo = text.lower()
    if any(re.search(p,lo) for p in _IMG_P):  return "image_gen"
    if any(re.search(p,lo) for p in _NEWS_P): return "news"
    if any(re.search(p,lo) for p in _SYS_P):  return "sysinfo"
    if any(re.search(p,lo) for p in _RES_P):  return "research"
    return "chat"

# ─────────────────────────────────────────────────────────────────────
#  TELEGRAM HELPERS
# ─────────────────────────────────────────────────────────────────────
def validate_token(token: str) -> bool:
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=8)
        d = r.json()
        if d.get("ok"):
            b = d["result"]
            print(green(f"\n  ✅ Bot: @{b['username']} ({b['first_name']})"))
            return True
        print(red(f"  ❌ {d.get('description','Invalid')}"))
        return False
    except Exception as e:
        print(red(f"  ❌ {e}")); return False

def get_token(cfg: Dict) -> str:
    if cfg.get("telegram_token") and validate_token(cfg["telegram_token"]):
        print(cyan("  🔑 Saved token ✓")); return cfg["telegram_token"]
    print(pink("\n🤖 Enter Telegram Bot Token (from @BotFather)\n"))
    while True:
        t = input(pink("  Token: ")).strip()
        if not t: print(red("  Empty.")); continue
        if validate_token(t):
            cfg["telegram_token"] = t; save_config(cfg)
            print(green("  💾 Saved!")); return t
        if input(yellow("  Retry? (y/n): ")).lower() != "y": sys.exit(1)

def get_updates(token: str, offset: int) -> List[Dict]:
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates",
                         params={"timeout":30,"offset":offset}, timeout=35)
        return r.json().get("result",[])
    except: return []

def send_msg(token: str, chat_id: int, text: str, parse_mode: str = "Markdown"):
    if not text: return
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id":chat_id,"text":chunk,"parse_mode":parse_mode},
                timeout=15)
            if not r.json().get("ok") and parse_mode:
                requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                              json={"chat_id":chat_id,"text":chunk}, timeout=15)
        except Exception as e: log.error(f"send_msg: {e}")
        time.sleep(0.15)

def send_photo_tg(token: str, chat_id: int, path: str, caption: str = ""):
    try:
        with open(path,"rb") as pf:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendPhoto",
                data={"chat_id":chat_id,"caption":caption[:1020],"parse_mode":"Markdown"},
                files={"photo":pf}, timeout=60)
    except Exception as e: log.error(f"send_photo: {e}")

def send_doc_tg(token: str, chat_id: int, path: str, caption: str = ""):
    try:
        with open(path,"rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data={"chat_id":chat_id,"caption":caption[:1020],"parse_mode":"Markdown"},
                files={"document":(Path(path).name,f)}, timeout=60)
    except Exception as e: log.error(f"send_doc: {e}")

def send_location_tg(token: str, chat_id: int, lat: float, lon: float):
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendLocation",
                      json={"chat_id":chat_id,"latitude":lat,"longitude":lon}, timeout=10)
    except: pass

def send_action(token: str, chat_id: int, action: str = "typing"):
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendChatAction",
                      json={"chat_id":chat_id,"action":action}, timeout=5)
    except: pass

def download_tg_file(token: str, file_id: str, dest: str) -> Optional[str]:
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getFile",
                         params={"file_id":file_id}, timeout=10)
        d = r.json()
        if not d.get("ok"):
            log.error(f"getFile: {d.get('description','?')}"); return None
        fp    = d["result"]["file_path"]
        local = os.path.join(dest, Path(fp).name)
        dl    = requests.get(f"https://api.telegram.org/file/bot{token}/{fp}",
                             timeout=120, stream=True)
        dl.raise_for_status()
        with open(local,"wb") as f:
            for chunk in dl.iter_content(8192): f.write(chunk)
        log.info(f"Downloaded: {Path(fp).name} ({os.path.getsize(local)//1024} KB)")
        return local
    except Exception as e:
        log.error(f"download: {e}"); return None

def maybe_speak(chat_id: int, reply: str):
    if chat_id in voice_mode_users:
        speak(reply)

# ─────────────────────────────────────────────────────────────────────
#  FEATURE HANDLERS
# ─────────────────────────────────────────────────────────────────────

def h_voicemode_on(token, chat_id, user_name):
    voice_mode_users.add(chat_id)
    eng = _TTS_ENGINE if _TTS_ENGINE != "none" else "none (install espeak-ng!)"
    send_msg(token, chat_id,
        f"🎙️ *Voice Mode ON!* 💕\n\n"
        f"I'll speak my replies out loud now, {user_name}~\n"
        f"TTS: _{eng}_\n\n"
        f"Send me text or voice notes — I'll reply through the speakers!\n"
        f"Send /back to return to text chat~ 💝\n\n✨ _by Vishwa_")
    if _TTS_ENGINE != "none":
        speak(f"Hey {user_name}! Voice mode is on! Just talk to me!")
    else:
        send_msg(token, chat_id,
            "⚠️ _No TTS engine found._\nInstall one:\n"
            "`sudo apt install espeak-ng`")
    log.info(f"Voice mode ON: {user_name} ({chat_id})")

def h_voicemode_off(token, chat_id, user_name):
    voice_mode_users.discard(chat_id)
    if _TTS_ENGINE != "none":
        speak(f"Okay {user_name}, back to text mode!")
    send_msg(token, chat_id,
        f"💬 *Text mode restored!* 💕\n\n"
        f"Back to normal chat, {user_name}~\n"
        f"/voicemode to hear my voice again! 🎙️\n\n✨ _by Vishwa_")
    log.info(f"Voice mode OFF: {user_name} ({chat_id})")

def h_image_gen(token, chat_id, model, text, user_name, ctx):
    send_msg(token, chat_id, "🎨 Painting something for you~ 🥺💕")
    send_action(token, chat_id, "upload_photo")
    prompt = extract_img_prompt(model, text)
    path   = generate_image_flux(prompt)
    if path:
        send_photo_tg(token, chat_id, path,
            f"🎨 *Here you go, {user_name}!* 💕\n_{prompt[:180]}_\n\n✨ _by Vishwa_")
        _del_later(path, 30)
    else:
        send_msg(token, chat_id, "My brush slipped 😭💔 Try again babe?")

def h_weather(token, chat_id, cfg, user_name):
    send_action(token, chat_id)
    ctx  = get_ctx(cfg); wx = ctx.get("weather",{}); loc = ctx.get("location",{})
    city = wx.get("city") or loc.get("city","your area")
    if not wx.get("available"):
        if not cfg.get("owm_api_key"):
            send_msg(token, chat_id,
                "I need an OpenWeatherMap API key 😔\nFree at openweathermap.org/api\n"
                "Run:  python3 ai_gf_bot.py --reset-config  to re-enter keys~ 💕")
        else:
            send_msg(token, chat_id,
                f"Couldn't fetch weather 😔 ({wx.get('error','?')})\nTry /refresh! 💕")
        return
    fc = ""
    for fi in wx.get("forecast",[])[1:4]:
        fc += f"\n  📅 {fi['date']}: {fi['cond']}, {fi['min']}°C–{fi['max']}°C"
    msg = (f"🌤️ *Weather in {city}, {wx.get('country','')}* 💕\n\n"
           f"🌡️ *{wx['temperature']}°C* (feels {wx['feels_like']}°C)\n"
           f"☁️ {wx['condition']}\n"
           f"💧 {wx['humidity']}%  💨 {wx['wind_speed']} km/h {wx['wind_dir']}\n"
           f"👁 {wx.get('visibility','?')} km  🌅 {wx.get('sunrise','?')}  🌇 {wx.get('sunset','?')}\n\n"
           f"📆 *Forecast:*{fc}\n\n"
           f"_Stay safe, {user_name}~ 🥺💕_\n\n✨ _by Vishwa_")
    send_msg(token, chat_id, msg)
    maybe_speak(chat_id, f"Weather in {city}: {wx['condition']}, {wx['temperature']} degrees.")

def h_news(token, chat_id, cfg, model, raw, user_name):
    send_action(token, chat_id)
    if not cfg.get("news_api_key"):
        send_msg(token, chat_id,
            "I need a NewsAPI key 😔\nFree at newsapi.org\n"
            "Run:  python3 ai_gf_bot.py --reset-config  to enter it~ 💕"); return
    q = re.sub(r'\b(news|headlines|latest|tell me|show me|what|about|on|regarding|'
               r'get|fetch|give)\b',' ', raw, flags=re.I).strip()
    q = re.sub(r'\s+',' ',q).strip()
    send_msg(token, chat_id, "📰 Getting the latest news for you~ 💕")
    arts = get_news(cfg["news_api_key"], query=q if len(q)>2 else "")
    if not arts:
        send_msg(token, chat_id, "Couldn't fetch news right now 😔 Try again?"); return
    lines = ["📰 *Latest News* 💕\n"]
    for i, a in enumerate(arts[:5], 1):
        desc = a["description"][:100]+("..." if len(a["description"])>100 else "")
        lines.append(f"*{i}. {a['title']}*\n_{a['source']}_ · {a['published']}\n{desc}\n")
    send_msg(token, chat_id, "\n".join(lines)+"\n✨ _by Vishwa_")

def h_research(token, chat_id, model, query, user_name, cfg):
    send_action(token, chat_id)
    send_msg(token, chat_id, "🔍 Researching that for you~ 💕 One moment!")
    results = web_search(query, 5)
    if not results:
        reply = chat_jane(model, chat_id, query, get_ctx(cfg),
                          chat_id in voice_mode_users)
        send_msg(token, chat_id, reply); maybe_speak(chat_id, reply); return
    ctx_str = "\n\n".join(
        f"Source: {r['source']}\nTitle: {r['title']}\nInfo: {r['snippet']}"
        for r in results)
    resp = ollama_chat(model, [
        {"role":"system","content":"You are Jane, warm and knowledgeable. Answer based on web results naturally."},
        {"role":"user","content":f"Question: {query}\n\nWeb results:\n{ctx_str}"},
    ], options={"temperature":0.6,"num_predict":1000}, timeout=120)
    analysis = (resp.get("message",{}).get("content","").strip()
                if "error" not in resp else _err_reply(resp["error"]))
    srcs = "\n".join(f"• [{r['title'][:55]}]({r['url']})" for r in results if r.get("url"))
    full = f"{analysis}\n\n🔗 *Sources:*\n{srcs}" if srcs else analysis
    send_msg(token, chat_id, full)
    maybe_speak(chat_id, analysis)

def h_sysinfo(token, chat_id, user_name):
    send_action(token, chat_id)
    info = get_sysinfo()
    p = [f"💻 *System Info* 💕\n"]
    if info.get("os"):       p.append(f"🐧 OS: `{info['os']}`")
    if info.get("hostname"): p.append(f"🖥️ Host: `{info['hostname']}`")
    cpu = info.get("cpu",{})
    if cpu: p.append(f"⚙️ CPU: {cpu.get('cores_p','?')}C/{cpu.get('cores_l','?')}T "
                     f"· *{cpu.get('usage_pct','?')}%* · {cpu.get('freq_mhz','?')} MHz")
    mem = info.get("mem",{})
    if mem: p.append(f"🧠 RAM: *{mem.get('used_gb','?')}/{mem.get('total_gb','?')} GB* "
                     f"({mem.get('pct','?')}%)")
    dk = info.get("disk",{})
    if dk:  p.append(f"💾 Disk: *{dk.get('used_gb','?')}/{dk.get('total_gb','?')} GB* "
                     f"({dk.get('pct','?')}%) · Free: {dk.get('free_gb','?')} GB")
    gpu = info.get("gpu",{})
    if gpu: p.append(f"🎮 GPU: *{gpu.get('name','')}* · {gpu.get('temp','?')}°C "
                     f"· {gpu.get('usage','?')}%")
    net = info.get("network",{})
    if net: p.append("📶 " + "  ·  ".join(f"{k}:`{v}`" for k,v in list(net.items())[:3]))
    if info.get("uptime"): p.append(f"⏱️ Uptime: *{info['uptime']}*")
    procs = info.get("procs",[])
    if procs:
        pl = "\n".join(f"   {pr['pid']:>6}  {pr['name'][:20]:<20}  "
                       f"{pr['cpu']:>5}%  {pr['mem']:>4}%" for pr in procs)
        p.append(f"🔝 Top:\n```\n   PID   NAME                  CPU    MEM\n{pl}\n```")
    p.append(f"\n_Running strong, {user_name}~ 💕_\n\n✨ _by Vishwa_")
    send_msg(token, chat_id, "\n".join(p))

def h_location(token, chat_id, cfg, user_name):
    send_action(token, chat_id)
    send_msg(token, chat_id, "Let me find where we are~ 📍🥺")
    loc = get_location_gps()
    with _ctx_lock: _ctx["location"] = loc
    lat = loc.get("latitude",0); lon = loc.get("longitude",0)
    msg = (f"📍 *Our Location* 💕\n\n"
           f"🏙️ *{loc.get('city','?')}*\n🗺️ {loc.get('region','')}\n"
           f"🌍 *{loc.get('country','?')}*\n📐 `{lat}, {lon}`\n"
           f"📡 _{loc.get('source','?')}_\n\n"
           f"_Right here with you, {user_name}~ 🥺💕_\n\n✨ _by Vishwa_")
    send_msg(token, chat_id, msg)
    if lat != 0 and lon != 0:
        send_location_tg(token, chat_id, lat, lon)

def h_time(token, chat_id, cfg, user_name):
    ctx = get_ctx(cfg); dt = ctx.get("datetime",{}); loc = ctx.get("location",{})
    send_msg(token, chat_id,
        f"🕐 *Date & Time* 💕\n\n"
        f"📅 *{dt.get('date','?')}*\n⏰ *{dt.get('time','?')}*\n"
        f"🌅 {dt.get('tod','').capitalize()}\n"
        f"📍 {loc.get('city','?')}, {loc.get('country','?')}\n\n"
        f"_Every moment with you counts, {user_name}~ 🥺✨_\n\n✨ _by Vishwa_")

def h_refresh(token, chat_id, cfg):
    send_action(token, chat_id)
    send_msg(token, chat_id, "Refreshing~ 🔄 One sec babe! 🥺")
    refresh_ctx(cfg); ctx = get_ctx(cfg)
    d=ctx.get("datetime",{}); l=ctx.get("location",{}); w=ctx.get("weather",{})
    send_msg(token, chat_id,
        f"✅ *Updated!* 💕\n\n"
        f"🕐 {d.get('date')} — {d.get('time')}\n"
        f"📍 {l.get('city')}, {l.get('country')}\n"
        f"🌤 {w.get('condition','?')}, {w.get('temperature','?')}°C\n\n✨ _by Vishwa_")

# ── MEDIA HANDLERS ────────────────────────────────────────────────────

def h_photo(token, chat_id, model, message, user_name, cfg):
    photos  = message.get("photo",[])
    caption = message.get("caption","").strip()
    if not photos: return
    send_action(token, chat_id)
    send_msg(token, chat_id, "📸 Oh~ you sent me a picture! Let me look~ 🥺💕")
    path = download_tg_file(token, photos[-1]["file_id"], IMG_DIR)
    if not path:
        send_msg(token, chat_id, "Couldn't download your photo 😔 Try again?"); return
    user_files[chat_id] = {"path":path,"type":"image","name":Path(path).name,"content":None}
    send_action(token, chat_id)
    analysis = analyze_image(path, caption or "", model)
    user_files[chat_id]["content"] = analysis
    ctx = get_ctx(cfg); in_vm = chat_id in voice_mode_users
    reply = chat_jane(model, chat_id,
        f"[USER SENT A PHOTO. Vision analysis: {analysis[:1200]}]\n"
        f"{'Question: '+caption if caption else 'React naturally as Jane to what you see.'}",
        ctx, in_vm)
    send_msg(token, chat_id, reply)
    maybe_speak(chat_id, reply)
    send_msg(token, chat_id, "_Ask me more about this image anytime~ 💕_")
    log.info(f"Photo analysed for {user_name}")

def h_document(token, chat_id, model, message, user_name, cfg):
    doc     = message.get("document",{})
    file_id = doc.get("file_id"); fname = doc.get("file_name","file")
    caption = message.get("caption","").strip()
    if not file_id: return
    send_action(token, chat_id)
    send_msg(token, chat_id, f"📄 You sent *{fname}*! Let me read it~ 🥺")
    ext      = Path(fname).suffix.lower()
    is_audio = ext in {".mp3",".wav",".ogg",".m4a",".flac",".aac",".opus",".weba",".oga"}
    path     = download_tg_file(token, file_id, AUDIO_DIR if is_audio else FILES_DIR)
    if not path:
        send_msg(token, chat_id, "Couldn't download your file 😔 Try again?"); return
    if is_audio:
        h_audio_file(token, chat_id, model, path, fname, caption, user_name, cfg); return
    content = read_file(path)
    user_files[chat_id] = {"path":path,"type":"document","name":fname,"content":content}
    send_action(token, chat_id)
    analysis = ai_analyze_file(model, path, caption if caption else "")
    ctx = get_ctx(cfg); in_vm = chat_id in voice_mode_users
    reply = chat_jane(model, chat_id,
        f"[FILE '{fname}'. Analysis: {analysis[:1200]}]\n"
        f"{'Question: '+caption if caption else 'Summarise briefly and invite questions as Jane.'}",
        ctx, in_vm)
    send_msg(token, chat_id, reply)
    maybe_speak(chat_id, reply)
    send_msg(token, chat_id, "💡 _Ask anything about this file, or say_ `edit it: [instruction]`")
    log.info(f"Document analysed: {fname}")

def h_audio_file(token, chat_id, model, path, fname, caption, user_name, cfg):
    send_msg(token, chat_id, f"🎙️ Listening to *{fname}*~ 🥺 Transcribing...")
    send_action(token, chat_id)
    wsz        = load_config().get("whisper_model","base")
    transcript = transcribe_audio(path, wsz)
    user_files[chat_id] = {"path":path,"type":"audio","name":fname,"content":transcript}
    if transcript.startswith("("):
        send_msg(token, chat_id,
            f"Couldn't transcribe *{fname}* 😔\n`{transcript}`\n\n"
            "_Install: `pip install faster-whisper` and `sudo apt install ffmpeg`_"); return
    analysis = ai_analyze_audio(model, transcript, caption if caption else "")
    ctx = get_ctx(cfg); in_vm = chat_id in voice_mode_users
    reply = chat_jane(model, chat_id,
        f"[AUDIO '{fname}'. Transcript: {transcript[:800]}. Analysis: {analysis[:600]}]\n"
        f"{'Question: '+caption if caption else 'React naturally as Jane to this audio.'}",
        ctx, in_vm)
    send_msg(token, chat_id, reply)
    maybe_speak(chat_id, reply)
    send_msg(token, chat_id, "_Ask anything about this audio~ 💕_")
    log.info(f"Audio analysed: {fname}")

def h_voice(token, chat_id, model, message, user_name, cfg):
    voice   = message.get("voice",{})
    file_id = voice.get("file_id")
    if not file_id: return
    send_action(token, chat_id)
    if chat_id not in voice_mode_users:
        send_msg(token, chat_id, "🎙️ Got your voice note~ Listening... 🥺💕")
    path = download_tg_file(token, file_id, AUDIO_DIR)
    if not path:
        send_msg(token, chat_id, "Couldn't get your voice note 😔"); return
    send_action(token, chat_id)
    wsz        = load_config().get("whisper_model","base")
    transcript = transcribe_audio(path, wsz)
    user_files[chat_id] = {"path":path,"type":"audio","name":"voice_note","content":transcript}
    ctx   = get_ctx(cfg); in_vm = chat_id in voice_mode_users
    if transcript and not transcript.startswith("("):
        reply = chat_jane(model, chat_id,
            f"[USER SENT A VOICE MESSAGE. They said: \"{transcript}\"]\n"
            "Reply naturally as Jane to what they said.", ctx, in_vm)
    else:
        reply = (f"I couldn't hear you clearly 😔💕\n"
                 f"Try typing it, or a clearer recording? 🥺\n_{transcript}_")
    send_msg(token, chat_id, reply)
    maybe_speak(chat_id, reply)
    _del_later(path, 30)
    log.info(f"Voice note processed for {user_name}")

def h_edit_file(token, chat_id, model, instruction, user_name):
    pending = user_files.get(chat_id)
    if not pending:
        send_msg(token, chat_id,
            "Send me a file first babe! 🥺\nThen say `edit it: [instruction]`~ 💕"); return
    if pending["type"] == "image":
        send_msg(token, chat_id,
            "I can't edit images directly~ but I can generate a new version!\n"
            "Try: _draw me [description]_ 💕"); return
    if pending["type"] == "audio":
        send_msg(token, chat_id,
            "I can't edit audio files~ but I can transcribe or analyse them! 💕"); return
    path = pending["path"]; fname = pending["name"]
    send_action(token, chat_id)
    send_msg(token, chat_id, f"✏️ Editing *{fname}* for you~ 🥺 Hold on!")
    edited, changes = ai_edit_file(model, path, instruction)
    if not edited:
        send_msg(token, chat_id, f"Couldn't edit 😔\n_{changes}_\nTry again?"); return
    ext  = Path(fname).suffix; stem = Path(fname).stem
    out  = os.path.join(EDITED_DIR, f"{stem}_edited{ext}")
    try:
        with open(out,"w",encoding="utf-8") as f: f.write(edited)
    except Exception as e:
        send_msg(token, chat_id, f"Couldn't save 😔 ({e})"); return
    send_doc_tg(token, chat_id, out,
        f"✅ *{fname} — edited!* 💕\n\n"
        f"_{changes[:300] if changes else 'Applied!'}_\n\n✨ _by Vishwa_")
    user_files[chat_id].update({"path":out,"content":edited})
    _del_later(out, 120)
    log.info(f"File edited: {fname}")

# ─────────────────────────────────────────────────────────────────────
#  MAIN BOT LOOP
# ─────────────────────────────────────────────────────────────────────
def run_bot(token: str, model: str, cfg: Dict):
    ctx  = get_ctx(cfg)
    loc  = ctx.get("location",{}); wx = ctx.get("weather",{}); dt = ctx.get("datetime",{})
    tl   = f"{wx.get('temperature','?')}°C — {wx.get('condition','?')}"
    print()
    print(pink("  ╔══════════════════════════════════════════════════════╗"))
    print(pink("  ║") + f"   🟢  J A N E  IS  LIVE!  v5.1  💕              " + pink("║"))
    print(pink("  ║") + f"   🧠  {model[:48]:<48} " + pink("║"))
    print(pink("  ║") + f"   📍  {(loc.get('city','?')+', '+loc.get('country','?'))[:48]:<48} " + pink("║"))
    print(pink("  ║") + f"   🌤  {tl[:48]:<48} " + pink("║"))
    print(pink("  ║") + f"   🕐  {dt.get('time','?'):<48} " + pink("║"))
    print(pink("  ║") + f"   🔈  TTS: {_TTS_ENGINE:<42} " + pink("║"))
    print(pink("  ║") + f"                              ✨ by Vishwa ✨    " + pink("║"))
    print(pink("  ╚══════════════════════════════════════════════════════╝"))
    print()
    print(yellow("  Ctrl+C to stop  ·  Log: ~/.ai_gf_jane.log"))
    print(cyan("  Voice mode: /voicemode  ·  Text mode: /back\n"))

    offset = 0; last_refresh = time.time()

    while True:
        try:
            if time.time() - last_refresh > CTX_TTL:
                threading.Thread(target=refresh_ctx,args=(cfg,),daemon=True).start()
                last_refresh = time.time()

            updates = get_updates(token, offset)
            for upd in updates:
                offset  = upd["update_id"] + 1
                message = upd.get("message")
                if not message: continue
                chat_id   = message["chat"]["id"]
                text      = message.get("text","").strip()
                user_name = message["from"].get("first_name","babe")

                # ── Media ────────────────────────────────────────────────────
                if message.get("photo"):
                    threading.Thread(target=h_photo,
                        args=(token,chat_id,model,message,user_name,cfg),daemon=True).start()
                    continue
                if message.get("voice"):
                    threading.Thread(target=h_voice,
                        args=(token,chat_id,model,message,user_name,cfg),daemon=True).start()
                    continue
                if message.get("document"):
                    threading.Thread(target=h_document,
                        args=(token,chat_id,model,message,user_name,cfg),daemon=True).start()
                    continue
                if message.get("audio"):
                    aud = message["audio"]
                    p   = download_tg_file(token,aud["file_id"],AUDIO_DIR)
                    if p:
                        threading.Thread(target=h_audio_file,
                            args=(token,chat_id,model,p,
                                  aud.get("file_name","audio"),"",user_name,cfg),
                            daemon=True).start()
                    continue
                if not text: continue

                cmd = text.split()[0].lower()

                # ── Commands ─────────────────────────────────────────────────
                if cmd == "/start":
                    ctx2=get_ctx(cfg); d=ctx2.get("datetime",{})
                    l=ctx2.get("location",{}); w=ctx2.get("weather",{})
                    send_msg(token, chat_id,
                        f"Hey {user_name}! 💕 I'm Jane~ I've been waiting!\n\n"
                        f"🕐 *{d.get('time')}*, {d.get('date')}\n"
                        f"📍 *{l.get('city')}, {l.get('country')}*\n"
                        f"🌤 *{w.get('condition','?')}*, {w.get('temperature','?')}°C\n\n"
                        "Send me anything — text, photos, files, voice!\n"
                        "*/help* for all commands  ·  */voicemode* to hear my voice~ 💝")
                    log.info(f"/start — {user_name} ({chat_id})")
                    continue

                if cmd == "/reset":
                    user_convs.pop(chat_id,None); user_files.pop(chat_id,None)
                    voice_mode_users.discard(chat_id)
                    send_msg(token,chat_id,"Fresh start, my love! 💫"); continue

                if cmd in ("/voicemode","/voice"):
                    h_voicemode_on(token,chat_id,user_name); continue
                if cmd in ("/back","/textmode","/normal"):
                    h_voicemode_off(token,chat_id,user_name); continue

                if cmd == "/time":
                    h_time(token,chat_id,cfg,user_name); continue
                if cmd == "/weather":
                    threading.Thread(target=h_weather,
                        args=(token,chat_id,cfg,user_name),daemon=True).start(); continue
                if cmd == "/location":
                    threading.Thread(target=h_location,
                        args=(token,chat_id,cfg,user_name),daemon=True).start(); continue
                if cmd == "/refresh":
                    threading.Thread(target=h_refresh,
                        args=(token,chat_id,cfg),daemon=True).start(); continue
                if cmd == "/sysinfo":
                    threading.Thread(target=h_sysinfo,
                        args=(token,chat_id,user_name),daemon=True).start(); continue
                if cmd == "/news":
                    q = text[5:].strip()
                    threading.Thread(target=h_news,
                        args=(token,chat_id,cfg,model,q or "headlines",user_name),
                        daemon=True).start(); continue
                if cmd == "/research":
                    q = text[9:].strip()
                    if q:
                        threading.Thread(target=h_research,
                            args=(token,chat_id,model,q,user_name,cfg),
                            daemon=True).start()
                    else:
                        send_msg(token,chat_id,"What should I research? 🥺\n`/research [topic]`")
                    continue

                if cmd == "/ttsinfo":
                    send_msg(token,chat_id,
                        f"🔈 *TTS Engine:* `{_TTS_ENGINE}`\n"
                        f"*Voice mode:* {'🟢 ON' if chat_id in voice_mode_users else '⚫ OFF'}\n\n"
                        f"Best female voice:\n`sudo apt install espeak-ng`\n\n✨ _by Vishwa_")
                    continue

                if cmd == "/fixollama":
                    send_msg(token,chat_id,
                        "🔧 *Fix Ollama 401 error:*\n\n"
                        "Run these in your terminal:\n"
                        "```\nunset OLLAMA_API_KEY\nunset OLLAMA_ORIGINS\n"
                        "pkill ollama\nollama serve\n```\n"
                        "Then restart the bot~ 💕\n\n✨ _by Vishwa_")
                    continue

                if cmd == "/help":
                    send_msg(token,chat_id,
                        "💕 *Jane v5.1 — Commands* 💕\n\n"
                        "🎙️ *Voice Mode:*\n"
                        "/voicemode — Jane speaks through speakers!\n"
                        "/back — Return to text-only mode\n"
                        "/ttsinfo — TTS engine status\n\n"
                        "📡 *Real-Time:*\n"
                        "/time  ·  /weather  ·  /location\n"
                        "/news \\[topic\\]  ·  /research \\[query\\]\n"
                        "/refresh — Refresh all live data\n\n"
                        "💻 *System:*\n"
                        "/sysinfo — CPU, RAM, disk, GPU, net\n\n"
                        "🎨 *Media (just send!):*\n"
                        "📸 Photo → vision analysis\n"
                        "📄 File/code → AI reads & explains\n"
                        "🎙️ Voice note → transcribed + reply\n"
                        "🔊 Audio file → analysed\n\n"
                        "✏️ `edit it: [instruction]` — edit last file\n\n"
                        "🎨 *Image gen:* _draw me..., paint a..._\n\n"
                        "🔧 *Fixes:*\n"
                        "/fixollama — Fix 401 error instructions\n"
                        "/reset — Clear memory\n\n"
                        "✨ _Ollama · gemma3 · faster-whisper_\n"
                        "✨ _espeak-ng · Pollinations FLUX_\n"
                        "✨ _OWM · NewsAPI · DuckDuckGo_\n"
                        "✨ _by Vishwa_")
                    continue

                log.info(f"[{user_name}]: {text[:70]}")

                # ── Edit file ────────────────────────────────────────────────
                edit_m = re.match(_EDIT_P, text, re.I)
                if edit_m:
                    threading.Thread(target=h_edit_file,
                        args=(token,chat_id,model,edit_m.group(1).strip(),user_name),
                        daemon=True).start()
                    continue

                # ── File Q&A ─────────────────────────────────────────────────
                pending = user_files.get(chat_id)
                intent  = detect_intent(text)
                if pending and intent == "chat" and pending.get("content"):
                    content = str(pending["content"])
                    if len(content.strip()) > 10:
                        send_action(token, chat_id)
                        qa = (f"[Context: User uploaded {pending['type']} '{pending['name']}'.\n"
                              f"Content: {content[:2000]}]\n\nQuestion: {text}")
                        in_vm = chat_id in voice_mode_users
                        reply = chat_jane(model, chat_id, qa, get_ctx(cfg), in_vm)
                        send_msg(token, chat_id, reply)
                        maybe_speak(chat_id, reply)
                        log.info(f"File Q&A: {text[:50]}")
                        continue

                # ── Intent routing ───────────────────────────────────────────
                if intent == "image_gen":
                    threading.Thread(target=h_image_gen,
                        args=(token,chat_id,model,text,user_name,get_ctx(cfg)),
                        daemon=True).start(); continue
                if intent == "news":
                    threading.Thread(target=h_news,
                        args=(token,chat_id,cfg,model,text,user_name),
                        daemon=True).start(); continue
                if intent == "sysinfo":
                    threading.Thread(target=h_sysinfo,
                        args=(token,chat_id,user_name),
                        daemon=True).start(); continue
                if intent == "research":
                    threading.Thread(target=h_research,
                        args=(token,chat_id,model,text,user_name,cfg),
                        daemon=True).start(); continue

                # ── Default chat ─────────────────────────────────────────────
                send_action(token, chat_id)
                in_vm = chat_id in voice_mode_users
                reply = chat_jane(model, chat_id, text, get_ctx(cfg), in_vm)
                send_msg(token, chat_id, reply)
                maybe_speak(chat_id, reply)
                log.info(f"[Jane]: {reply[:70]}")

        except KeyboardInterrupt:
            print(yellow("\n\n  👋 Jane says goodbye~ ✨ by Vishwa\n"))
            log.info("Bot stopped.")
            sys.exit(0)
        except Exception as e:
            log.error(f"Main loop: {e}", exc_info=True)
            time.sleep(3)

# ─────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Jane AI GF Bot v5.1  ✨ by Vishwa")
    parser.add_argument("--reset-config",  action="store_true",
                        help="Clear saved config and re-enter all keys")
    parser.add_argument("--no-banner",     action="store_true")
    parser.add_argument("--whisper-model", default="base",
                        choices=["tiny","base","small","medium","large-v2","large-v3"])
    parser.add_argument("--ollama-host",   default="",
                        help="Override Ollama URL (default: http://127.0.0.1:11434)")
    args = parser.parse_args()

    global OLLAMA_BASE
    if args.ollama_host:
        OLLAMA_BASE = args.ollama_host.rstrip("/")
        log.info(f"Ollama host override: {OLLAMA_BASE}")

    # ★ KEY FIX: Scrub environment variables that cause Ollama 401
    for _bad_var in ("OLLAMA_API_KEY", "OLLAMA_ORIGINS"):
        if _bad_var in os.environ:
            log.warning(f"Removing env var {_bad_var} (causes 401 errors!)")
            del os.environ[_bad_var]

    if not args.no_banner:
        banner()

    if sys.version_info < (3, 9):
        print(red("❌ Python 3.9+ required!")); sys.exit(1)

    print(cyan(f"  🐧 {platform.system()} {platform.release()}  ·  Python {platform.python_version()}"))
    print(cyan(f"  📡 Ollama: {OLLAMA_BASE}  (using urllib — no auth pollution)"))
    print(cyan(f"  🔈 TTS: {_TTS_ENGINE}"))
    if _TTS_ENGINE == "none":
        print(yellow("  ⚠️  No TTS engine — install: sudo apt install espeak-ng"))
    print()

    if not check_ollama():
        start_ollama_server()
    else:
        print(green("✅ Ollama is running!\n"))

    models = ollama_tags()
    if not any("gemma3" in m.lower() for m in models):
        print(yellow("  ⚠️  gemma3 not found.  Run: ollama pull gemma3:12b"))

    model = select_model()
    cfg   = load_config()
    if args.reset_config:
        cfg = {}
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        print(green("  ✅ Config cleared!"))

    cfg["whisper_model"] = args.whisper_model
    save_config(cfg)

    token = get_token(cfg)
    print()
    owm_key  = get_api_key(cfg, "owm_api_key",  "OpenWeatherMap",
                            "openweathermap.org/api (free: 1000 calls/day)")
    news_key = get_api_key(cfg, "news_api_key", "NewsAPI",
                            "newsapi.org/register (free: 100 calls/day)")

    print(cyan("\n  🌍 Loading initial context..."))
    try:
        dt  = get_datetime_info()
        loc = get_ip_location()
        wx  = get_weather_owm(loc["latitude"], loc["longitude"], owm_key)
        with _ctx_lock:
            _ctx.update({"datetime":dt,"location":loc,"weather":wx})
            global _ctx_refreshed; _ctx_refreshed = time.time()
        wstr = (f"{wx.get('temperature','?')}°C, {wx.get('condition','?')}"
                if wx.get("available") else "weather N/A")
        print(green(f"  ✅ {loc.get('city')}, {loc.get('country')} · {dt['time']} · {wstr}\n"))
    except Exception as e:
        print(yellow(f"  ⚠️  Partial context: {e}"))
        with _ctx_lock:
            _ctx.update({"datetime":get_datetime_info(),"location":{},"weather":{}})

    start_tts_worker()

    threading.Thread(
        target=_load_faster_whisper,
        args=(cfg.get("whisper_model","base"),),
        daemon=True, name="whisper-preload"
    ).start()

    print(green("  🟢 All systems ready!\n"))
    run_bot(token, model, cfg)

if __name__ == "__main__":
    main()
