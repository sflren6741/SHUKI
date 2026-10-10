/* Continuous voice turns. The existing dock supplies rendering and local STT/TTS. */
const VOICE_LANGUAGE_LABELS = Object.freeze({en: 'English', ja: '日本語'});
const VOICE_WORK_CONFIRMATION_TOKENS = Object.freeze({en: 'start_work', ja: 'start_work_ja'});

class VoiceConversation {
  constructor(ui) {
    this.ui = ui;
    this.active = false;
    this.language = 'en';
    this.epoch = 0;
    this.turn = 0;
    this.pending = '';
    this.session = '';
    this.controllers = new Set();
    this.job = '';
    this.busy = false;
    this.transcribing = 0;
    this.sttQueue = Promise.resolve();
    this.proposal = null;
    this.work = null;
    this.workStarting = false;
    this.workSending = false;
    this.workSendError = '';
    this.notice = '';
    this.languageRevision = 0;
    this.noiseSamples = [];
    this.lookupApproval = null;
    this.speakingPractice = '';
    this.practiceSendReady = false;
  }
  state(text) { this.ui.state(text); }
  async request(url, options = {}, timeout = 95000, independent = false) {
    const ctl = new AbortController();
    if (!independent) this.controllers.add(ctl);
    const timer = setTimeout(() => ctl.abort(), timeout);
    try {
      const res = await fetch(url, {...options, signal: ctl.signal});
      const data = await res.json();
      if (!res.ok || data.error) throw new Error(data.error || `HTTP ${res.status}`);
      return data;
    } finally { clearTimeout(timer); this.controllers.delete(ctl); }
  }
  async start(session = '') {
    // Voice and the typed dock share one conversation: an existing session id is
    // carried in so switching input mode never starts a new thread.
    if (this.active) return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder || !this.ui.mime)
      return this.state('Voice recording is unavailable in this browser.');
    this.active = true;
    const epoch = ++this.epoch;
    this.language = 'en';
    this.pending = ''; this.session = session || ''; this.busy = false; this.job = ''; this.stopping = false;
    this.lookupApproval = null;
    this.transcribing = 0; this.sttQueue = Promise.resolve();
    this.ui.active(true);
    this.ui.language?.(this.language);
    this.state('Opening microphone…');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio: {
        echoCancellation: true, noiseSuppression: true, autoGainControl: true
      }});
      if (!this.active || epoch !== this.epoch) { stream.getTracks().forEach(t => t.stop()); return; }
      this.stream = stream;
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      this.audio = new AudioCtx();
      await this.audio.resume();
      if (!this.active || epoch !== this.epoch) return;
      this.analyser = this.audio.createAnalyser();
      this.analyser.fftSize = 2048;
      this.source = this.audio.createMediaStreamSource(stream);
      this.source.connect(this.analyser); // Never route microphone audio to speakers.
      this.samples = new Float32Array(this.analyser.fftSize);
      this.speaking = false; this.loudSince = 0; this.lastSpeech = performance.now();
      this.noiseSamples = [];
      this.record(epoch);
      this.tickTimer = setInterval(() => this.tick(epoch), 40);
      this.state('Listening');
    } catch (error) { if (epoch === this.epoch) this.fail(error); }
  }
  record(epoch) {
    if (!this.active || epoch !== this.epoch) return;
    const recorder = new MediaRecorder(this.stream, {mimeType: this.ui.mime});
    const language = this.language, revision = this.languageRevision;
    const chunks = [];
    this.recorder = recorder; this.clipSpeech = false; this.clipStart = performance.now();
    recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
    recorder.onerror = e => { if (epoch === this.epoch) this.fail(e.error || new Error('Recording failed')); };
    recorder.onstop = () => {
      if (!this.active || epoch !== this.epoch) return;
      const hasSpeech = this.clipSpeech;
      const blob = new Blob(chunks, {type: recorder.mimeType});
      this.record(epoch);
      if (hasSpeech && blob.size > 1000 && revision === this.languageRevision) this.transcribe(blob, epoch, language);
    };
    recorder.start();
  }
  tick(epoch) {
    if (!this.active || epoch !== this.epoch) return;
    this.analyser.getFloatTimeDomainData(this.samples);
    const rms = Math.sqrt(this.samples.reduce((n, x) => n + x*x, 0) / this.samples.length);
    const now = performance.now();
    // A rolling lower percentile follows steady room noise without following
    // individual loud peaks. Keep the user's selected pause unchanged.
    this.noiseSamples.push(rms);
    if (this.noiseSamples.length > 75) this.noiseSamples.shift();
    const levels = [...this.noiseSamples].sort((a, b) => a - b);
    const floor = levels[Math.floor((levels.length - 1) * 0.2)];
    const threshold = Math.max(0.025, floor * 2.5);
    if (rms > threshold) {
      if (!this.loudSince) this.loudSince = now;
      if (now - this.loudSince >= 160) {
        this.lastSpeech = now; this.clipSpeech = true;
        if (!this.speaking) {
          this.speaking = true;
          // Microphone activity may queue a follow-up, but must never cancel
          // an in-flight reply. Explicit typed/stop controls still interrupt.
          if (!this.busy) {
            this.interrupt();
            this.state('Listening — keep talking');
          }
        }
      }
    } else { this.loudSince = 0; }
    if (this.speaking && now - this.lastSpeech >= this.ui.pause()) {
      this.speaking = false;
      if (!this.busy) this.state('Transcribing…');
      if (this.recorder.state === 'recording') this.recorder.stop();
    } else if (this.recorder.state === 'recording' &&
               now - this.clipStart > (this.clipSpeech ? 30000 : 2000)) {
      // Limit idle audio and long turns. STT is serialized; long-turn text is merged.
      this.recorder.stop();
    }
    this.flush();
    if (this.notice && !this.speaking && !this.clipSpeech && !this.busy && !this.pending && !this.transcribing
        && now - this.lastSpeech >= this.ui.pause()) {
      const notice = this.notice; this.notice = '';
      this.ui.speak?.(notice, this.language);
    }
  }
  interrupt() {
    this.turn++;
    // Keep a displayed proposal through the confirmation utterance. flush()
    // decides whether the complete utterance authorizes, cancels, or abandons it.
    this.ui.stopSpeak();
    if (this.job && !this.stopping) {
      const id = this.job, epoch = this.epoch;
      this.stopping = true;
      // An exact ID is mandatory: never stop an unrelated dashboard job.
      this.request('/job-stop?id=' + encodeURIComponent(id), {}, 10000)
        .catch(e => { if (this.active && epoch === this.epoch && e.message !== 'not running') this.fail(e); })
        .finally(() => { if (epoch === this.epoch) this.stopping = false; });
    }
  }
  transcribe(blob, epoch, language = this.language) {
    const revision = this.languageRevision;
    if (++this.transcribing > 3) return this.fail(new Error('Transcription cannot keep up. Session stopped.'));
    this.sttQueue = this.sttQueue.then(async () => {
      if (!this.active || epoch !== this.epoch || revision !== this.languageRevision) return;
      const sttLanguage = language === 'ja' ? 'ja' : 'en';
      const data = await this.request('/stt?language=' + sttLanguage, {method: 'POST',
        headers: {'Content-Type': blob.type}, body: blob});
      if (!this.active || epoch !== this.epoch || revision !== this.languageRevision) return;
      const text = (data.text || '').trim();
      if (text) this.pending = [this.pending, text].filter(Boolean).join('\n');
      this.ui.draft(this.pending);
    }).catch(e => { if (this.active && epoch === this.epoch && revision === this.languageRevision) this.fail(e); })
      .finally(() => {
        if (epoch !== this.epoch) return;
        this.transcribing--;
        this.flush();
      });
  }
  sendTyped(text) {
    if (!text.trim()) return;
    if (this.speakingPractice) this.practiceSendReady = true;
    this.interrupt();
    this.pending = [this.pending, text.trim()].filter(Boolean).join('\n');
    this.flush();
  }
  sendPracticeAnswer() {
    if (!this.active || !this.speakingPractice || this.busy) return;
    this.practiceSendReady = true;
    if (this.clipSpeech && this.recorder?.state === 'recording') {
      this.speaking = false;
      this.recorder.stop();
    }
    this.flush();
  }
  detectLanguageCommand(text) {
    const compact = String(text || '').trim().toLowerCase()
      .replace(/[.,!?;:]+$/g, '').replace(/\s+/g, ' ');
    const switchTo = target => new RegExp(
      '^(?:please\\s+)?(?:switch|change|set)\\s+(?:the\\s+)?(?:active\\s+)?'
      + '(?:language\\s+)?to\\s+' + target + '(?:\\s+(?:only|mode))?$');
    const respondIn = target => new RegExp(
      '^(?:please\\s+)?(?:use|speak|respond|reply|answer|talk|interpret)\\s+'
      + '(?:in\\s+)?' + target + '(?:\\s+(?:only|mode))?$');
    if (switchTo('english').test(compact) || respondIn('english').test(compact)
        || /^english(?:\s+(?:only|mode))?$/.test(compact)) return 'en';
    if (switchTo('japanese').test(compact) || respondIn('japanese').test(compact)
        || /^japanese(?:\s+(?:only|mode))?$/.test(compact)) return 'ja';

    const japanese = String(text || '').trim()
      .replace(/[。！？!?、,，．.]+$/g, '').replace(/\s+/g, '');
    const japaneseCommand = term => new RegExp(
      '^(?:' + term + ')(?:(?:に)?切り替えて?|にして|で(?:話して|答えて|返して|応答して|お願いします)'
      + '|(?:だけ|のみ)(?:で)?|モード|でお願いします)?$');
    if (japaneseCommand('英語|えいご').test(japanese)) return 'en';
    if (japaneseCommand('日本語|にほんご').test(japanese)) return 'ja';
    return '';
  }
  handleLanguageCommand(text) {
    const language = this.detectLanguageCommand(text);
    if (!language) return false;
    this.setLanguage(language);
    this.pending = '';
    this.ui.draft('');
    this.ui.language?.(language);
    const confirmation = language === 'ja' ? '日本語に切り替えました。' : 'English selected.';
    this.ui.user?.(text);
    const reply = this.ui.reply?.();
    if (reply) this.ui.render(reply, confirmation);
    this.ui.speak?.(confirmation, language, true);
    this.state('Listening — ' + VOICE_LANGUAGE_LABELS[language]);
    return true;
  }
  setLanguage(language) {
    if (!['en', 'ja'].includes(language)) return;
    this.interrupt(); this.languageRevision++;
    this.language = language; this.pending = ''; this.ui.draft('');
    this.ui.language?.(language);
    if (this.recorder?.state === 'recording') this.recorder.stop();
  }
  normalizeWorkCommand(text) {
    return String(text || '').trim().toLowerCase()
      .replace(/[.,!?;:]+/g, ' ').replace(/\s+/g, ' ').trim();
  }
  confirmation(text) {
    const compact = this.normalizeWorkCommand(text).replace(/[。！？、]/g, '').replace(/\s+/g, '');
    if (['yes', 'yesplease', 'ok', 'okay', 'soundsgood', 'goahead', 'doitnow', 'doitnowok',
         'continue', 'pleasecontinue', 'はい', 'はいお願いします', 'お願いします', '進めて',
         '続けて', '調べて'].includes(compact)) return 'yes';
    if (['no', 'nothanks', 'notnow', 'cancel', 'いいえ', '今はいい', 'やめて', 'キャンセル'].includes(compact)) return 'no';
    return '';
  }
  detectWorkCommand(text) {
    const compact = this.normalizeWorkCommand(text);
    const startPatterns = [
      /^(?:please\s+)?(?:start|begin|proceed|go ahead|do it)(?:\s+please)?$/,
      /^(?:(?:yes|okay|ok)\s+)?(?:start|begin)\s+(?:(?:the|this|approved|proposed)\s+)?(?:work|task|proposal)$/,
      /^(?:(?:yes|okay|ok)\s+)?execute\s+(?:(?:the|this|approved|proposed)\s+)?(?:work|task|proposal)$/,
      /^(?:approve|confirm)\s+and\s+(?:start|begin|execute)\s+(?:(?:the|this|approved|proposed)\s+)?(?:work|task|proposal)$/
    ];
    if (startPatterns.some(pattern => pattern.test(compact))) return 'start';
    if (new Set([
      'cancel proposal', 'cancel the proposal', 'discard proposal',
      'discard the proposal', 'cancel work proposal', 'not now'
    ]).has(compact)) return 'cancel';
    if (new Set([
      'yes', 'yes please', 'okay', 'ok', 'do that',
      'continue', 'execute', 'please do that'
    ]).has(compact)) return 'unclear';

    const japanese = String(text || '').trim()
      .replace(/[。！？!?、,，．.]+$/g, '').replace(/\s+/g, '');
    if ([
      '作業開始', '作業を開始', '作業を開始して', '作業を開始してください',
      'この作業を開始して', 'タスクを開始して', 'タスクを実行して',
      'このタスクを実行して', 'これを実行して', '提案を実行して',
      '承認して実行して', '開始', '開始して', '進めて', '実行して'
    ].includes(japanese)) return 'start';
    if (['提案をキャンセル', '提案を破棄', '作業をキャンセル', '今はやめて'].includes(japanese))
      return 'cancel';
    if (['はい', 'はいお願いします', 'お願いします', '進めて', 'これで', 'やって', '実行', '開始'].includes(japanese))
      return 'unclear';
    return '';
  }
  clearProposal() {
    this.proposal = null;
    this.ui.proposal?.(null);
  }
  renderWork(extra = {}) {
    this.ui.work?.(this.work ? {...this.work, ...extra, sending:this.workSending, send_error:this.workSendError} : null);
  }
  async sendWork(text, approved = false, approvalMethod = 'click') {
    if (!this.work?.id) throw new Error('No work selected. Discuss a proposal first.');
    const question = this.work.question;
    if (question && this.work.status !== 'waiting') throw new Error('The worker is still finishing its turn.');
    if (question?.kind === 'scope' && !approved)
      throw new Error('Review the revised scope and say the exact start command or click Start revised work.');
    if (this.workSending) throw new Error('A work message is already being sent.');
    const method = approved && approvalMethod === 'voice' ? 'voice' : 'click';
    const confirmation = method === 'voice' ? VOICE_WORK_CONFIRMATION_TOKENS[this.language] : '';
    // Retain the ID on ambiguous network errors, so a manual resend cannot duplicate execution.
    if (!this.outgoing || this.outgoing.text !== text || this.outgoing.id !== this.work.id
        || this.outgoing.question_id !== (question?.id || '') || this.outgoing.approved !== approved
        || this.outgoing.approval_method !== method)
      this.outgoing = {action:'message', id:this.work.id, text,
        message_id: Date.now().toString(36) + '-' + Math.random().toString(36).slice(2),
        question_id: question?.id || '', approved, approval_method: method, confirmation};
    this.workSending = true;
    this.workSendError = '';
    this.renderWork();
    try {
      const result = await this.workRequest(this.outgoing);
      this.outgoing = null;
      await this.pollWork();
      return result;
    } catch (error) {
      this.workSendError = 'Send failed: ' + error.message + ' Your text is kept; retry to confirm delivery.';
      throw error;
    } finally {
      this.workSending = false;
      this.renderWork();
    }
  }
  async approveScope(approvalMethod = 'click') {
    if (this.workStarting || this.work?.question?.kind !== 'scope') return;
    this.workStarting = true;
    try { await this.sendWork(this.work.question.text, true, approvalMethod); return true; }
    catch (error) { this.workSendError ||= error.message; this.renderWork(); return false; }
    finally { this.workStarting = false; }
  }
  async replyToWork() {
    const text = this.ui.workReply?.()?.trim();
    if (!text || this.workStarting) return;
    this.workStarting = true;
    try { await this.sendWork(text); this.ui.clearWorkReply?.(); }
    catch (error) { this.workSendError ||= error.message; this.renderWork(); }
    finally { this.workStarting = false; }
  }
  async flush() {
    if (this.speakingPractice && !this.practiceSendReady) return;
    if (!this.active || this.busy || this.workStarting || this.speaking || this.clipSpeech || this.transcribing || !this.pending ||
        performance.now() - this.lastSpeech < this.ui.pause()) return;
    const text = this.pending;
    this.practiceSendReady = false;
    if (this.handleLanguageCommand(text)) return;
    this.busy = true;
    const epoch = this.epoch, turn = this.turn, language = this.language;
    this.pending = ''; this.ui.draft('');
    this.ui.user(text);
    const reply = this.ui.reply();
    this.state('Thinking — you can keep talking');
    let completed = false;
    try {
      let lookupSource = '';
      if (this.lookupApproval) {
        const approval = this.lookupApproval;
        this.lookupApproval = null; // Only the direct reply can approve this lookup.
        const decision = this.confirmation(text);
        if (decision === 'no') {
          const message = language === 'ja' ? 'わかりました。調査はここで止めます。' : 'Okay, I’ll leave the lookup there.';
          this.ui.render(reply, message); this.ui.speak?.(message, language); return;
        }
        if (decision === 'yes') {
          if (approval.expires_at <= Date.now() / 1000) {
            const message = 'That lookup confirmation expired. Please tell me what to check again.';
            this.ui.render(reply, message); this.ui.speak?.(message, language); return;
          }
          lookupSource = approval.id;
        }
      }
      if (!this.speakingPractice && ['running', 'waiting'].includes(this.work?.status)) {
        const command = text.trim().replace(/[.!。！]+$/g, '').toLowerCase();
        if (['stop working', 'stop work', 'pause work', '作業を止めて', '作業停止', '実装を止めて'].includes(command)) {
          const stopped = await this.stopWork();
          this.ui.render(reply, stopped ? 'Stop requested. Waiting for a tool boundary.'
            : 'Stop could not be confirmed. Check the work card.');
          return;
        }
      }
      let workCommand = this.speakingPractice ? '' : this.detectWorkCommand(text);
      const shortApproval = !this.speakingPractice && this.confirmation(text) === 'yes';
      if (this.proposal?.awaitingApproval && shortApproval) workCommand = 'start';
      if (this.proposal) this.proposal.awaitingApproval = false;
      if (!lookupSource && workCommand === 'start') {
        let started = false;
        if (this.work?.status === 'waiting' && this.work.question?.kind === 'scope') {
          started = await this.approveScope('voice');
        } else if (this.proposal) {
          started = await this.startWork('voice');
        } else {
          const message = this.work?.status === 'running'
            ? 'Work is already running. I did not start another job.'
            : 'There is no pending work proposal. Say what you want to do first.';
          this.ui.render(reply, message); this.ui.speak?.(message, language, true); return;
        }
        const message = started ? 'Confirmed. Starting the approved work.'
          : 'The work was not started. Check the work card for details.';
        this.ui.render(reply, message); this.ui.speak?.(message, language, true); return;
      }
      if (workCommand === 'cancel') {
        if (this.proposal) {
          this.clearProposal();
          const message = 'The pending work proposal was cancelled.';
          this.ui.render(reply, message); this.ui.speak?.(message, language, true); return;
        }
        const message = 'There is no pending work proposal to cancel.';
        this.ui.render(reply, message); this.ui.speak?.(message, language, true); return;
      }
      if (!lookupSource && this.proposal && workCommand === 'unclear') {
        const rendered = 'I did not start anything. Say “start work” to run the displayed proposal, or say “cancel proposal”.';
        const spoken = language === 'ja'
          ? '提案はまだ実行していません。画面に表示された開始コマンドを言うか、提案をキャンセルしてください。'
          : 'I did not start anything. Repeat the exact start command shown on screen, or cancel the proposal.';
        this.ui.render(reply, rendered); this.ui.speak?.(spoken, language, true); return;
      }
      // Do not abort submission on session stop: receive its ID and cancel exactly that job.
      const discussion = this.proposal
        ? text + '\n\nCurrent displayed proposal (reference only; retain unless the user requests a scope change):\n' + this.proposal.summary
        : text;
      const res = await fetch('/exec?voice=1&text=' + encodeURIComponent(discussion)
        + '&session=' + encodeURIComponent(this.session) + '&label=Voice%20conversation'
        + '&voice_lang=' + encodeURIComponent(language)
        + '&lookup_source=' + encodeURIComponent(lookupSource)
        + '&work=' + encodeURIComponent(this.speakingPractice ? '' : this.work?.id || '')
        + '&ielts=' + encodeURIComponent(this.speakingPractice));
      const started = await res.json();
      if (!res.ok || started.error) throw new Error(started.error || `HTTP ${res.status}`);
      const id = started.job;
      if (!id) throw new Error('Missing voice job ID');
      if (!this.active || epoch !== this.epoch) {
        await fetch('/job-stop?id=' + encodeURIComponent(id)); return;
      }
      this.ui.model?.(started.model);
      this.job = id;
      if (turn !== this.turn) this.interrupt();
      const deadline = performance.now() + 180000;
      const waitingSince = performance.now();
      let waitingNotice = false;
      while (this.active && epoch === this.epoch) {
        const data = await this.request('/job?id=' + encodeURIComponent(id), {}, 10000);
        if (!this.active || epoch !== this.epoch) return;
        this.ui.model?.(data.model);
        if (data.status === 'running') {
          if (turn === this.turn && data.voice_activity) this.state(data.voice_activity);
          if (turn === this.turn && data.partial)
            this.ui.render(reply, data.partial.split(/\n?VOICE_(?:WORK|LOOKUP|SEND):/)[0]);
          if (!waitingNotice && turn === this.turn && performance.now() - waitingSince >= 10000
              && !this.speaking && !this.clipSpeech && !this.pending && !this.transcribing) {
            waitingNotice = true;
            const message = language === 'ja' ? '返答に少し時間がかかっています。' : 'My reply is taking a little longer.';
            this.state(message);
            this.ui.speak?.(message, language);
          }
          if (performance.now() > deadline) throw new Error('Reply timed out. Session stopped.');
          await new Promise(resolve => setTimeout(resolve, 300));
          continue;
        }
        if (data.session) { this.session = data.session; this.ui.session?.(data.session); }
        if (data.status === 'error') throw new Error(data.result || 'Reply failed');
        completed = true;
        const interrupted = turn !== this.turn || data.status === 'stopped';
        this.ui.render(reply, interrupted ? 'Interrupted' : (data.result || 'No reply received.'));
        if (!interrupted && data.sources?.length) this.ui.sources?.(reply, data.sources);
        if (!interrupted && data.lookup_pending) {
          this.lookupApproval = {id, expires_at: data.lookup_expires_at};
          if (this.proposal) this.proposal.awaitingApproval = false;
        }
        if (!interrupted && data.voice_relay) {
          const relay = data.voice_relay;
          // Never send a delayed decision to a different work item or a newer question.
          if (relay.work_id !== this.work?.id || relay.question_id !== (this.work?.question?.id || '')) {
            this.ui.render(reply, 'The work changed while we were talking. Please repeat that instruction.');
          } else {
            try {
              await this.sendWork(text);
              if (this.active && epoch === this.epoch && turn === this.turn) {
                this.ui.render(reply, 'Added to the work. You can keep talking.');
                this.ui.speak?.('Added to the work.', language);
              }
            } catch (error) { this.ui.render(reply, 'That update was not confirmed: ' + error.message); }
          }
          break;
        }
        if (!interrupted && data.proposal && this.work?.status !== 'running' && !this.workStarting) {
          const previous = this.proposal?.summary || '';
          const changed = previous !== data.proposal;
          const before = previous.split('\n').filter(Boolean);
          const after = data.proposal.split('\n').filter(Boolean);
          const changes = previous && changed
            ? [...before.filter(line => !after.includes(line)).map(line => 'Removed: ' + line),
               ...after.filter(line => !before.includes(line)).map(line => 'Added: ' + line)].join('\n') : '';
          this.proposal = {id, summary: data.proposal, previous, changes,
            awaitingApproval: true, expires_at: data.proposal_expires_at || 0};
          this.ui.proposal?.(this.proposal);
        }
        if (!interrupted && (data.result || data.proposal)) {
          const hint = data.proposal
            ? (language === 'ja'
              ? '内容がまとまりました。この内容で実行しましょうか？'
              : 'The plan is ready. Shall I carry it out?')
            : '';
          this.ui.speak([data.result, hint].filter(Boolean).join(' '), language);
        }
        break;
      }
    } catch (error) {
      if (this.active && epoch === this.epoch) {
        if (error.message === 'busy') {
          const message = language === 'ja'
            ? 'この会話では別の返答を生成中です。終了後にもう一度話してください。'
            : 'A reply is already running in this conversation. Wait for it to finish, then send your message again.';
          this.ui.render(reply, message);
          this.ui.speak?.(message, language);
        } else this.fail(error);
      }
    } finally {
      if (epoch === this.epoch) {
        this.job = ''; this.busy = false;
        if (this.active) {
          // Preserve the unfinished user turn if no session was established before cancellation.
          if (completed && turn !== this.turn && !this.session)
            this.pending = [text, this.pending].filter(Boolean).join('\n');
          this.state(this.speaking ? 'Listening — keep talking' : 'Listening');
          this.flush();
        }
      }
    }
  }
  workRequest(data) {
    return this.request('/voice-work', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data)}, 15000, true);
  }
  async startWork(approvalMethod = 'click') {
    if (!this.proposal || this.workStarting || this.work?.status === 'running') return;
    const proposal = this.proposal;
    this.workStarting = true;
    this.ui.proposal?.({...proposal, starting: true});
    this.ui.rememberWork?.('source', proposal.id);
    try {
      const request = {action: 'start', id: proposal.id, approved: true};
      if (approvalMethod === 'voice') {
        request.approval_method = 'voice';
        request.confirmation = VOICE_WORK_CONFIRMATION_TOKENS[this.language];
      }
      const data = await this.workRequest(request);
      this.work = {id: data.job, status: 'running', scope: proposal.summary, model: data.model};
      this.workSendError = '';
      this.ui.rememberWork?.('job', data.job);
      this.proposal = null;
      this.ui.proposal?.(null);
      this.renderWork();
      this.pollWork();
      return true;
    } catch (error) {
      // The server makes Start idempotent. A repeated click or voice command checks the same proposal.
      if (/expired|no longer available/i.test(error.message || '')) this.clearProposal();
      else {
        this.proposal = proposal;
        this.ui.proposal?.({...proposal, error: 'Start could not be confirmed: ' + error.message});
      }
      return false;
    } finally { this.workStarting = false; }
  }
  async pollWork() {
    clearTimeout(this.workTimer);
    if (!this.work) return;
    const id = this.work.id;
    try {
      const data = await this.request('/job?id=' + encodeURIComponent(id), {}, 10000, true);
      if (id !== this.work?.id) return;
      this.work = {...this.work, ...data};
      delete this.work.error;
      this.renderWork();
      const noticeKey = id + ':' + data.work_turn + ':' + data.status;
      if (noticeKey !== this.lastNotice && ['waiting', 'done', 'error', 'stopped'].includes(data.status)
          && !(['done', 'waiting'].includes(data.status) && data.resume_ready === false)) {
        this.lastNotice = noticeKey;
        const notice = data.status === 'waiting' ? (data.question?.text || 'There is a question about the work. You can answer here.')
          : data.status === 'done' ? 'Work finished. The result is ready to review.' : 'Work ' + data.status + '. Check the work card.';
        this.ui.notice?.(notice);
        if (this.active) this.notice = notice;
      }
      if (data.status === 'running') this.workTimer = setTimeout(() => this.pollWork(), 1000);
      else if (['done', 'waiting'].includes(data.status) && data.resume_ready === false)
        this.workTimer = setTimeout(() => this.pollWork(), 1000);
      this.ui.rememberWork?.('job', id);
    } catch (error) {
      if (id !== this.work?.id) return;
      // 'unknown job' はサーバーのジョブ台帳（インメモリ）にIDが無い＝サーバー再起動等で
      // 二度と復旧しない状態。持ち越しても毎回同じエラーを出すだけで畳めなくなるため
      // （2026-09-14）、ここで諦めて記憶を消し、カード自体を閉じる。
      if (error.message === 'unknown job') {
        this.work = null;
        this.ui.rememberWork?.();
        this.ui.work?.(null);
      } else {
        this.renderWork({error: 'Work status unavailable: ' + error.message});
      }
    }
  }
  async restoreWork(saved) {
    if (!saved?.id) return;
    try {
      let id = saved.id;
      if (saved.kind === 'source') {
        const source = await this.request('/job?id=' + encodeURIComponent(id), {}, 10000, true);
        if (!source.work_id) throw new Error('Start was not recorded. Discuss the work again.');
        id = source.work_id;
      }
      this.work = {id, status: 'running'};
      await this.pollWork();
    } catch (error) {
      // 復旧不能（プロポーザルの出所も消えている）。同じく記憶を消してカードを閉じる。
      this.work = null;
      this.ui.rememberWork?.();
      this.ui.work?.(null);
    }
  }
  async stopWork() {
    if (!this.work || !['running', 'waiting'].includes(this.work.status)) return false;
    if (this.work.stop_requested) return true;
    const id = this.work.id;
    try {
      const data = await this.workRequest({action: 'stop', id});
      if (id !== this.work?.id) return;
      if (data.finished) { await this.pollWork(); return true; }
      this.work.stop_requested = true;
      this.renderWork();
      return true;
    } catch (error) {
      this.renderWork({error: 'Stop was not confirmed: ' + error.message});
      return false;
    }
  }
  fail(error) { this.end(); this.state(String(error.message || error)); }
  end() {
    this.practiceSendReady = false;
    this.notice = '';
    this.lookupApproval = null;
    this.active = false; this.epoch++; this.turn++;
    clearInterval(this.tickTimer);
    this.ui.stopSpeak();
    if (!this.workStarting) { this.proposal = null; this.ui.proposal?.(null); }
    if (this.job) fetch('/job-stop?id=' + encodeURIComponent(this.job)).catch(() => {});
    this.job = '';
    for (const ctl of this.controllers) ctl.abort();
    this.controllers.clear();
    if (this.recorder?.state === 'recording') this.recorder.stop();
    this.stream?.getTracks().forEach(t => t.stop());
    this.source?.disconnect();
    if (this.audio && this.audio.state !== 'closed') this.audio.close().catch(() => {});
    this.ui.active(false);
    this.state('Microphone off');
  }
}
