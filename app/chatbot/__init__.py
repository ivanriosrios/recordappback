"""
Módulo chatbot de RecordApp — motor de agendamiento conversacional por WhatsApp.

Este módulo es self-contained (no importa de api/, tasks/).
Comunica con el resto del sistema a través de modelos y la capa de mensajería.

Punto de entrada:
    from app.chatbot.engine import ChatbotEngine
    engine = ChatbotEngine(session)
    engine.handle_message(phone="+573001234567", text="Hola")
"""
from app.chatbot.engine import ChatbotEngine

__all__ = ["ChatbotEngine"]
