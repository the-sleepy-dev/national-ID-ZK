from flask import Flask, render_template_string, request, send_file
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

ZKEY_PATH = "build/proof_circuit.zkey"
JS_WITNESS_GENERATOR = "build/proof_circuit_js/generate_witness.js" 
WASM_PATH = "build/proof_circuit_js/proof_circuit.wasm" 


@app.route('/')
def index_penduduk():
    html_content = f"""
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <title>Server Data Penduduk (Prover)</title>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f0f8ff; padding: 20px; }}
            .container {{ background-color: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); max-width: 600px; margin: auto; }}
            h2 {{ color: #004d99; border-bottom: 2px solid #004d99; padding-bottom: 10px; }}
            button {{ background-color: #00bfff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; transition: background-color 0.3s; }}
            button:hover {{ background-color: #0099cc; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Server Data Penduduk - ZK Proof Generator</h2>
            <p>Upload **KTP.json** Anda. Bukti akan dibuat untuk NIK, Nama, dan Tahun Lahir (Keaslian Data).</p>
            <form method="POST" enctype="multipart/form-data" action="/generate-proof">
                <div class="form-group">
                    <label for="ktp_file">Upload KTP.json:</label>
                    <input type="file" name="ktp_file" id="ktp_file" accept=".json" required>
                </div>
                <p><b>Target Bukti Publik:</b> Bukti konsistensi NIK, Nama, dan Tahun Lahir.</p>
                <button type="submit">GENERATE PROOF</button>
            </form>
        </div>
    </body>
    </html>
    """
    return render_template_string(html_content)

@app.route('/generate-proof', methods=['POST'])
def generate_proof():
    if 'ktp_file' not in request.files:
        return "File tidak ditemukan", 400
    
    file = request.files['ktp_file']

    try:
        ktp_data = json.loads(file.read().decode('utf-8'))
        
        private_nik_hash = normalize_nik(ktp_data['nik'])
        private_name_hash = normalize_name(ktp_data['nama'])
        private_birth_year = normalize_birth_year(ktp_data['tanggal_lahir'])

        input_data = {
            "private_nik_hash": str(private_nik_hash),
            "private_name_hash": str(private_name_hash),
            "private_birth_year": str(private_birth_year),
            
            "public_nik_hash": str(private_nik_hash),
            "public_name_hash": str(private_name_hash),
            "public_birth_year": str(private_birth_year)
        }
        
        with open('build/input.json', 'w') as f:
            json.dump(input_data, f)

        print("\n[PROVER] Menghasilkan Bukti ZK...")
        
        witness_generator_path = os.path.join(os.getcwd(), JS_WITNESS_GENERATOR)
        wasm_path_full = os.path.join(os.getcwd(), WASM_PATH)
        
        subprocess.run(
            ['node', witness_generator_path, wasm_path_full, 'build/input.json', 'build/witness.wtns'], 
            check=True, 
            capture_output=True, 
            text=True
        )

        subprocess.run(
            ['snarkjs', 'groth16', 'prove', ZKEY_PATH, 'build/witness.wtns', 'build/proof.json', 'build/public.json'], 
            check=True, 
            capture_output=True, 
            text=True
        )

        print("[PROVER] Bukti berhasil dibuat.")
        
        with open('build/proof.json', 'r') as f_proof:
            proof = json.load(f_proof)
        with open('build/public.json', 'r') as f_public:
            public = json.load(f_public)
        
        proof_package = {
            "proof": proof,
            "public_signals": public,
            "description": "ZK Proof for NIK, Name, Birth Year consistency"
        }
        
        proof_filename = "bob_zk_proof.json"
        with open(proof_filename, 'w') as f:
            json.dump(proof_package, f, indent=2)

        return send_file(
            proof_filename,
            mimetype='application/json',
            as_attachment=True,
            download_name=proof_filename
        )

    except subprocess.CalledProcessError as e:
        error_output = e.stderr.strip().split('\n')[-1]
        print(f"[ERROR] SnarkJS/Witness Gagal: {error_output}")
        return f"Gagal membuat bukti ZK. Pastikan data KTP valid. Error: {error_output}", 500
    except Exception as e:
        print(f"[ERROR] Internal: {e}")
        return f"Terjadi kesalahan saat membuat bukti: {e}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)