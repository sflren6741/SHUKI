"""Local CPU speech recognition; no paid provider, credentials or audio upload."""
import io
from pathlib import Path
import threading

import shuki_paths

MAX_AUDIO_BYTES = 15 * 1024 * 1024
MIME_TYPES = {'audio/webm', 'audio/ogg', 'audio/mp4', 'audio/wav', 'audio/x-wav'}
_MODEL = None
_LOCK = threading.Lock()


def transcribe(data, content_type, language='en'):
    """Download model weights on first use, then recognize clips locally.

    Keep the optional dependency lazy so the dashboard also boots without voice
    setup. Models are cached outside the repository and vault. Audio stays in
    memory and is never sent to a model provider.
    """
    global _MODEL
    mime = (content_type or '').split(';', 1)[0].strip().lower()
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_AUDIO_BYTES or mime not in MIME_TYPES:
        raise ValueError('Unsupported or empty audio clip (maximum 15 MB).')
    if language not in ('en', 'ja'):
        raise ValueError('Unsupported speech recognition language.')
    with _LOCK:
        if _MODEL is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise RuntimeError('Local voice setup is required: install faster-whisper==1.2.1 av==16.1.0 '
                                   'in the dashboard Python environment. See docs/SETUP.md.') from None
            cache = Path(shuki_paths.data_dir('speech')) / 'models'
            cache.mkdir(parents=True, exist_ok=True)
            try:
                _MODEL = WhisperModel('small', device='cpu', compute_type='int8', download_root=str(cache))
            except Exception:
                raise RuntimeError('Local speech model is unavailable. Complete the first model '
                                   'download with internet access, then retry explicitly.') from None
        try:
            segments, _ = _MODEL.transcribe(io.BytesIO(data), language=language, vad_filter=True)
            text = ''.join(segment.text for segment in segments).strip()
        except Exception:
            raise RuntimeError('Local speech recognition failed. Check the voice dependency versions in docs/SETUP.md and the audio clip; retry explicitly.') from None
    return {'text': text, 'provider': 'local', 'model': 'small'}
