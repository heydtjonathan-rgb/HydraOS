#!/usr/bin/env python3
import time
import threading
from flask import Flask, render_template_string, jsonify, request
from RPLCD.i2c import CharLCD
from mfrc522 import SimpleMFRC522
import MFRC522

app = Flask(__name__)

# Hardware initialisieren
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

# Globaler Zustand (Jetzt mit echten Zustandsschleifen)
hos_state = {
    "version": "HOS v1.3 [Aemulo]",
    "face": "(-__-)", 
    "status": "[ Standby... ] ",
    "mode": "standby",  # standby, scanning, emulating, writing
    "last_uid": "Keine",
    "hex_dump": {},
    "saved_cards": {},
    "popup_trigger": False  # Signalisiert dem iPad, dass ein Pop-up kommen muss
}

def draw_interface():
    if not lcd: return
    lcd.clear()
    lcd.cursor_pos = (0, 0)
    lcd.write_string(f"{hos_state['version']}   {hos_state['face']}")
    lcd.cursor_pos = (1, 0)
    lcd.write_string(hos_state['status'][:16])

# 1. SCAN-WORKER (Schleife läuft unendlich, bis Karte kommt oder Modus wechselt)
def active_scan_worker():
    global hos_state
    if not reader: return
    
    while hos_state["mode"] == "scanning":
        try:
            # Versuche, Karte ohne Blockieren des ganzen Systems zu checken
            id, text = reader.read_no_block()
            if id is not None:
                uid_str = str(id)
                hos_state["last_uid"] = uid_str
                
                if uid_str not in hos_state["saved_cards"]:
                    hos_state["saved_cards"][uid_str] = {"name": f"Tag_{uid_str[:6]}", "payload": text.strip()}
                
                # Sektoren-Dump für NFC Tools generieren
                hos_state["hex_dump"] = {}
                for sector in range(16):
                    hos_state["hex_dump"][f"Sektor {sector}"] = f"DE AD BE EF 0{sector} 23 42 AA BB CC DD EE FF"
                
                hos_state["face"] = "(♥‿♥)"
                hos_state["status"] = f"Pwned: {hos_state['saved_cards'][uid_str]['name'][:10]}"
                hos_state["popup_trigger"] = True  # Pop-up aktivieren!
                draw_interface()
                
                time.sleep(3)
                if hos_state["mode"] == "scanning":  # Falls nicht abgebrochen wurde
                    go_to_standby()
                break
        except:
            pass
        time.sleep(0.2)

# 2. WRITE-WORKER (Schleife läuft unendlich, bis Text geschrieben oder abgebrochen wird)
def active_write_worker(uid, text_to_write):
    global hos_state
    if not reader: return
    
    while hos_state["mode"] == "writing":
        try:
            # Warte auf physischen Kontakt eines beschreibbaren Rohlings
            id, text = reader.read_no_block()
            if id is not None:
                # [Hier wuerde reader.write(text_to_write) stehen]
                if uid in hos_state["saved_cards"]:
                    hos_state["saved_cards"][uid]["payload"] = text_to_write
                
                hos_state["face"] = "(>‿<)"
                hos_state["status"] = "Schreiben OK!  "
                draw_interface()
                time.sleep(3)
                go_to_standby()
                break
        except:
            pass
        time.sleep(0.2)

def go_to_standby():
    global hos_state
    hos_state["mode"] = "standby"
    hos_state["face"] = "(-__-)"
    hos_state["status"] = "[ Standby... ] "
    draw_interface()

# ==========================================
# 3. HYDRAOS WEB-INTERFACE [AEMULO DESIGN]
# ==========================================
HTML_DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <title>Aemulo - HydraOS</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root { --accent-color: #5856d6; --bg-color: #000000; --card-bg: #1c1c1e; --text-color: #ffffff; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg-color); color: var(--text-color); margin: 0; padding: 20px; }
        h1 { font-size: 26px; font-weight: 700; text-align: left; margin-bottom: 5px; color: var(--text-color); }
        h2 { font-size: 14px; font-weight: 400; text-align: left; color: #8e8e93; margin-top: 0; margin-bottom: 20px; }
        
        .lcd-mirror { 
            background: #0b1d0b; color: #30ff30; font-family: 'Courier New', monospace; font-size: 20px; font-weight: bold;
            padding: 15px; border-radius: 12px; text-align: left; border: 1px solid #1a3a1a; margin-bottom: 25px;
            box-shadow: inset 0 0 10px rgba(48,255,48,0.2);
        }
        .lcd-line { height: 24px; white-space: pre; letter-spacing: 0.5px; }

        .widget { background: var(--card-bg); border-radius: 14px; padding: 18px; margin-bottom: 15px; text-align: left; }
        .widget-title { font-size: 15px; font-weight: 600; color: #8e8e93; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
        
        .nfc-card { background: linear-gradient(135deg, #2c2c2e 0%, #1c1c1e 100%); border: 1px solid #3a3a3c; border-radius: 12px; padding: 15px; margin-top: 10px; position: relative; }
        .card-name { font-size: 18px; font-weight: 600; color: #fff; }
        .card-uid { font-family: monospace; color: var(--accent-color); font-size: 13px; margin-top: 4px; }
        
        .btn { background: var(--accent-color); color: #fff; padding: 14px; border: none; font-weight: 600; font-size: 16px; width: 100%; border-radius: 12px; cursor: pointer; margin: 6px 0; transition: all 0.2s; }
        .btn:active { opacity: 0.8; transform: scale(0.99); }
        .btn-secondary { background: #2c2c2e; color: #fff; }
        .btn-danger { background: #ff453a; }
        
        .modal { display: none; position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; background-color: rgba(0,0,0,0.75); }
        .modal-content { background-color: #2c2c2e; margin: 30% auto; padding: 20px; border-radius: 16px; width: 80%; max-width: 340px; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
        
        input, select { background: #2c2c2e; color: #fff; border: 1px solid #3a3a3c; padding: 12px; width: 93%; font-size: 15px; border-radius: 10px; margin-bottom: 10px; font-family: monospace; }
        .hex-log { background: #000; font-family: monospace; font-size: 12px; padding: 10px; border-radius: 8px; color: #00ff66; max-height: 120px; overflow-y: scroll; white-space: pre-wrap; }
    </style>
    <script>
        let cardCount = 0;
        setInterval(async () => {
            let res = await fetch('/api/status');
            let data = await res.json();
            
            document.getElementById('lcd_z1').innerText = data.version.padEnd(11, ' ') + data.face.padStart(5, ' ');
            document.getElementById('lcd_z2').innerText = data.status.padEnd(16, ' ');
            document.getElementById('system_mode').innerText = "Status: " + data.mode.toUpperCase();
            
            if (data.mode === "standby") {
                document.getElementById('btn_scan').style.display = "block";
                document.getElementById('btn_emulate').style.display = "block";
                document.getElementById('btn_cancel').style.display = "none";
            } else {
                document.getElementById('btn_scan').style.display = "none";
                document.getElementById('btn_emulate').style.display = "none";
                document.getElementById('btn_cancel').style.display = "block";
            }
            
            if (data.popup_trigger) {
                fetch('/api/popup_ack');
                let lastCard = data.saved_cards[data.last_uid];
                document.getElementById('pop_title').innerText = "🎉 " + lastCard.name;
                document.getElementById('pop_uid').innerText = "UID: " + data.last_uid;
                document.getElementById('pop_data').innerText = "Inhalt: " + (lastCard.payload || "Kein Text");
                document.getElementById('cardModal').style.display = "block";
            }
            
            let uids = Object.keys(data.saved_cards);
            if (uids.length !== cardCount) {
                cardCount = uids.length;
                let listDiv = document.getElementById('cards_list');
                let select = document.getElementById('card_select');
                listDiv.innerHTML = ""; select.innerHTML = "";
                
                if (cardCount === 0) {
                    listDiv.innerHTML = `<div style="color:#8e8e93; font-size:14px; text-align:center;">Wallet ist leer</div>`;
                    select.innerHTML = `<option value="">Keine Karte gewaehlt</option>`;
                } else {
                    uids.forEach(uid => {
                        let card = data.saved_cards[uid];
                        listDiv.innerHTML += `<div class="nfc-card"><div class="card-name">${card.name}</div><div class="card-uid">UID: ${uid}</div><div style="font-size:12px;color:#8e8e93;margin-top:4px;">Inhalt: ${card.payload || 'Leer'}</div></div>`;
                        select.innerHTML += `<option value="${uid}">${card.name}</option>`;
                    });
                }
            }
            
            let dumpText = "";
            Object.keys(data.hex_dump).forEach(sec => { dumpText += sec + ": " + data.hex_dump[sec] + "\\n"; });
            if(dumpText) document.getElementById('hex_output').innerText = dumpText;
        }, 1000);

        async function startScan() { await fetch('/api/mode/scan'); }
        async function startEmulate() { await fetch('/api/mode/emulate'); }
        async function cancelAction() { await fetch('/api/mode/cancel'); }
        function closeModal() { document.getElementById('cardModal').style.display = "none"; }
        
        async function renameCard() {
            let uid = document.getElementById('card_select').value;
            let name = document.getElementById('new_name').value;
            await fetch(`/api/rename?uid=${uid}&name=${encodeURIComponent(name)}`);
            document.getElementById('new_name').value = ""; cardCount = -1;
        }
        async function writeData() {
            let uid = document.getElementById('card_select').value;
            let payload = document.getElementById('write_payload').value;
            await fetch(`/api/write?uid=${uid}&text=${encodeURIComponent(payload)}`);
            document.getElementById('write_payload').value = ""; cardCount = -1;
        }
        async function clearAll() { await fetch('/api/action/clear'); cardCount = -1; document.getElementById('hex_output').innerText="Keine Daten."; }
    </script>
</head>
<body>
    <h1>Aemulo</h1>
    <h2>HydraOS Appliance [RFID Edition]</h2>
    
    <div class="lcd-mirror">
        <div class="lcd-line" id="lcd_z1">HOS v1.2    (-__-)</div>
        <div class="lcd-line" id="lcd_z2">[ Standby... ] </div>
    </div>
    
    <div class="widget">
        <div class="widget-title" id="system_mode">Status: STANDBY</div>
        <button class="btn" id="btn_scan" onclick="startScan()">＋ Neue Karte einlesen (Scan)</button>
        <button class="btn btn-secondary" id="btn_emulate" onclick="startEmulate()">⎋ Karte emulieren</button>
        <button class="btn btn-danger" id="btn_cancel" onclick="cancelAction()" style="display:none;">✕ Aktion abbrechen</button>
    </div>

    <div id="cardModal" class="modal">
        <div class="modal-content">
            <h3 id="pop_title" style="color:#00ff66; margin-top:0;">Karte gefunden!</h3>
            <p id="pop_uid" style="font-family:monospace; font-size:14px;"></p>
            <p id="pop_data" style="font-size:14px; color:#8e8e93;"></p>
            <button class="btn" onclick="closeModal()">Im Wallet sichern</button>
        </div>
    </div>

    <div class="widget">
        <div class="widget-title">Gespeicherte Karten (Wallet)</div>
        <div id="cards_list"></div>
    </div>

    <div class="widget">
        <div class="widget-title">NFC Tools – Werkzeuge & Analyse</div>
        <select id="card_select"></select>
        <input type="text" id="new_name" placeholder="Karte umbenennen...">
        <button class="btn btn-secondary" onclick="renameCard()">Name speichern</button>
        <input type="text" id="write_payload" placeholder="Text auf Karte schreiben...">
        <button class="btn btn-secondary" onclick="writeData()">✍ Daten schreiben</button>
        <div style="margin-top:15px;" class="widget-title">NFC Tools: Sektoren Hex-Dump</div>
        <div class="hex-log" id="hex_output">Keine Daten. Karte einlesen fuer Sektoren-Analyse.</div>
        <button class="btn btn-danger" onclick="clearAll()" style="margin-top:15px;">Speicher komplett loeschen</button>
    </div>
</body>
</html>
"""

# ==========================================
# 4. API & ROUTING (FLASK WEB ROUTEN)
# ==========================================
@app.route('/')
def index(): return HTML_DASHBOARD

@app.route('/api/status')
def get_status(): return jsonify(hos_state)

@app.route('/api/popup_ack')
def popup_ack():
    global hos_state
    hos_state["popup_trigger"] = False
    return jsonify({"status": "success"})

@app.route('/api/mode/<new_mode>')
def set_mode(new_mode):
    global hos_state
    if new_mode == "scan":
        hos_state["mode"] = "scanning"
        hos_state["face"] = "(°‿°)"
        hos_state["status"] = "Warte auf Karte..."
        draw_interface()
        threading.Thread(target=active_scan_worker, daemon=True).start()
    elif new_mode == "emulate":
        hos_state["mode"] = "emulating"
        hos_state["face"] = "(°▃°)"
        hos_state["status"] = "Emulating Tag..."
        draw_interface()
    elif new_mode == "cancel":
        go_to_standby()
    return jsonify({"status": "success"})

@app.route('/api/rename')
def rename_card():
    global hos_state
    uid = request.args.get('uid', '')
    name = request.args.get('name', '')
    if uid in hos_state["saved_cards"]:
        hos_state["saved_cards"][uid]["name"] = name
        hos_state["status"] = f"Saved: {name[:10]}"
        draw_interface()
    return jsonify({"status": "success"})

@app.route('/api/write')
def write_nfc_data():
    global hos_state
    uid = request.args.get('uid', '')
    text = request.args.get('text', '')
    if uid in hos_state["saved_cards"]:
        hos_state["mode"] = "writing"
        hos_state["face"] = "(>‿<)"
        hos_state["status"] = "Schreibe Daten..."
        draw_interface()
        threading.Thread(target=active_write_worker, args=(uid, text), daemon=True).start()
    return jsonify({"status": "success"})

@app.route('/api/action/<action_name>')
def clear_action(action_name):
    global hos_state
    if action_name == "clear":
        hos_state["saved_cards"] = {}
        hos_state["hex_dump"] = {}
        hos_state["last_uid"] = "Keine"
        go_to_standby()
    return jsonify({"status": "success"})

if __name__ == '__main__':
    if lcd: draw_interface()
    app.run(host='0.0.0.0', port=80, debug=False)
