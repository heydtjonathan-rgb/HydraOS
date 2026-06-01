#!/usr/bin/env python3
import time
import threading
from flask import Flask, render_template_string, jsonify
from RPLCD.i2c import CharLCD
from mfrc522 import SimpleMFRC522

# ==========================================
# 1. HARDWARE & INITIALISIERUNG
# ==========================================
app = Flask(__name__)

lcd = None
for addr in [0x27, 0x3F]:
    try:
        lcd = CharLCD('PCF8574', addr)
        break
    except:
        continue

try:
    reader = SimpleMFRC522()
except:
    reader = None

# Der globale Systemzustand für die RFID-Version von HydraOS
hos_state = {
    "version": "HOS v1.0 [RFID]",
    "face": "(°‿°)",
    "status": "Scanning...     ",
    "scans": 0,
    "last_uid": "Keine Karte",
    "saved_uids": [] # Liste für geklonte/gespeicherte Karten
}

# ==========================================
# 2. LCD-RENDERING (ZEILE 1 & ZEILE 2)
# ==========================================
def draw_interface():
    if not lcd: return
    lcd.clear()
    # Zeile 1: OS-Version links, Tamagotchi-Gesicht rechts
    lcd.cursor_pos = (0, 0)
    lcd.write_string(f"{hos_state['version']}   {hos_state['face']}")
    # Zeile 2: Der aktuelle Live-Status (max. 16 Zeichen)
    lcd.cursor_pos = (1, 0)
    lcd.write_string(hos_state['status'][:16])

def rfid_auto_scan():
    global hos_state
    while True:
        if reader:
            # Wartet passiv, bis eine Karte an die Box gehalten wird
            id, text = reader.read()
            hos_state["scans"] += 1
            hos_state["last_uid"] = str(id)
            if str(id) not in hos_state["saved_uids"]:
                hos_state["saved_uids"].append(str(id))
            
            # Das Tamagotchi freut sich über das RFID-Futter!
            hos_state["face"] = "(♥‿♥)"
            hos_state["status"] = f"Pwned! ID:{str(id)[:8]}"
            draw_interface()
            
            # Nach 4 Sekunden geht es zurück in den Scan-Modus
            time.sleep(4)
            hos_state["face"] = "(^‿^)"
            hos_state["status"] = "Scanning...     "
            draw_interface()
        time.sleep(0.5)

# Startet den RFID-Hintergrund-Scanner
if reader:
    threading.Thread(target=rfid_auto_scan, daemon=True).start()

# ==========================================
# 3. HYDRAOS WEB-DASHBOARD (HTML & AJAX)
# ==========================================
HTML_DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <title>HydraOS Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: 'Courier New', monospace; background: #050505; color: #00ff66; text-align: center; padding: 10px; }
        h1 { color: #00ff66; text-shadow: 0 0 10px #00ff66; font-size: 22px; }
        
        /* Das gespiegelte LCD-Display im Flipper-Look */
        .lcd-mirror { 
            background: #002200; color: #00ff66; font-size: 22px; font-weight: bold;
            padding: 15px; border: 3px solid #00ff66; border-radius: 5px;
            display: inline-block; text-align: left; width: 90%; max-width: 380px;
            box-shadow: inset 0 0 15px rgba(0,255,102,0.5), 0 0 10px rgba(0,255,102,0.3);
            margin-bottom: 20px;
        }
        .lcd-line { height: 26px; letter-spacing: 1px; white-space: pre; }
        
        .box { background: #111; padding: 15px; margin: 15px auto; max-width: 410px; border: 1px solid #333; border-radius: 5px; }
        .btn { background: #00ff66; color: #000; padding: 12px; border: none; font-weight: bold; font-size: 14px; width: 90%; cursor: pointer; margin: 8px 0; border-radius: 3px; }
        .btn:hover { background: #00cc52; box-shadow: 0 0 8px #00ff66; }
        .btn-danger { background: #ff3333; color: white; }
        .btn-danger:hover { background: #cc0000; box-shadow: 0 0 8px #ff3333; }
        select { background: #222; color: #00ff66; border: 1px solid #00ff66; padding: 10px; width: 90%; font-size: 14px; font-family: monospace; }
    </style>
    <script>
        // Spiegelt das LCD-Display jede Sekunde live auf das iPad-Dashboard
        setInterval(async () => {
            let res = await fetch('/api/status');
            let data = await res.json();
            
            // Zeile 1 spiegeln (Name/Version + Gesicht)
            // Wir fuellen mit Leerzeichen auf, damit es wie ein echtes 16x2 Display aussieht
            let line1 = data.version.padEnd(11, ' ') + data.face.padStart(5, ' ');
            document.getElementById('lcd_z1').innerText = line1;
            
            // Zeile 2 spiegeln (Status-Text)
            document.getElementById('lcd_z2').innerText = data.status.padEnd(16, ' ');
            
            // Liste der gespeicherten UIDs aktualisieren
            let select = document.getElementById('card_select');
            let currentLength = select.options.length;
            if (data.saved_uids.length > currentLength) {
                select.innerHTML = "";
                data.saved_uids.forEach(uid => {
                    let opt = document.createElement('option');
                    opt.value = uid;
                    opt.innerText = "Karte ID: " + uid;
                    select.appendChild(opt);
                });
            }
        }, 1000);

        async function triggerAction(actionName) {
            let targetUid = document.getElementById('card_select').value || "none";
            await fetch(`/api/action/${actionName}?uid=${targetUid}`);
        }
    </script>
</head>
<body>
    <h1>[ HYDRA-OS CONTROLLER ]</h1>
    
    <!-- 1. OBEN: DAS GESPIEGELTE LCD-DISPLAY -->
    <div class="lcd-mirror">
        <div class="lcd-line" id="lcd_z1">Lade Zeile 1...</div>
        <div class="lcd-line" id="lcd_z2">Lade Zeile 2...</div>
    </div>
    
    <!-- 2. DARUNTER: DIE RFID-AKTIONEN -->
    <div class="box">
        <h3>Gefangene RFID-Schluessel</h3>
        <select id="card_select">
            <option value="">(Keine Karten im Speicher)</option>
        </select>
    </div>

    <div class="box">
        <h3>Aktionen ausfuehren</h3>
        <button class="btn" onclick="triggerAction('emulate')">Ausgewaehlte Karte emulieren</button>
        <button class="btn" onclick="triggerAction('clone')">Karte auf Rohling schreiben</button>
        <button class="btn btn-danger" onclick="triggerAction('clear')">Speicher loeschen</button>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return HTML_DASHBOARD

@app.route('/api/status')
def get_status():
    return jsonify(hos_state)

@app.route('/api/action/<action_name>')
def web_action(action_name):
    global hos_state
    import request
    target_uid = request.args.get('uid', 'none')
    
    if action_name == "emulate":
        hos_state["face"] = "(°▃°)"
        hos_state["status"] = f"Emulating:{target_uid[:6]}"
        draw_interface()
        # [Hier kommt spaeter der echte SPI-Befehl fuer die RC522-Emulation hin]
        
    elif action_name == "clone":
        hos_state["face"] = "(>‿<)"
        hos_state["status"] = "Writing Rohling"
        draw_interface()
        if reader and target_uid != "none":
            # Wartet, bis du einen leeren RFID-Schluesselanhaenger an die Box haeltst
            reader.write(f"KLON:{target_uid}")
            hos_state["status"] = "Klonen erfolgreich"
            draw_interface()

    elif action_name == "clear":
        hos_state["saved_uids"] = []
        hos_state["scans"] = 0
        hos_state["face"] = "(✿◠‿◠)"
        hos_state["status"] = "Speicher leer!  "
        draw_interface()
        
    return jsonify({"status": "success"})

if __name__ == '__main__':
    if lcd: draw_interface()
    # Startet den Webserver auf Port 80 (Standard für Webseiten)
    app.run(host='0.0.0.0', port=80, debug=False)
