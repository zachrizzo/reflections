# Hosted NPC dialogue relay. Build context: Tools/RealtimeVoice. Not deployed; see ArtDirection/NpcDialogue/README.md.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY api_keys.py openai_key.py persona.py reply_cache.py voices.json composing.py decider.py costs.py gemini.py \
     tts.py actions.py pipeline.py relay.py hosted_relay.py ./
ENV PYTHONUNBUFFERED=1 REFLECTIONS_NPC_DATA_DIR=/data PORT=8080
EXPOSE 8080
RUN useradd --create-home relay && mkdir -p /data && chown relay /data
USER relay
CMD ["python", "hosted_relay.py"]
