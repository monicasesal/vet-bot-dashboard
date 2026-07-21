import os
from openai import OpenAI

#Inicializar el cliente de openAI pero apuntando a Groq gracias a mi variable del env
client = OpenAI(
    api_key=os.getenv('GROQ_API_KEY'),
    base_url=os.getenv('GROQ_BASE_URL')
)

def generar_respuesta_veterinaria(mensaje_usuario):
    try:
        respuesta = client.chat.completions.create(
            model='llama-3.1-8b-instant',
            messages=[
                {
                    'role': 'system',
                    'content': (
                        "Eres VetBot, un asistente virtual experto para una clínica veterinaria. "
                        "Tu tono es amable, empático y profesional. "
                        "Ayuda a los clientes con información sobre vacunas, citas, horarios y cuidados básicos. "
                        "REGLA CRUCIAL: Ante cualquier síntoma grave o de emergencia, debes recordarles "
                        "amablemente que no eres un veterinario de carne y hueso y recomendarles "
                        "traer a la mascota a la clínica de inmediato o llamar a su teléfono de urgencias."
                    )
                },
                {
                    'role': 'user',
                    'content': mensaje_usuario
                }
            ], temperature=0.7
        )

        return respuesta.choices[0].message.content
    
    except Exception as e:
        print("Error al hablar con la IA de Groq:", e)
        return "Lo siento, estoy teniendo un pequeño problema técnico. ¿Podrías repetir tu consulta?"