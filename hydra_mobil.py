#!/usr/bin/env python3
import time
import threading
from flask import Flask, render_template_string, jsonify, request
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
    "saved_cards": {}  # Speichert Karten als {"UID": "Name"}
}

# ==========================================
# 2. LCD-RENDERING
# ==========================================
def draw_interface():
    if not lcd: return
    lcd.clear()
    lcd.cursor_pos = (0, 0)
    lcd.write_string(f"{hos_state['version']}   {hos_state['face']}")
    lcd.cursor_pos = (1, 0)
    lcd.write_string(hos_state['status'][:16])

def rfid_auto_scan():
    global hos_state
    while True:
        if reader:
            id, text = reader.read()
            uid_str = str(id)
            hos_state["scans"] += 1
            hos_state["last_uid"] = uid_str
            
            # Wenn die Karte neu ist, bekommt sie standardmaessig die ID als Namen
            if uid_str not in hos_state["saved_cards"]:
                hos_state["saved_cards"][uid_str] = f"Karte_{uid_str[:6]}"
            
            hos_state["face"] = "(♥‿♥)"
            hos_state["status"] = f"Pwned! {hos_state['saved_cards'][uid_str][:10]}"
            draw_interface()
            
            time.sleep(4)
            hos_state["face"] = "(^‿^)"
            hos_state["status"] = "Scanning...     "
            draw_interface()
        time.sleep(0.5)

if reader:
    threading.Thread(target=rfid_auto_scan, daemon=True).start()

# ==========================================
# 3. HYDRAOS WEB-DASHBOARD (MIT BENENNUNG)
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
        .lcd-mirror { 
            background: #002200; color: #00ff66; font-size: 22px; font-weight: bold;
            padding: 15px; border: 3px solid #00ff66; border-radius: 5px;
            display: inline-block; text-align: left; width: 90%; max-width: 380px;
            box-shadow: inset 0 0 15px rgba(0,255,102,0.5), 0 0 10px rgba(0,255,102,0.3);
            margin-bottom: 20px;
        }
        .lcd-line { height: 26px; letter-spacing: 1px; white-space: pre; }
        .box { background: #111; padding: 15px; margin: 15px auto; max-width: 410px; border: 1px solid #333; border-radius: 5px; text-align: left; }
        .box h3 { margin-top: 0; text-align: center; color: #00ff66; }
        .btn { background: #00ff66; color: #000; padding: 12px; border: none; font-weight: bold; font-size: 14px; width: 100%; cursor: pointer; margin: 8px 0; border-radius: 3px; }
        .btn:hover { background: #00cc52; box-shadow: 0 0 8px #00ff66; }
        .btn-danger { background: #ff3333; color: white; }
        .btn-danger:hover { background: #cc0000; box-shadow: 0 0 8px #ff3333; }
        select, input { background: #222; color: #00ff66; border: 1px solid #00ff66; padding: 10px; width: 95%; font-size: 14px; font-family: monospace; margin-bottom: 10px; }
    </style>
    <script>
        let currentCardCount = 0;

        setInterval(async () => {
            let res = await fetch('/api/status');
            let data = await res.json();
            
            let line1 = data.version.padEnd(11, ' ') + data.face.padStart(5, ' ');
            document.getElementById('lcd_z1').innerText = line1;
            document.getElementById('lcd_z2').innerText = data.status.padEnd(16, ' ');
            
            let uids = Object.keys(data.saved_cards);
            if (uids.length !== currentCardCount) {
                currentCardCount = uids.length;
                let select = document.getElementById('card_select');
                let selectedValue = select.value;
                select.innerHTML = "";
                
                if (currentCardCount === 0) {
                    let opt = document.createElement('option');
                    opt.value = "";
                    opt.innerText = "(Keine Karten im Speicher)";
                    select.appendChild(opt);
                } else {
                    uids.forEach(uid => {
                        let opt = document.createElement('option');
                        opt.value = uid;
                        opt.innerText = data.saved_cards[uid] + " [" + uid.substring(0,6) + "...]";
                        select.appendChild(opt);
                    });
                    if (selectedValue && data.saved_cards[selectedValue]) {
                        select.value = selectedValue;
                    }
                }
            }
        }, 1000);

        async function triggerAction(actionName) {
            let targetUid = document.getElementById('card_select').value;
            if (!targetUid && actionName !== 'clear') {
                alert("Bitte waehle zuerst eine Karte aus!");
                return;
            }
            await fetch(`/api/action/${actionName}?uid=${targetUid}`);
        }

        async function renameCard() {
            let targetUid = document.getElementById('card_select').value;
            let newName = document.getElementById('new_name').value;
            if (!targetUid || !newName) {
                alert("Waehle eine Karte und gib einen Namen ein!");
                return;
            }
            await fetch(`/api/rename?uid=${targetUid}&name=${encodeURIComponent(newName)}`);
            document.getElementById('new_name').value = "";
            currentCardCount = -1; // Erzwingt Neuladen der Liste
        }
    </script>
</head>
<body>
    <h1>[ HYDRA-OS CONTROLLER ]</h1>
    
    <div class="lcd-mirror">
        <div class="lcd-line" id="lcd_z1">Lade Zeile 1...</div>
        <div class="lcd-line" id="lcd_z2">Lade Zeile 2...</div>
    </div>
    
    <div class="box">
        <h3>Gefangene RFID-Schluessel</h3>
        <select id="card_select"></select>
        
        <input type="text" id="new_name" placeholder="Neuen Namen eingeben...">
        <button class="btn" onclick="renameCard()" style="background:#00b3ff;">Karte umbenennen</button>
    </div>

    <div class="box">
        <h3>Aktionen ausfuehren</h3>
        <button class="btn" onclick="triggerAction('emulate')">Ausgewaehlte Karte emulieren</button>
        <button class="btn" onclick="triggerAction('clone')">Karte auf Rohling schreiben</button>
        <button class="btn btn-danger" onclick="triggerAction('clear')">Speicher loeschen</button>
    </div>
</body>
</html>
""";

@app.route('/')
def index(): return HTML_DASHBOARD

@app.route('/api/status')
def get_status(): return jsonify(hos_state)

@app.route('/api/rename')
def rename_card():
    global hos_state
    uid = request.args.get('uid', '')
    name = request.args.get('name', '')
    if uid in hos_state["saved_cards"] and name:
        hos_state["saved_cards"][uid] = name
        hos_state["status"] = f"Renamed: {name[:8]}"
        draw_interface()
    return jsonify({"status": "success"})

@app.route('/api/action/<action_name>')
def web_action(action_name):
    global hos_state
    target_uid = request.args.get('uid', 'none')
    
    if action_name == "emulate":
        card_name = hos_state["saved_cards"].get(target_uid, "Karte")
        hos_state["face"] = "(°▃°)"
        hos_state["status"] = f"Emul: {card_name[:10]}"
        draw_interface()
        # Hier wird spaeter die RC522 Hardware-Emulation getriggert
        
    elif action_name == "clone":
        hos_state["face"] = "(>‿<)"
        hos_state["status"] = "Hold Rohling..."
        draw_interface()
        if reader and target_uid != "none":
            # [Hier wuerde reader.write() stehen, wir loesen es fuer den Flow passiv]
            pass

    elif action_name == "clear":
        hos_state["saved_cards"] = {}
        hos_state["scans"] = 0
        hos_state["face"] = "(✿◠‿◠)"
        hos_state["status"] = "Speicher leer!  "
        draw_interface()
        
    return jsonify({"status": "success"})

if __name__ == '__main__':
    if lcd: draw_interface()
    app.run(host='0.0.0.0', port=80, debug=False)
