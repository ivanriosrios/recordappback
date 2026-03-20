#!/usr/bin/env python3
"""
OlaApp — Script de configuración completa de Twilio.

Ejecuta esto desde tu máquina local (NO desde Railway/Docker):

    cd recordApp/back/recordappback
    pip install twilio requests
    python scripts/setup_twilio.py

Este script:
1. Verifica la conexión con tu cuenta Twilio
2. Lista tus números de WhatsApp disponibles
3. Crea los 5 Content Templates necesarios para OlaApp
4. Configura el webhook de mensajes entrantes
5. Envía un mensaje de prueba
"""

import json
import os
import sys
import time
import requests
from requests.auth import HTTPBasicAuth

# ─── CONFIGURACIÓN ───────────────────────────────────────────────────────
# Cargar credenciales desde variables de entorno para evitar comprometer secretos
def get_env_or_exit(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"❌ Falta la variable de entorno {name}")
        sys.exit(1)
    return value


# Tus credenciales de Twilio (defínelas en tu entorno / Railway)
ACCOUNT_SID = get_env_or_exit("TWILIO_ACCOUNT_SID")
API_KEY_SID = get_env_or_exit("TWILIO_API_KEY_SID")
API_KEY_SECRET = get_env_or_exit("TWILIO_API_KEY_SECRET")

# Tu número sender de WhatsApp (sandbox de Twilio)
WHATSAPP_FROM = get_env_or_exit("TWILIO_WHATSAPP_NUMBER")

# URL de tu backend en Railway
RAILWAY_BASE_URL = os.getenv("RAILWAY_BASE_URL", "")

# Número para prueba (tu propio WhatsApp, con código de país)
TEST_PHONE = os.getenv("TEST_PHONE", "")

# ─── AUTH ────────────────────────────────────────────────────────────────
AUTH = HTTPBasicAuth(API_KEY_SID, API_KEY_SECRET)
BASE_API = "https://api.twilio.com/2010-04-01"
CONTENT_API = "https://content.twilio.com/v1"


def api_get(url, params=None):
    r = requests.get(url, auth=AUTH, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def api_post(url, data=None, json_body=None):
    if json_body:
        r = requests.post(url, auth=AUTH, json=json_body, timeout=15)
    else:
        r = requests.post(url, auth=AUTH, data=data, timeout=15)
    return r


# ─── PASO 1: Verificar conexión ─────────────────────────────────────────

def step1_verify_connection():
    print("\n═══ PASO 1: Verificando conexión con Twilio ═══")
    try:
        data = api_get(f"{BASE_API}/Accounts/{ACCOUNT_SID}.json")
        print(f"  ✅ Cuenta: {data['friendly_name']}")
        print(f"  ✅ Estado: {data['status']}")
        print(f"  ✅ Tipo:   {data['type']}")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


# ─── PASO 2: Listar números WhatsApp ────────────────────────────────────

def step2_list_numbers():
    print("\n═══ PASO 2: Números de teléfono en la cuenta ═══")
    try:
        data = api_get(
            f"{BASE_API}/Accounts/{ACCOUNT_SID}/IncomingPhoneNumbers.json"
        )
        numbers = data.get("incoming_phone_numbers", [])
        if not numbers:
            print("  ⚠️  No hay números. Puede que uses el sandbox de WhatsApp.")
        for n in numbers:
            caps = n.get("capabilities", {})
            print(f"  📱 {n['phone_number']} — SMS:{caps.get('sms')} Voice:{caps.get('voice')}")

        # Check WhatsApp senders
        print(f"\n  📨 Sender configurado: {WHATSAPP_FROM}")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


# ─── PASO 3: Crear Content Templates ────────────────────────────────────

# Templates de RecordApp mapeados al formato de Twilio Content API
TEMPLATES = [
    {
        "friendly_name": "OlaApp - Recordatorio de Cita",
        "language": "es",
        "variables": {"1": "Juan", "2": "Corte de cabello", "3": "Barbería El Patrón"},
        "types": {
            "twilio/text": {
                "body": "Hola {{1}} 👋, te recordamos que tienes programado tu servicio de *{{2}}* en *{{3}}*. ¿Confirmas tu asistencia? Responde *SI* o *NO*."
            }
        },
        "meta_name": "recordatorio_cita",
    },
    {
        "friendly_name": "OlaApp - Encuesta Post-Servicio",
        "language": "es",
        "variables": {"1": "Juan", "2": "Barbería El Patrón", "3": "Corte de cabello"},
        "types": {
            "twilio/text": {
                "body": "Hola {{1}}, hace poco te atendimos en *{{2}}* con el servicio *{{3}}*. ¿Cómo te fue? Responde:\n\n1️⃣ Excelente\n2️⃣ Bien\n3️⃣ Regular\n4️⃣ Mal"
            }
        },
        "meta_name": "encuesta_servicio",
    },
    {
        "friendly_name": "OlaApp - Feliz Cumpleaños",
        "language": "es",
        "variables": {"1": "Juan", "2": "Barbería El Patrón"},
        "types": {
            "twilio/text": {
                "body": "🎂 ¡Feliz cumpleaños {{1}}! 🎉\n\nDe parte de todo el equipo de *{{2}}* te deseamos un excelente día. ¡Te esperamos pronto!"
            }
        },
        "meta_name": "feliz_cumpleanos",
    },
    {
        "friendly_name": "OlaApp - Reactivación Cliente",
        "language": "es",
        "variables": {"1": "Juan", "2": "Barbería El Patrón"},
        "types": {
            "twilio/text": {
                "body": "Hola {{1}}, hace tiempo que no te vemos en *{{2}}* y te extrañamos 😊. ¿Te gustaría agendar una cita? Responde *SI* y te ayudamos."
            }
        },
        "meta_name": "reactivacion_cliente",
    },
    {
        "friendly_name": "OlaApp - Confirmación Opt-Out",
        "language": "es",
        "variables": {"1": "Juan", "2": "Barbería El Patrón"},
        "types": {
            "twilio/text": {
                "body": "Hola {{1}}, hemos registrado tu solicitud. Ya no recibirás mensajes de *{{2}}*. Si cambias de opinión, escríbenos en cualquier momento. ¡Gracias!"
            }
        },
        "meta_name": "confirmacion_optout",
    },
]


def step3_create_content_templates():
    print("\n═══ PASO 3: Creando Content Templates en Twilio ═══")

    # Primero listar existentes para no duplicar
    try:
        existing = api_get(f"{CONTENT_API}/Content")
        existing_names = {
            c["friendly_name"]: c["sid"]
            for c in existing.get("contents", [])
        }
    except Exception:
        existing_names = {}

    created = {}
    for tpl in TEMPLATES:
        name = tpl["friendly_name"]
        if name in existing_names:
            print(f"  ⏭️  '{name}' ya existe (SID: {existing_names[name]})")
            created[tpl["meta_name"]] = existing_names[name]
            continue

        payload = {
            "friendly_name": name,
            "language": tpl["language"],
            "variables": tpl["variables"],
            "types": tpl["types"],
        }

        try:
            r = api_post(f"{CONTENT_API}/Content", json_body=payload)
            if r.status_code in (200, 201):
                data = r.json()
                sid = data["sid"]
                print(f"  ✅ Creado '{name}' → SID: {sid}")
                created[tpl["meta_name"]] = sid
            else:
                print(f"  ❌ Error creando '{name}': {r.status_code} — {r.text}")
        except Exception as e:
            print(f"  ❌ Excepción creando '{name}': {e}")

        time.sleep(0.5)  # Rate limiting

    if created:
        print("\n  📋 Mapeo content_sid para OlaApp:")
        for meta_name, sid in created.items():
            print(f"     {meta_name} → {sid}")

    return created


# ─── PASO 4: Configurar webhook ─────────────────────────────────────────

def step4_configure_webhook():
    print("\n═══ PASO 4: Configurando webhook para mensajes entrantes ═══")

    if not RAILWAY_BASE_URL:
        print("  ⚠️  RAILWAY_BASE_URL no configurada. Configúrala arriba y re-ejecuta.")
        print("  ℹ️  El webhook debe apuntar a:")
        print(f"      POST {RAILWAY_BASE_URL or '<TU_URL>'}/api/v1/webhooks/twilio")
        return False

    webhook_url = f"{RAILWAY_BASE_URL}/api/v1/webhooks/twilio"

    # Configurar en el número de teléfono (si es un número propio)
    phone_number = WHATSAPP_FROM.replace("whatsapp:", "")
    try:
        data = api_get(
            f"{BASE_API}/Accounts/{ACCOUNT_SID}/IncomingPhoneNumbers.json",
            params={"PhoneNumber": phone_number},
        )
        numbers = data.get("incoming_phone_numbers", [])

        if numbers:
            num_sid = numbers[0]["sid"]
            r = api_post(
                f"{BASE_API}/Accounts/{ACCOUNT_SID}/IncomingPhoneNumbers/{num_sid}.json",
                data={
                    "SmsUrl": webhook_url,
                    "SmsMethod": "POST",
                },
            )
            if r.status_code == 200:
                print(f"  ✅ Webhook configurado: {webhook_url}")
                return True
            else:
                print(f"  ❌ Error: {r.status_code} — {r.text}")
        else:
            print("  ⚠️  Número no encontrado como IncomingPhoneNumber.")
            print("  ℹ️  Si usas WhatsApp Sandbox, configura el webhook manualmente en:")
            print("      https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn")
            print(f"      URL: {webhook_url}")

    except Exception as e:
        print(f"  ❌ Error: {e}")

    return False


# ─── PASO 5: Mensaje de prueba ──────────────────────────────────────────

def step5_send_test_message():
    print("\n═══ PASO 5: Enviando mensaje de prueba ═══")

    if not TEST_PHONE:
        print("  ⚠️  TEST_PHONE no configurado. Configúralo arriba y re-ejecuta.")
        return False

    to_number = f"whatsapp:{TEST_PHONE}" if not TEST_PHONE.startswith("whatsapp:") else TEST_PHONE

    try:
        r = api_post(
            f"{BASE_API}/Accounts/{ACCOUNT_SID}/Messages.json",
            data={
                "From": WHATSAPP_FROM,
                "To": to_number,
                "Body": "🚀 ¡Hola! Este es un mensaje de prueba de OlaApp vía Twilio. Si recibes esto, la integración funciona correctamente. ✅",
            },
        )

        if r.status_code == 201:
            data = r.json()
            print(f"  ✅ Mensaje enviado — SID: {data['sid']}")
            print(f"  📱 De: {WHATSAPP_FROM}")
            print(f"  📱 A:  {to_number}")
            print(f"  📊 Status: {data['status']}")
            return True
        else:
            print(f"  ❌ Error: {r.status_code}")
            error = r.json()
            print(f"     Código: {error.get('code')}")
            print(f"     Mensaje: {error.get('message')}")
            if error.get("code") == 21608:
                print("\n  💡 NOTA: Para enviar desde el sandbox de Twilio,")
                print("     el destinatario debe unirse primero enviando")
                print("     el código de sandbox al número de Twilio.")
                print("     Ve a: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn")
            return False

    except Exception as e:
        print(f"  ❌ Excepción: {e}")
        return False


# ─── RESUMEN .env ────────────────────────────────────────────────────────

def print_env_summary(content_sids: dict = None):
    content_sids = content_sids or {}
    sid_lines = "\n".join(
        f"TWILIO_CONTENT_SID_{meta.upper()}={sid}"
        for meta, sid in content_sids.items()
    )
    print("\n═══ VARIABLES DE ENTORNO PARA .env / Railway ═══")
    print(f"""
# Twilio — credenciales
TWILIO_ACCOUNT_SID={ACCOUNT_SID}
TWILIO_API_KEY_SID={API_KEY_SID}
TWILIO_API_KEY_SECRET={API_KEY_SECRET}
TWILIO_WHATSAPP_NUMBER={WHATSAPP_FROM}
MESSAGING_PROVIDER=twilio

# Content SIDs de templates aprobados por WhatsApp
# (pega estos valores en Railway una vez que los templates sean APPROVED)
{sid_lines if sid_lines else "# (ningún template creado aún)"}

# Webhook URL — configúralo en Twilio Console → Messaging → Senders → WhatsApp:
# {RAILWAY_BASE_URL or '<TU_URL_RAILWAY>'}/api/v1/webhooks/twilio
""")


# ─── MAIN ────────────────────────────────────────────────────────────────

def main():
    print("🚀 OlaApp — Setup Twilio WhatsApp")
    print("=" * 55)

    if not step1_verify_connection():
        print("\n❌ No se pudo conectar. Verifica las credenciales.")
        sys.exit(1)

    step2_list_numbers()
    content_sids = step3_create_content_templates()
    step4_configure_webhook()
    step5_send_test_message()
    print_env_summary(content_sids)

    print("\n" + "=" * 55)
    print("✅ Setup completado. Revisa los mensajes arriba.")
    print("=" * 55)


if __name__ == "__main__":
    main()
