class SpeechService:
    """Whisper adapter for elderly voice response recognition."""

    def transcribe(self, audio_path: str | None = None) -> dict:
        if not audio_path:
            return {
                "transcript": "",
                "intent": "none",
                "source": "demo_microphone",
            }

        try:
            import whisper

            model = whisper.load_model("base")
            result = model.transcribe(audio_path, fp16=False)
            transcript = str(result.get("text") or "").strip()
            return {
                "transcript": transcript,
                "intent": self._infer_intent(transcript),
                "source": audio_path,
                "model": "whisper-base",
            }
        except Exception as exc:
            return {
                "transcript": "",
                "intent": "none",
                "source": audio_path,
                "error": f"Whisper unavailable: {exc}",
            }

    def _infer_intent(self, transcript: str) -> str:
        text = transcript.lower()
        if not text:
            return "none"

        safe_words = [
            "没事",
            "不用",
            "安全",
            "我很好",
            "我没事",
            "i am ok",
            "i'm ok",
            "fine",
            "okay",
            "ok",
        ]
        help_words = [
            "救命",
            "疼",
            "痛",
            "不能动",
            "需要帮助",
            "help",
            "pain",
            "hurt",
            "can't move",
            "cannot move",
        ]

        if any(word in text for word in help_words):
            return "help"
        if any(word in text for word in safe_words):
            return "safe"
        return "unknown"
