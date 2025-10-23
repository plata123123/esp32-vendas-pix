# server_render.py
from flask import Flask, request, jsonify, send_file
import os, time, base64
from io import BytesIO
from PIL import Image
import mercadopago

app = Flask(__name__)

# TOKEN Mercado Pago e chave ESP definidas no ambiente (Render -> Environment)
TOKEN_MP = os.environ.get("TOKEN_MP", "")
ESP_ALLOWED_KEY = os.environ.get("ESP_KEY", "minha_esp_key_default")  # defina no Render

mp = mercadopago.SDK(TOKEN_MP)

# memória simples: token_esp -> {payment_id, status, qr_payload, qr_image_base64}
pagamentos = {}

def esp_auth_ok(received_key):
    return (received_key is not None) and (received_key == ESP_ALLOWED_KEY)

@app.route("/criar_pagamento")
def criar_pagamento():
    produto = request.args.get("produto")
    token = request.args.get("token")
    esp_key = request.args.get("esp_key")
    if not esp_auth_ok(esp_key):
        return "unauthorized", 401
    if not produto or not token:
        return "missing params", 400

    valores = {"A": 8.0, "B": 10.0, "C": 12.0, "D": 6.0}
    amount = valores.get(produto, 10.0)

    payment_data = {
        "transaction_amount": amount,
        "description": f"Produto {produto}",
        "payment_method_id": "pix",
        "payer": {"email": "cliente@exemplo.com"}
    }

    try:
        resp = mp.payment().create(payment_data)
        r = resp["response"]
        payment_id = r.get("id")
        poi = r.get("point_of_interaction", {}) or {}
        tdata = poi.get("transaction_data", {}) or {}

        qr_payload = tdata.get("qr_code") or tdata.get("qr_code_payload") or None
        qr_base64 = tdata.get("qr_code_base64") or None

        pagamentos[token] = {"payment_id": payment_id, "status": "pendente",
                             "qr_payload": qr_payload, "qr_image_base64": qr_base64, "created": time.time()}

        if qr_payload:
            return jsonify({"qr_payload": qr_payload, "token": token})
        elif qr_base64:
            return jsonify({"qr_image_base64": qr_base64, "token": token})
        else:
            return jsonify({"message": "qr not available", "token": token})
    except Exception as e:
        print("MP create error:", e)
        return "mp error", 500

@app.route("/status_pagamento")
def status_pagamento():
    token = request.args.get("token")
    esp_key = request.args.get("esp_key")
    if not esp_auth_ok(esp_key):
        return "unauthorized", 401
    if not token or token not in pagamentos:
        return "invalido", 404
    try:
        payment_id = pagamentos[token]["payment_id"]
        info = mp.payment().get(payment_id)
        status = info["response"].get("status")
        if status == "approved":
            pagamentos[token]["status"] = "aprovado"
        return pagamentos[token]["status"]
    except Exception as e:
        print("status error:", e)
        return "erro", 500

@app.route("/show_qr")
def show_qr():
    token = request.args.get("token")
    if not token or token not in pagamentos:
        return "invalid", 400
    entry = pagamentos[token]
    b64 = entry.get("qr_image_base64")
    if not b64:
        return "no image", 404
    try:
        imgdata = base64.b64decode(b64)
        return send_file(BytesIO(imgdata), mimetype='image/png')
    except Exception as e:
        print("decode error:", e)
        return "error",500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
