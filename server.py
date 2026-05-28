"""
Liggo Analyzer - Servidor Flask
Uso local: python liggo_server.py
Hosting gratuito: Render / PythonAnywhere
"""
import os, json, time, base64, threading, re, sys
from flask import Flask, request, send_from_directory
import requests as http

app = Flask(__name__, static_folder='static', static_url_path='')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SUPABASE_URL = "https://eptdvpvwspuykrcnxcqt.supabase.co"
ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVwdGR2cHZ3c3B1eWtyY254Y3F0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY0NjUxODMsImV4cCI6MjA3MjA0MTE4M30.71VGYm_StonujeP5W6BWqSu4ivrEQ00-8fyWOvxbmLM"
USER_ID = "8b28a824-1483-4028-aa48-32aa810704aa"
COOKIE_FILE = os.path.join(SCRIPT_DIR, "cookie_data.json")

# Estado global
current_access_token = ""
current_refresh_token = ""
current_cookie = ""
cookie_part0 = ""
cookie_part1 = ""
ready = False

def load_cookie():
    global current_refresh_token, cookie_part0, cookie_part1
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE) as f:
                data = json.load(f)
                current_refresh_token = data.get("refresh_token", "")
                cookie_part0 = data.get("cookie_part0", "")
                cookie_part1 = data.get("cookie_part1", "")
                if cookie_part0 and cookie_part1:
                    global current_cookie
                    current_cookie = "sb-eptdvpvwspuykrcnxcqt-auth-token.0=" + cookie_part0 + "; sb-eptdvpvwspuykrcnxcqt-auth-token.1=" + cookie_part1
                return True
        except: pass
    return False

def save_cookie():
    with open(COOKIE_FILE, "w") as f:
        json.dump({"refresh_token": current_refresh_token, "cookie_part0": cookie_part0, "cookie_part1": cookie_part1}, f)

def extract_refresh_from_full_cookie(raw_cookie):
    """Extrae el refresh_token del cookie base64 completo"""
    try:
        # Buscar el bloque base64: base64-XXXX
        match = re.search(r'base64-([A-Za-z0-9+/=_.-]+)', raw_cookie)
        if match:
            b64 = match.group(1)
            padded = b64 + '=' * (4 - len(b64) % 4) if len(b64) % 4 else b64
            decoded = base64.urlsafe_b64decode(padded).decode('utf-8')
            data = json.loads(decoded)
            rt = data.get("refresh_token", "")
            # Tambien puede estar anidado
            if not rt and "user" in data and isinstance(data["user"], dict):
                rt = data["user"].get("refresh_token", "")
            return rt
    except: pass
    return ""

def refresh_session():
    """Renovar el access token de Supabase usando refresh_token"""
    global current_access_token, current_cookie, current_refresh_token, ready, cookie_part0, cookie_part1
    if not current_refresh_token:
        ready = False
        return False
    try:
        headers = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}", "Content-Type": "application/json"}
        body = {"refresh_token": current_refresh_token}
        r = http.post(f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token", headers=headers, json=body, timeout=10)
        if r.status_code == 200:
            data = r.json()
            current_access_token = data.get("access_token", "")
            current_refresh_token = data.get("refresh_token", current_refresh_token)

            # Construir el session JSON como lo hace el browser
            session_data = {
                "access_token": current_access_token,
                "token_type": data.get("token_type", "bearer"),
                "expires_in": data.get("expires_in", 3600),
                "expires_at": data.get("expires_at", 0),
                "refresh_token": current_refresh_token,
                "user": data.get("user", {})
            }
            session_json = json.dumps(session_data, separators=(',', ':'))
            session_b64 = base64.b64encode(session_json.encode('utf-8')).decode('utf-8')
            mid = min(2050, len(session_b64) // 2)
            cookie_part0 = "base64-" + session_b64[:mid]
            cookie_part1 = session_b64[mid:]
            current_cookie = "sb-eptdvpvwspuykrcnxcqt-auth-token.0=" + cookie_part0 + "; sb-eptdvpvwspuykrcnxcqt-auth-token.1=" + cookie_part1

            save_cookie()
            ready = True
            print(f"[OK] Token renovado: {current_access_token[:30]}...")
            return True
        else:
            ready = False
            print(f"[ERROR] Refresh: {r.status_code} {r.text[:100]}")
            return False
    except Exception as e:
        ready = False
        print(f"[ERROR] Refresh: {e}")
        return False

def reset_counter():
    from datetime import datetime
    utc_date = datetime.utcnow().strftime("%Y-%m-%d")
    uri = f"{SUPABASE_URL}/rest/v1/usage_tracking?user_id=eq.{USER_ID}&date=eq.{utc_date}"
    headers = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}", "Content-Type": "application/json", "Prefer": "return=minimal"}
    try:
        http.patch(uri, headers=headers, json={"analyses_count": -999}, timeout=10)
    except: pass

# Cargar cookie guardada e iniciar sesion
if load_cookie():
    refresh_session()

# Loop de auto-refresh
def auto_refresh_loop():
    while True:
        time.sleep(3000)
        refresh_session()
threading.Thread(target=auto_refresh_loop, daemon=True).start()

HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>Liggo Analyzer</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#fafbfc;min-height:100vh;display:flex;justify-content:center;align-items:flex-start;padding:24px 16px}
.card{background:#fff;border-radius:20px;padding:28px 24px;width:100%;max-width:440px;box-shadow:0 2px 20px rgba(0,0,0,0.06),0 0 0 1px rgba(0,0,0,0.04)}
h1{font-size:20px;color:#1a1a2e;margin-bottom:2px}
.sub{font-size:13px;color:#8892a4;margin-bottom:24px}
label{display:block;font-size:12px;font-weight:600;color:#4a5568;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;margin-top:18px}
select,input[type=file]{width:100%;padding:12px 14px;border:1.5px solid #e8ecf1;border-radius:12px;font-size:14px;color:#2d3748;background:#f8f9fb;transition:border .2s,box-shadow .2s;appearance:none}
select{background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%238892a4' fill='none' stroke-width='1.5'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 14px center;padding-right:36px}
input[type=file]::file-selector-button{background:#e8ecf1;border:none;padding:6px 14px;border-radius:8px;font-size:13px;color:#4a5568;margin-right:10px;cursor:pointer;font-weight:500}
select:focus,input[type=file]:focus{outline:none;border-color:#8b9cf7;box-shadow:0 0 0 3px rgba(139,156,247,0.15)}
img.preview{max-width:100%;max-height:220px;margin-top:10px;border-radius:12px;display:none;border:1px solid #e8ecf1}
.btn{width:100%;padding:13px;background:#6366f1;color:#fff;border:none;border-radius:12px;font-size:15px;font-weight:600;cursor:pointer;margin-top:22px;transition:background .2s,transform .1s}
.btn:hover:not(:disabled){background:#4f46e5;transform:translateY(-1px)}
.btn:active:not(:disabled){transform:translateY(0)}
.btn:disabled{opacity:.55;cursor:not-allowed}
.result{margin-top:20px;padding:18px;background:#f8f9fb;border-radius:12px;display:none;border:1px solid #e8ecf1}
.result .resp{font-size:15px;color:#1a1a2e;line-height:1.5}
.result .meta{font-size:11px;color:#8892a4;margin-top:10px;padding-top:10px;border-top:1px solid #e8ecf1}
.error{color:#e53e3e}
.row{display:flex;gap:14px}
.row>div{flex:1}
.footer{text-align:center;font-size:10px;color:#c4cad4;margin-top:16px;line-height:1.6}
.spinner{display:none;width:20px;height:20px;border:2px solid #e8ecf1;border-top-color:#6366f1;border-radius:50%;animation:spin .6s linear infinite;margin:12px auto 0}
@keyframes spin{to{transform:rotate(360deg)}}
.config-box{background:#fef9ef;border:1.5px solid #f0dca0;border-radius:12px;padding:16px;margin-bottom:20px;display:none}
.config-box label{color:#8a6c00}
.config-box textarea{width:100%;padding:10px;border:1.5px solid #e8ecf1;border-radius:8px;font-size:12px;font-family:monospace;min-height:60px;margin:8px 0;resize:vertical}
.config-box .btn-small{padding:8px 16px;background:#6366f1;color:#fff;border:none;border-radius:8px;font-size:13px;cursor:pointer}
.config-box .btn-small:hover{background:#4f46e5}
.status-info{font-size:11px;text-align:center;margin-top:10px;color:#8892a4}
</style>
</head>
<body>
<div class="card">
  <h1>Liggo Analyzer</h1>
  <p class="sub">Sube un screenshot y Gemini 3.1 Flash Lite te sugiere respuestas</p>

  <div id="configBox" class="config-box">
    <label>Cookie de sesion</label>
    <p style="font-size:12px;color:#8a6c00;margin-bottom:6px">
      En tu PC: abre Liggo, F12 → Console, escribe <code style="background:#f0dca0;padding:1px 4px;border-radius:3px">document.cookie</code>, copia todo y pegalo aqui.
    </p>
    <textarea id="cookieInput" placeholder="Pega el cookie aqui..."></textarea>
    <button class="btn-small" id="saveCookieBtn">Guardar cookie</button>
  </div>

  <div id="mainContent">
    <div class="row">
      <div>
        <label>Tipo</label>
        <select id="type"><option>Chat</option><option>Historia</option></select>
      </div>
      <div>
        <label>Estilo</label>
        <select id="style"><option>gracioso</option><option>provocativo</option><option>coquetear</option><option>enamorar</option><option>epica</option></select>
      </div>
    </div>

    <label>Captura de pantalla</label>
    <input type="file" id="file" accept="image/*">
    <img id="preview" class="preview">

    <button class="btn" id="analyzeBtn">Analizar</button>
    <div class="spinner" id="spinner"></div>

    <div class="result" id="result">
      <div class="resp" id="response"></div>
      <div class="meta" id="meta"></div>
    </div>
  </div>

  <div class="footer" id="statusMsg">Conectando...</div>
</div>

<script>
const configBox=document.getElementById('configBox'),cookieInput=document.getElementById('cookieInput'),
saveBtn=document.getElementById('saveCookieBtn'),statusMsg=document.getElementById('statusMsg'),
fileInput=document.getElementById('file'),preview=document.getElementById('preview'),
btn=document.getElementById('analyzeBtn'),spinner=document.getElementById('spinner'),
resultDiv=document.getElementById('result'),respEl=document.getElementById('response'),
metaEl=document.getElementById('meta'),main=document.getElementById('mainContent');

// Verificar estado al cargar
async function checkStatus(){
  try{
    const r=await fetch('/api/status');const d=await r.json();
    if(d.ready){configBox.style.display='none';main.style.display='block';statusMsg.textContent='✅ Sesion activa - Gemini listo'}
    else{configBox.style.display='block';main.style.display='none';statusMsg.textContent='⚠️ Configura la cookie para empezar'+(d.error?' - '+d.error:'')}
  }catch(e){statusMsg.textContent='Error de conexion: '+e.message}
}
checkStatus();

saveBtn.addEventListener('click',async function(){
  const val=cookieInput.value.trim();if(!val){alert('Pega la cookie primero');return}
  saveBtn.textContent='Guardando...';saveBtn.disabled=true;
  try{
    const r=await fetch('/api/set-cookie',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cookie:val})});
    const d=await r.json();
    if(d.ok){statusMsg.textContent='✅ Cookie guardada';checkStatus()}
    else{alert('Error: '+d.error);saveBtn.textContent='Guardar cookie';saveBtn.disabled=false}
  }catch(e){alert('Error: '+e.message);saveBtn.textContent='Guardar cookie';saveBtn.disabled=false}
});

fileInput.addEventListener('change',function(){
  const f=this.files[0];if(!f)return;
  const r=new FileReader();r.onload=e=>{preview.src=e.target.result;preview.style.display='block'};r.readAsDataURL(f);
});

btn.addEventListener('click',async function(){
  const f=fileInput.files[0];if(!f){alert('Selecciona una imagen');return}
  btn.style.display='none';spinner.style.display='block';resultDiv.style.display='none';
  const r=new FileReader();
  r.onload=async function(e){
    try{
      const res=await fetch('/api/proxy',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({image:e.target.result,analysisType:document.getElementById('type').value,responseStyle:document.getElementById('style').value})});
      const d=await res.json();
      resultDiv.style.display='block';
      if(d.success){
        respEl.textContent=d.response;respEl.className='resp';
        metaEl.textContent=d.extractedText;
      }else{
        respEl.textContent='Error: '+(d.error||'Desconocido');respEl.className='resp error';
        if(d.error==='Usuario no autenticado'){statusMsg.textContent='⚠️ Sesion expirada, actualiza la cookie';checkStatus()}
      }
    }catch(err){
      resultDiv.style.display='block';respEl.textContent='Error de conexion: '+err.message;respEl.className='resp error';
    }
    btn.style.display='block';spinner.style.display='none';
  };r.readAsDataURL(f);
});
</script>
</body>
</html>"""

@app.route('/')
def index():
    return HTML

@app.route('/api/status')
def status():
    return {'ready': ready, 'error': '' if ready else 'Sin sesion'}

@app.route('/api/set-cookie', methods=['POST'])
def set_cookie():
    global current_refresh_token, current_cookie, current_access_token, ready, cookie_part0, cookie_part1
    data = request.get_json(force=True)
    raw = data.get("cookie", "")
    rt = extract_refresh_from_full_cookie(raw)
    if not rt:
        return {'ok': False, 'error': 'No se pudo extraer el refresh_token de la cookie'}

    # Extraer y guardar las partes .0 y .1 del cookie original del usuario
    match0 = re.search(r'\.0=base64-([^;]+)', raw)
    match1 = re.search(r'\.1=([^;]+)', raw)
    if match0:
        cookie_part0 = "base64-" + match0.group(1).strip()
    if match1:
        cookie_part1 = match1.group(1).strip()
    current_cookie = "sb-eptdvpvwspuykrcnxcqt-auth-token.0=" + cookie_part0 + "; sb-eptdvpvwspuykrcnxcqt-auth-token.1=" + cookie_part1

    current_refresh_token = rt
    save_cookie()
    if refresh_session():
        return {'ok': True}
    # Si falla refresh, usar el cookie del usuario directamente
    ready = True
    return {'ok': True}

@app.route('/api/proxy', methods=['POST', 'OPTIONS'])
def proxy():
    if request.method == 'OPTIONS':
        return '', 204, {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type'}
    if not ready:
        return {'error': 'Usuario no autenticado', 'success': False}, 401, {'Access-Control-Allow-Origin': '*'}

    data = request.get_json(force=True)
    reset_counter()

    headers = {
        'Content-Type': 'application/json',
        'Cookie': current_cookie
    }
    try:
        r = http.post('https://liggo.love/api/analyze', headers=headers, json=data, timeout=120)
        resp = app.response_class(r.content, status=r.status_code, content_type='application/json')
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp
    except Exception as e:
        return {'error': str(e), 'success': False}, 500, {'Access-Control-Allow-Origin': '*'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8765))
    print(f"\n  Liggo Analyzer")
    print(f"  http://localhost:{port}")
    print(f"  Ctrl+C para detener\n")
    app.run(host='0.0.0.0', port=port, debug=False)
