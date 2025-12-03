from flask import Flask, render_template_string, request, redirect, url_for, session, flash
import json
import subprocess
import os
import hashlib
import datetime


def normalize_nik(nik):
    """Hashing NIK (string) menjadi nilai numerik field-safe."""
    normalized_nik = nik.strip()
    hash_object = hashlib.sha256(normalized_nik.encode())
    hex_digest = hash_object.hexdigest()
    return int(hex_digest[:16], 16) 

def normalize_name(name):
    """Hashing Nama (string) menjadi nilai numerik field-safe."""
    normalized_name = name.strip().upper() 
    hash_object = hashlib.sha256(normalized_name.encode())
    hex_digest = hash_object.hexdigest()
    return int(hex_digest[:16], 16)

def normalize_birth_year(dob_str):
    """Mengambil tahun (YYYY) dari tanggal lahir format DD-MM-YYYY."""
    try:
        return int(dob_str.strip().split('-')[2])
    except:
        raise ValueError("Format tanggal lahir harus DD-MM-YYYY (Contoh: 07-07-1997).")


app = Flask(__name__)
app.secret_key = 'super_secret_key_anda' 
VKEY_PATH = "build/verification_key.json"

CURRENT_YEAR = 2025
GAME_MIN_AGE = 18

# --- Routes ---

@app.route('/')
def index_game():
    html_content = f"""
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <title>Game Platform (Verifier)</title>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #e6ffe6; padding: 20px; }}
            .container {{ background-color: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 600px; margin: auto; }}
            h2 {{ color: #006633; padding-bottom: 0px; }}
            h3 {{ color: #006633; border-bottom: 2px solid #006633; padding-bottom: 10px; }}
            .form-group {{ margin-bottom: 15px; }}
            label {{ font-weight: bold; display: block; margin-bottom: 5px; color: #333; }}
            input[type="text"], input[type="file"] {{ padding: 10px; border: 1px solid #ccc; border-radius: 4px; display: block; width: 100%; box-sizing: border-box; }}
            button {{ background-color: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; transition: background-color 0.3s; }}
            button:hover {{ background-color: #45a049; }}
            .result-valid {{ color: green; font-weight: bold; font-size: 1.2em; margin-top: 20px; }}
            .result-invalid {{ color: red; font-weight: bold; font-size: 1.2em; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Indonesia National Standard for Secure Identity Verification (off-chain)</h2>
            <p>Input data klaim Anda dan upload bukti ZK. Syarat minimum usia untuk platform ini adalah <b>{GAME_MIN_AGE} tahun</b>.</p>
            <form method="POST" enctype="multipart/form-data" action="/verify-proof">                
                <div class="form-group"><label for="nik">NIK:</label><input type="text" name="nik" id="nik" placeholder="Contoh: 3333332222220001" required></div>
                <div class="form-group"><label for="name">Nama Lengkap:</label><input type="text" name="name" id="name" placeholder="Contoh: Jane Nobody" required></div>
                <div class="form-group"><label for="dob">Tanggal Lahir (DD-MM-YYYY):</label><input type="text" name="dob" id="dob" placeholder="Contoh: 01-01-2001" required></div>
                
                
                <div class="form-group"><label for="proof_file">Upload ZK Proof File ([xxxxx]_zk_proof.json):</label><input type="file" name="proof_file" id="proof_file" accept=".json" required></div>
                <button type="submit">UPLOAD & VERIFY PROOF</button>
            </form>
            
            {{% with messages = get_flashed_messages(with_categories=true) %}}
              {{% if messages %}}
                <hr>
                {{% for category, message in messages %}}
                  <div class="{'{% if category == "valid" %}result-valid{% else %}result-invalid{% endif %}'}">
                    Status Verifikasi: {{{{ message }}}}  
                  </div>
                {{% endfor %}}
              {{% endif %}}
            {{% endwith %}}
        </div>
    </body>
    </html>
    """
    return render_template_string(html_content)

@app.route('/verify-proof', methods=['POST'])
def verify_proof():
    if 'proof_file' not in request.files:
        flash('File Bukti tidak ditemukan', 'invalid')
        return redirect(url_for('index_game'))

    file = request.files['proof_file']
    
    try:
        proof_package = json.loads(file.read().decode('utf-8'))
        proof = proof_package['proof']
        available_public_signals = proof_package['public_signals'] 

        nik_input = request.form.get('nik')
        name_input = request.form.get('name')
        dob_input = request.form.get('dob')

        expected_nik_hash = str(normalize_nik(nik_input))
        expected_name_hash = str(normalize_name(name_input))
        expected_birth_year = str(normalize_birth_year(dob_input))
        expected_birth_year_int = normalize_birth_year(dob_input)
        
        
        MINIMUM_SIGNALS_REQUIRED = 4 
        if len(available_public_signals) < MINIMUM_SIGNALS_REQUIRED:
            flash(f"Bukti ZK rusak atau tidak lengkap. Hanya ditemukan {len(available_public_signals)} sinyal publik, minimal diperlukan {MINIMUM_SIGNALS_REQUIRED}.", 'invalid')
            return redirect(url_for('index_game'))

        is_consistent = (
            available_public_signals[0] == "1" and
            available_public_signals[1] == expected_nik_hash and
            available_public_signals[2] == expected_name_hash and
            available_public_signals[3] == expected_birth_year
        )

        if not is_consistent:
            print("For debug only (console)")
            print(f"EXPECTED DUMMY (1): 1, AVAILABLE (Index 0): {available_public_signals[0]}")
            print(f"EXPECTED NIK HASH: {expected_nik_hash}, AVAILABLE (Index 1): {available_public_signals[1]}")
            print(f"EXPECTED NAME HASH: {expected_name_hash}, AVAILABLE (Index 2): {available_public_signals[2]}")
            print(f"EXPECTED TAHUN: {expected_birth_year}, AVAILABLE (Index 3): {available_public_signals[3]}")
            return redirect(url_for('index_game'))
        
        expected_public_signals_for_snarkjs = [
            "1",                         
            expected_nik_hash,           
            expected_name_hash,          
            expected_birth_year,         
        ]
        
        with open('build/verify_proof.json', 'w') as f:
            json.dump(proof, f)
        with open('build/verify_public.json', 'w') as f:
            json.dump(expected_public_signals_for_snarkjs, f) 

        print("[VERIFIER] Memverifikasi Keaslian Bukti ZK...")
        
        result = subprocess.run(
            ['snarkjs', 'groth16', 'verify', VKEY_PATH, 'build/verify_public.json', 'build/verify_proof.json'], 
            check=False, capture_output=True, text=True
        )

        verification_output = result.stdout.strip()
        
        if "OK" in verification_output:
            age_limit_year = CURRENT_YEAR - GAME_MIN_AGE 

            birth_year_from_proof = int(available_public_signals[3])
            
            if birth_year_from_proof <= age_limit_year:
                status = f"FILE PROOF VALID & SYARAT USIA ({GAME_MIN_AGE}+ tahun) TERPENUHI! ✅"
                category = 'valid'
            else:
                status = f"SYARAT USIA ({GAME_MIN_AGE}+ tahun) TIDAK TERPENUHI. ❌"
                category = 'invalid'
                
        else:
            print(f"[VERIFIER DEBUG] SnarkJS Output: {verification_output}")
            status = "FILE PROOF INVALID. ❌ Bukti Gagal Diverifikasi (Proof Palsu/Modifikasi)."
            category = 'invalid'
            
        flash(status, category)
        return redirect(url_for('index_game'))

    except ValueError as e:
        flash(f"Input data manual salah: {e}", 'invalid')
        return redirect(url_for('index_game'))
    except Exception as e:
        print(f"[ERROR] Internal: {e}")
        flash(f"Terjadi kesalahan saat verifikasi: {e}", 'invalid')
        return redirect(url_for('index_game'))

if __name__ == '__main__':
    app.run(host='0.0.0.0',port=5001, debug=True)