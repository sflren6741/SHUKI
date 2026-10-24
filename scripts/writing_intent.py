"""Explicit writing actions shared by saves, Files and scheduled monster work."""

EXPLICIT_CONSENT = 'explicit-v1'


def explicit_consent(entry):
    """Only newly saved, deliberately AI-submitted writing carries this marker."""
    return (entry.get('ai_consent') == EXPLICIT_CONSENT
            and entry.get('source') in ('home', 'journal')
            and entry.get('processing') == 'ai'
            and entry.get('ai_action') in ('request', 'monster', 'companion')
            and not entry.get('private') and entry.get('storage') != 'private')


def content_allowed(entry, is_private):
    """Keep legacy exclusions; explicit consent authorizes only this entry's text."""
    if (entry.get('processing') != 'ai' or entry.get('private')
            or entry.get('storage') == 'private'):
        return False
    return explicit_consent(entry) or not is_private(
        str(entry.get('text', '')) + ' ' + str(entry.get('theme', '')))


def validate_action(processing, value=None):
    if processing not in ('record', 'ai'):
        raise ValueError('Invalid processing mode')
    if processing == 'record':
        if value not in (None, ''):
            raise ValueError('Private saves cannot request an AI action')
        return ''
    if value is None:  # Legacy AI submissions are requests, never monster consent.
        return 'request'
    if value not in ('request', 'monster', 'companion'):
        raise ValueError('Invalid AI action')
    return value


def monster_requested(entry):
    """Metadata only: do not inspect private or record-only writing."""
    return (entry.get('source') in ('home', 'journal')
            and entry.get('processing') == 'ai'
            and entry.get('ai_action') == 'monster'
            and not entry.get('private') and entry.get('storage') != 'private')


def companion_requested(entry):
    """Live diary saving never implies a task, monster or encyclopedia request."""
    return (entry.get('source') in ('home', 'journal')
            and entry.get('processing') == 'ai'
            and entry.get('ai_action') == 'companion'
            and not entry.get('private') and entry.get('storage') != 'private')
