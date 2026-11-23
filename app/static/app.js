/**
 * Supplier Saarthi - Client Application Logic (Person C - Day 2)
 * Voice Recording, Transcription, Extraction, Dynamic Confirmation & Offline Drafts
 */

(function () {
  'use strict';

  // ==========================================
  // 1. STATE & STORAGE MANAGEMENT
  // ==========================================
  const State = {
    recorder: null,
    audioChunks: [],
    audioBlob: null,
    isRecording: false,
    recordingTimerInterval: null,
    recordingSeconds: 0,
    currentKind: 'delivery', // 'delivery' or 'promise'
    currentRecord: null,
    readbackText: '',
    selectedMimeType: 'audio/webm',
  };

  // Keys for persistent storage
  const STORAGE_KEY_CURRENT = 'saarthi_current_record';
  const STORAGE_KEY_READBACK = 'saarthi_readback_text';
  const STORAGE_KEY_OFFLINE = 'saarthi_offline_drafts';

  function saveCurrentDraft(record, readback) {
    State.currentRecord = record;
    State.readbackText = readback || '';
    try {
      sessionStorage.setItem(STORAGE_KEY_CURRENT, JSON.stringify(record));
      sessionStorage.setItem(STORAGE_KEY_READBACK, State.readbackText);
    } catch (e) {
      console.warn('SessionStorage write error:', e);
    }
  }

  function loadCurrentDraft() {
    try {
      const rec = sessionStorage.getItem(STORAGE_KEY_CURRENT) || sessionStorage.getItem('munshi_current_record');
      const readback = sessionStorage.getItem(STORAGE_KEY_READBACK) || sessionStorage.getItem('munshi_readback_text');
      if (rec) {
        State.currentRecord = JSON.parse(rec);
        State.readbackText = readback || '';
        return State.currentRecord;
      }
    } catch (e) {
      console.warn('SessionStorage read error:', e);
    }
    return null;
  }

  function clearCurrentDraft() {
    State.currentRecord = null;
    State.readbackText = '';
    try {
      sessionStorage.removeItem(STORAGE_KEY_CURRENT);
      sessionStorage.removeItem(STORAGE_KEY_READBACK);
      sessionStorage.removeItem('munshi_current_record');
      sessionStorage.removeItem('munshi_readback_text');
    } catch (e) {}
  }

  function saveOfflineDraft(record) {
    try {
      const drafts = JSON.parse(localStorage.getItem(STORAGE_KEY_OFFLINE) || localStorage.getItem('munshi_offline_drafts') || '[]');
      record.saved_locally_at = new Date().toISOString();
      drafts.push(record);
      localStorage.setItem(STORAGE_KEY_OFFLINE, JSON.stringify(drafts));
      updateOfflineBanner();
    } catch (e) {
      console.error('Failed to save offline draft:', e);
    }
  }

  // ==========================================
  // 2. AUDIO RECORDER (MediaRecorder API)
  // ==========================================
  function getSupportedMimeType() {
    const types = [
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus',
      'audio/mp4',
      'audio/wav',
    ];
    for (const t of types) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported(t)) {
        return t;
      }
    }
    return ''; // browser default
  }

  function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }

  function startTimer(timerEl) {
    State.recordingSeconds = 0;
    if (timerEl) {
      timerEl.textContent = '00:00';
      timerEl.style.display = 'inline-block';
    }
    if (State.recordingTimerInterval) {
      clearInterval(State.recordingTimerInterval);
    }
    State.recordingTimerInterval = setInterval(() => {
      State.recordingSeconds++;
      if (timerEl) {
        timerEl.textContent = formatTime(State.recordingSeconds);
      }
    }, 1000);
  }

  function stopTimer(timerEl) {
    if (State.recordingTimerInterval) {
      clearInterval(State.recordingTimerInterval);
      State.recordingTimerInterval = null;
    }
    if (timerEl) {
      timerEl.style.display = 'none';
      timerEl.textContent = '00:00';
    }
  }

  async function startRecording(onStart, onStopCallback, onError, timerEl) {
    if (State.isRecording) return;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      onError('Aapka browser voice recording support nahi karta. Kripya Chrome ya Safari use karein.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      State.selectedMimeType = getSupportedMimeType();
      const options = State.selectedMimeType ? { mimeType: State.selectedMimeType } : {};

      State.recorder = new MediaRecorder(stream, options);
      State.audioChunks = [];

      State.recorder.ondataavailable = function (e) {
        if (e.data && e.data.size > 0) {
          State.audioChunks.push(e.data);
        }
      };

      State.recorder.onstop = function () {
        // Stop audio tracks immediately
        stream.getTracks().forEach((track) => track.stop());
        stopTimer(timerEl);

        const type = State.selectedMimeType || (State.audioChunks[0] ? State.audioChunks[0].type : 'audio/webm');
        State.audioBlob = new Blob(State.audioChunks, { type: type });
        State.isRecording = false;

        if (State.audioBlob.size < 100) {
          onError('Recording bahut choti thi ya awaaz nahi aayi. Dobara tap karein.');
          return;
        }

        onStopCallback(State.audioBlob);
      };

      State.recorder.onerror = function (e) {
        stream.getTracks().forEach((track) => track.stop());
        stopTimer(timerEl);
        State.isRecording = false;
        onError('Recorder error: ' + (e.error ? e.error.message : 'Unknown error'));
      };

      State.recorder.start();
      State.isRecording = true;
      startTimer(timerEl);
      if (onStart) onStart();
    } catch (err) {
      State.isRecording = false;
      stopTimer(timerEl);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        onError('Microphone permission blocked hai. Browser settings mein jakar Microphone "Allow" karein.');
      } else if (err.name === 'NotFoundError') {
        onError('Koi microphone nahi mila.');
      } else {
        onError('Microphone start nahi ho saka: ' + err.message);
      }
    }
  }

  function stopRecording() {
    if (State.recorder && State.recorder.state !== 'inactive') {
      State.recorder.stop();
    }
  }

  // ==========================================
  // 3. API CALLS: TRANSCRIBE, EXTRACT, SAVE
  // ==========================================
  async function apiTranscribe(audioBlob) {
    const formData = new FormData();
    const ext = State.selectedMimeType.includes('ogg')
      ? '.ogg'
      : State.selectedMimeType.includes('mp4')
      ? '.m4a'
      : State.selectedMimeType.includes('wav')
      ? '.wav'
      : '.webm';

    // Strictly field name 'audio'
    formData.append('audio', audioBlob, 'speech' + ext);

    const response = await fetch('/api/transcribe', {
      method: 'POST',
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Transcription failed (HTTP ' + response.status + ')');
    }
    return data.text;
  }

  async function apiExtract(transcriptText, kind) {
    const payload = {
      text: transcriptText,
      kind: kind || State.currentKind || 'delivery',
    };

    const response = await fetch('/api/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Extraction failed (HTTP ' + response.status + ')');
    }
    return data;
  }

  async function apiSaveRecord(record) {
    const response = await fetch('/api/records', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(record),
    });

    const data = await response.json();
    if (!response.ok) {
      const errMsg = (data.detail && data.detail.error) || data.error || 'Server error';
      throw new Error(errMsg);
    }
    return data;
  }

  // ==========================================
  // 4. TTS READ-BACK (Spoken audio)
  // ==========================================
  function speakSentence(text) {
    if (!window.speechSynthesis || !text) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.95;
      utterance.pitch = 1.0;
      // Try to find a Hindi or Indian English voice
      const voices = window.speechSynthesis.getVoices();
      const hiVoice = voices.find((v) => v.lang.includes('hi') || v.lang.includes('IN'));
      if (hiVoice) utterance.voice = hiVoice;
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn('Speech synthesis unavailable:', e);
    }
  }

  // ==========================================
  // 5. CONFIRMATION CARD BUILDER & RENDERER
  // ==========================================
  function renderConfirmationCard(container, data, options = {}) {
    if (!container) return;
    const record = data.record || data;
    const readback = data.readback_text || State.readbackText || '';
    const clarification = data.clarification || null;

    saveCurrentDraft(record, readback);

    let html = '';

    // Clarification Banner if any
    if (clarification) {
      html += `
        <div class="box-card clarification-card" style="border-left: 4px solid var(--warning); background: var(--warning-light); margin-bottom: 16px; padding: 14px 16px;">
          <div style="font-weight: 700; color: #b45309; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">
            <span>❓</span>
            <span>Clarification Zaroori Hai:</span>
          </div>
          <div style="font-size: 13px; color: #78350f; line-height: 1.4;">${escapeHtml(clarification)}</div>
        </div>
      `;
    }

    // Spoken Readback box
    if (readback) {
      html += `
        <div class="box-card" style="border-left: 4px solid var(--primary); background: #f0f7ff; margin-bottom: 16px; padding: 14px 16px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <div style="font-size: 13px; font-weight: 700; color: var(--primary); display: flex; align-items: center; gap: 6px;">
              <span>🗣️</span>
              <span>Bolkar Sunaya Ja Raha Hai (Audio Readback):</span>
            </div>
            <button type="button" id="btn-replay-tts" style="background: none; border: none; font-size: 18px; cursor: pointer; padding: 4px 8px; border-radius: 6px; transition: background 0.15s ease;" title="Dobara sunein">🔊 Replay</button>
          </div>
          <div id="readback-display" style="background: #ffffff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 10px 12px; font-weight: 600; font-size: 14px; color: #1e3a8a; line-height: 1.5;">
            "${escapeHtml(readback)}"
          </div>
        </div>
      `;
    }

    // Editable Record Form
    const isDelivery = record.record_type === 'DELIVERY_DISCREPANCY';

    html += `
      <div class="box-card" id="editable-record-card" style="margin-bottom: 16px; padding: 18px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid var(--border);">
          <div class="box-title" style="margin-bottom: 0;">📝 Record ke Fields (Editable)</div>
          <span style="font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 6px; ${isDelivery ? 'background: #fee2e2; color: #dc2626; border: 1px solid #fecaca;' : 'background: #fef3c7; color: #b45309; border: 1px solid #fde68a;'}">
            ${isDelivery ? 'DELIVERY CHECK' : 'PROMISE NOTE'}
          </span>
        </div>

        <!-- Supplier Selector -->
        <div class="form-group" style="margin-bottom: 14px;">
          <label class="form-label">Vyapari (Supplier):</label>
          <select id="confirm-supplier-id" class="form-select">
            <option value="">-- Vyapari Chunein --</option>
            <option value="1" ${record.supplier_id === 1 ? 'selected' : ''}>Sharma Distributors</option>
            <option value="2" ${record.supplier_id === 2 ? 'selected' : ''}>Gupta Wholesale</option>
            <option value="3" ${record.supplier_id === 3 ? 'selected' : ''}>Balaji Traders</option>
            <option value="4" ${record.supplier_id === 4 ? 'selected' : ''}>Kumar Provisions</option>
          </select>
        </div>

        <!-- Event Date -->
        <div class="form-group" style="margin-bottom: 14px;">
          <label class="form-label">Tareekh (Date):</label>
          <input type="date" id="confirm-event-date" class="form-input" value="${record.event_date || new Date().toISOString().split('T')[0]}">
        </div>
    `;

    if (isDelivery) {
      const lines = record.lines && record.lines.length > 0 ? record.lines : [createEmptyLine()];

      html += `<div id="delivery-lines-container">`;
      lines.forEach((line, idx) => {
        html += renderDeliveryLineHtml(line, idx);
      });
      html += `</div>`;
    } else {
      // Promise Note Fields
      html += `
        <div class="form-group" style="margin-bottom: 14px;">
          <label class="form-label">Wada Type (Promise Type):</label>
          <select id="confirm-promise-type" class="form-select">
            <option value="DISCOUNT" ${record.promise_type === 'DISCOUNT' ? 'selected' : ''}>DISCOUNT (Chhoot)</option>
            <option value="REPLACEMENT" ${record.promise_type === 'REPLACEMENT' ? 'selected' : ''}>REPLACEMENT (Maal Badlaav)</option>
            <option value="CREDIT_NOTE" ${record.promise_type === 'CREDIT_NOTE' ? 'selected' : ''}>CREDIT_NOTE (Credit / Paisa)</option>
            <option value="FREE_GOODS" ${record.promise_type === 'FREE_GOODS' ? 'selected' : ''}>FREE_GOODS (Free Maal)</option>
            <option value="CREDIT_PERIOD" ${record.promise_type === 'CREDIT_PERIOD' ? 'selected' : ''}>CREDIT_PERIOD (Udhaar Din)</option>
            <option value="PRICE_LOCK" ${record.promise_type === 'PRICE_LOCK' ? 'selected' : ''}>PRICE_LOCK (Bhav Fix)</option>
            <option value="OTHER" ${record.promise_type === 'OTHER' ? 'selected' : ''}>OTHER (Anya)</option>
          </select>
        </div>

        <div class="form-group" style="margin-bottom: 14px;">
          <label class="form-label">Saaman / Product Name:</label>
          <input type="text" id="confirm-promise-product" class="form-input" value="${escapeHtml(record.product_name || '')}" placeholder="Jaise: Tata Salt 1kg">
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 14px;">
          <div class="form-group">
            <label class="form-label">Value (Amount/Qty):</label>
            <input type="number" step="any" id="confirm-promise-value" class="form-input" value="${record.value !== null && record.value !== undefined ? record.value : ''}" placeholder="5 ya 500">
          </div>
          <div class="form-group">
            <label class="form-label">Value Type:</label>
            <select id="confirm-promise-value-type" class="form-select">
              <option value="PERCENT" ${record.value_type === 'PERCENT' ? 'selected' : ''}>PERCENT (%)</option>
              <option value="AMOUNT_RS" ${record.value_type === 'AMOUNT_RS' ? 'selected' : ''}>AMOUNT_RS (₹)</option>
              <option value="QUANTITY" ${record.value_type === 'QUANTITY' ? 'selected' : ''}>QUANTITY (Sankhya)</option>
              <option value="DAYS" ${record.value_type === 'DAYS' ? 'selected' : ''}>DAYS (Din)</option>
            </select>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 14px;">
          <div class="form-group">
            <label class="form-label">Applies To:</label>
            <select id="confirm-promise-applies" class="form-select">
              <option value="NEXT_ORDER" ${record.applies_to === 'NEXT_ORDER' ? 'selected' : ''}>NEXT_ORDER (Agli Baar)</option>
              <option value="DATE" ${record.applies_to === 'DATE' ? 'selected' : ''}>DATE (Tareekh Par)</option>
              <option value="NONE" ${record.applies_to === 'NONE' ? 'selected' : ''}>NONE</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Follow-up Date:</label>
            <input type="date" id="confirm-promise-date" class="form-input" value="${record.follow_up_date || ''}">
          </div>
        </div>
      `;
    }

    html += `
      </div> <!-- End editable-record-card -->

      <!-- Action Buttons: Haan and Galat -->
      <div id="confirm-action-group">
        <div class="confirm-btn-group" style="display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 12px; margin-bottom: 12px;">
          <button type="button" class="btn-haan" id="btn-confirm-haan" style="font-size: 15px; padding: 13px;">
            ✅ HAAN (Sahi Hai - Save Karein)
          </button>
          <button type="button" class="btn-galat" id="btn-confirm-galat" style="font-size: 15px; padding: 13px;">
            ✏️ EDIT / THEEK KAREIN
          </button>
        </div>

        <!-- Feedback message area -->
        <div id="save-status-msg" style="margin-top: 10px;"></div>

        <div class="disclaimer-text" style="margin-top: 12px;">
          ⚠️ <em>"Yeh ek record hai, kanooni saboot nahi."</em><br>
          Haan dabane par hi record OPEN banta hai.
        </div>
      </div>
    `;

    container.innerHTML = html;
    container.style.display = 'block';

    // Hook events
    const btnReplay = container.querySelector('#btn-replay-tts');
    if (btnReplay && readback) {
      btnReplay.onclick = () => speakSentence(readback);
      speakSentence(readback);
    }

    const btnHaan = container.querySelector('#btn-confirm-haan');
    if (btnHaan) {
      btnHaan.onclick = () => handleHaanSave(container);
    }

    const btnGalat = container.querySelector('#btn-confirm-galat');
    if (btnGalat) {
      btnGalat.onclick = () => handleGalatEdit(container);
    }
  }

  function createEmptyLine() {
    return {
      product_id: null,
      product_name: '',
      unit: 'carton',
      expected_qty: null,
      received_qty: null,
      shortage_qty: null,
      damaged_qty: null,
      issue: 'MISSING_QTY',
      issues: [{ type: 'MISSING_QTY', detail: null, qty: null, custom: false }],
      amount_diff_rs: null,
      note: null,
    };
  }

  // Render individual delivery product line with the FULL issues list
  function renderDeliveryLineHtml(line, idx) {
    const rawIssues = line.issues && line.issues.length > 0
      ? line.issues
      : [{ type: line.issue || 'MISSING_QTY', detail: null, qty: null, custom: false }];

    // Render issue chips
    let issueChipsHtml = '';
    rawIssues.forEach((iss, i) => {
      const isPrimary = i === 0;
      const isCustom = Boolean(iss.custom);
      issueChipsHtml += `
        <div class="issue-badge ${isPrimary ? 'issue-badge-primary' : 'issue-badge-secondary'} ${isCustom ? 'issue-badge-custom' : ''}">
          <span class="issue-type">${escapeHtml(iss.type)}</span>
          ${isPrimary ? '<span class="primary-tag">(Main)</span>' : ''}
          ${isCustom ? '<span class="custom-tag">[AI-made]</span>' : ''}
          ${iss.qty ? `<span class="issue-qty">• Qty: ${iss.qty}</span>` : ''}
          ${iss.detail ? `<span class="issue-detail">"${escapeHtml(iss.detail)}"</span>` : ''}
        </div>
      `;
    });

    return `
      <div class="line-item-card" data-line-idx="${idx}" style="background: #f8fafc; border: 1px solid var(--border); border-radius: 12px; padding: 14px; margin-bottom: 12px;">
        <div class="form-group" style="margin-bottom: 10px;">
          <label class="form-label">Saaman (Product Name):</label>
          <input type="text" class="form-input line-product-name" value="${escapeHtml(line.product_name || '')}" placeholder="Jaise: Maggi Noodles 70g">
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 10px;">
          <div class="form-group">
            <label class="form-label">Mangaya (Exp):</label>
            <input type="number" step="any" class="form-input line-expected-qty" value="${line.expected_qty !== null && line.expected_qty !== undefined ? line.expected_qty : ''}">
          </div>
          <div class="form-group">
            <label class="form-label">Aaya (Recv):</label>
            <input type="number" step="any" class="form-input line-received-qty" value="${line.received_qty !== null && line.received_qty !== undefined ? line.received_qty : ''}">
          </div>
          <div class="form-group">
            <label class="form-label">Unit:</label>
            <input type="text" class="form-input line-unit" value="${escapeHtml(line.unit || 'carton')}">
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px;">
          <div class="form-group">
            <label class="form-label">Kami (Short):</label>
            <input type="number" step="any" class="form-input line-shortage-qty" value="${line.shortage_qty !== null && line.shortage_qty !== undefined ? line.shortage_qty : ''}">
          </div>
          <div class="form-group">
            <label class="form-label">Kharab (Damaged):</label>
            <input type="number" step="any" class="form-input line-damaged-qty" value="${line.damaged_qty !== null && line.damaged_qty !== undefined ? line.damaged_qty : ''}">
          </div>
        </div>

        <!-- FULL ISSUES LIST (Task D Requirement) -->
        <div class="form-group" style="margin-bottom: 8px;">
          <label class="form-label" style="display: flex; justify-content: space-between; align-items: center;">
            <span>Detected Problems (All Issues):</span>
            <span style="font-size: 11px; color: var(--primary); font-weight: 600;">${rawIssues.length} issue(s)</span>
          </label>
          <div class="issues-container" style="display: flex; flex-direction: column; gap: 6px;">
            ${issueChipsHtml}
          </div>
        </div>

        <!-- Primary Issue Selector (Editable) -->
        <div class="form-group" style="margin-top: 8px;">
          <label class="form-label">Primary Issue (Mukhya Samasya):</label>
          <select class="form-select line-primary-issue">
            <option value="MISSING_QTY" ${line.issue === 'MISSING_QTY' ? 'selected' : ''}>MISSING_QTY (Maal Kam)</option>
            <option value="DAMAGED" ${line.issue === 'DAMAGED' ? 'selected' : ''}>DAMAGED (Toota-Phuta)</option>
            <option value="QUALITY" ${line.issue === 'QUALITY' ? 'selected' : ''}>QUALITY (Kharab / Keede / Geela)</option>
            <option value="WRONG_SKU" ${line.issue === 'WRONG_SKU' ? 'selected' : ''}>WRONG_SKU (Galat Saaman)</option>
            <option value="PRICE_MISMATCH" ${line.issue === 'PRICE_MISMATCH' ? 'selected' : ''}>PRICE_MISMATCH (Rate Galat)</option>
            <option value="INVOICE_MISMATCH" ${line.issue === 'INVOICE_MISMATCH' ? 'selected' : ''}>INVOICE_MISMATCH (Bill Galat)</option>
            <option value="OTHER" ${line.issue === 'OTHER' ? 'selected' : ''}>OTHER (Anya Samasya)</option>
          </select>
        </div>
      </div>
    `;
  }

  // ==========================================
  // 6. HAAN (SAVE) & GALAT (EDIT) HANDLERS
  // ==========================================
  async function handleHaanSave(container) {
    const statusMsg = container.querySelector('#save-status-msg');
    const btnHaan = container.querySelector('#btn-confirm-haan');
    const btnGalat = container.querySelector('#btn-confirm-galat');

    if (!State.currentRecord) {
      if (statusMsg) {
        statusMsg.innerHTML = '<div class="alert alert-danger">Koi record data nahi mila. Dobara bolein.</div>';
      }
      return;
    }

    // Collect updated field values
    const suppSelect = container.querySelector('#confirm-supplier-id');
    const suppId = suppSelect ? parseInt(suppSelect.value, 10) : null;
    const suppName = suppSelect && suppSelect.selectedOptions[0] ? suppSelect.selectedOptions[0].text : '';

    if (!suppId) {
      if (statusMsg) {
        statusMsg.innerHTML = '<div class="alert alert-warning" style="background:#fef3c7; color:#b45309; padding:10px; border-radius:8px; font-size:13px; font-weight:600;">⚠️ Kripya Vyapari (Supplier) chunein save karne ke liye.</div>';
      }
      if (suppSelect) suppSelect.focus();
      return;
    }

    State.currentRecord.supplier_id = suppId;
    State.currentRecord.supplier_name = suppName;

    const eventDateInput = container.querySelector('#confirm-event-date');
    if (eventDateInput && eventDateInput.value) {
      State.currentRecord.event_date = eventDateInput.value;
    }

    if (State.currentRecord.record_type === 'DELIVERY_DISCREPANCY') {
      const lineCards = container.querySelectorAll('.line-item-card');
      const lines = [];
      lineCards.forEach((card, idx) => {
        const existingLine = (State.currentRecord.lines && State.currentRecord.lines[idx]) || {};
        const pName = card.querySelector('.line-product-name').value;
        const expQty = parseFloat(card.querySelector('.line-expected-qty').value) || null;
        const recvQty = parseFloat(card.querySelector('.line-received-qty').value) || null;
        const shortQty = parseFloat(card.querySelector('.line-shortage-qty').value) || null;
        const damQty = parseFloat(card.querySelector('.line-damaged-qty').value) || null;
        const unit = card.querySelector('.line-unit').value || 'carton';
        const primaryIssue = card.querySelector('.line-primary-issue').value || 'MISSING_QTY';

        lines.push({
          ...existingLine,
          product_name: pName,
          expected_qty: expQty,
          received_qty: recvQty,
          shortage_qty: shortQty,
          damaged_qty: damQty,
          unit: unit,
          issue: primaryIssue,
          issues: existingLine.issues && existingLine.issues.length > 0
            ? existingLine.issues
            : [{ type: primaryIssue, detail: null, qty: shortQty || damQty, custom: false }],
        });
      });
      State.currentRecord.lines = lines;
    } else {
      // Promise fields update
      const pType = container.querySelector('#confirm-promise-type');
      const pProd = container.querySelector('#confirm-promise-product');
      const pVal = container.querySelector('#confirm-promise-value');
      const pValType = container.querySelector('#confirm-promise-value-type');
      const pApplies = container.querySelector('#confirm-promise-applies');
      const pDate = container.querySelector('#confirm-promise-date');

      if (pType) State.currentRecord.promise_type = pType.value;
      if (pProd) State.currentRecord.product_name = pProd.value;
      if (pVal) State.currentRecord.value = parseFloat(pVal.value) || null;
      if (pValType) State.currentRecord.value_type = pValType.value;
      if (pApplies) State.currentRecord.applies_to = pApplies.value || 'NONE';
      if (pDate && pDate.value) State.currentRecord.follow_up_date = pDate.value;
    }

    // Must be confirmed before saving
    State.currentRecord.confirmed = true;
    State.currentRecord.status = 'OPEN';

    if (btnHaan) {
      btnHaan.disabled = true;
      btnHaan.innerText = '⏳ Saving to Supabase...';
    }
    if (btnGalat) btnGalat.disabled = true;

    try {
      const saved = await apiSaveRecord(State.currentRecord);
      clearCurrentDraft();

      // Render vibrant success card
      container.innerHTML = `
        <div class="box-card" style="border-left: 5px solid var(--success); background: #f0fdf4; padding: 24px; text-align: center;">
          <div style="font-size: 48px; margin-bottom: 8px;">✅</div>
          <div style="font-size: 20px; font-weight: 800; color: #15803d; margin-bottom: 6px;">
            Record Safalta Se Save Ho Gaya!
          </div>
          <div style="font-size: 13px; color: #166534; margin-bottom: 16px;">
            Status: <strong>OPEN</strong> | Vyapari: <strong>${escapeHtml(saved.supplier_name || suppName)}</strong>
          </div>

          <div style="display: flex; flex-direction: column; gap: 10px; margin-top: 16px;">
            <a href="/timeline/${suppId}" class="btn-haan" style="text-decoration: none; padding: 13px; text-align: center; font-size: 14px;">
              📊 ${escapeHtml(suppName)} ki Timeline Dekhein
            </a>
            <a href="/delivery" class="form-input" style="text-decoration: none; padding: 13px; text-align: center; font-weight: 700; background: #ffffff;">
              ➕ Naya Record Banayein (Delivery Check)
            </a>
            <a href="/" style="font-size: 13px; color: var(--text-muted); text-decoration: underline; margin-top: 4px;">
              Home Screen Par Wapas Jayein
            </a>
          </div>
        </div>
      `;
    } catch (err) {
      console.warn('Backend save failed, saving as local offline draft:', err);
      saveOfflineDraft(State.currentRecord);

      if (btnHaan) {
        btnHaan.disabled = false;
        btnHaan.innerText = '🔄 Retry Server Save';
      }
      if (btnGalat) btnGalat.disabled = false;

      if (statusMsg) {
        statusMsg.innerHTML = `
          <div class="box-card" style="border-left: 4px solid var(--warning); background: var(--warning-light); margin-top: 10px; padding: 12px;">
            <div style="font-weight: 700; color: #b45309; margin-bottom: 4px;">
              ⚠️ Server Save Failed: ${escapeHtml(err.message)}
            </div>
            <div style="font-size: 12px; color: #78350f;">
              Aapka record <strong>Phone mein Offline Draft</strong> ke roop mein save kar liya gaya hai. Internet wapas aane par Retry karein.
            </div>
          </div>
        `;
      }
    }
  }

  function handleGalatEdit(container) {
    const card = container.querySelector('#editable-record-card');
    if (card) {
      card.scrollIntoView({ behavior: 'smooth' });
      const firstInput = card.querySelector('input, select');
      if (firstInput) firstInput.focus();
    }
  }

  // ==========================================
  // 7. PAGE INITIALIZERS & WORKFLOW BINDINGS
  // ==========================================
  function initDeliveryPage() {
    State.currentKind = 'delivery';
    const micBtn = document.getElementById('mic-btn');
    const micStatus = document.getElementById('mic-status');
    const recordingTimer = document.getElementById('recording-timer');
    const transcriptBox = document.getElementById('transcript-box');
    const textFallback = document.getElementById('text-fallback');
    const btnExtractText = document.getElementById('btn-extract-text');
    const confirmationContainer = document.getElementById('confirmation-card-area');

    if (!micBtn) return;

    micBtn.onclick = function () {
      if (State.isRecording) {
        stopRecording();
      } else {
        startRecording(
          function onStart() {
            micBtn.classList.add('recording');
            if (micStatus) micStatus.innerText = '🔴 Awaaz suni ja rahi hai... Tap to STOP';
            if (transcriptBox) transcriptBox.innerHTML = '<span style="color:var(--danger); font-weight:600;">Listening... (Boliye)</span>';
          },
          async function onStop(blob) {
            micBtn.classList.remove('recording');
            if (micStatus) micStatus.innerText = '⏳ Transcribing with Whisper...';
            if (transcriptBox) transcriptBox.innerHTML = '<em>Awaaz se text banaya ja raha hai...</em>';

            try {
              const text = await apiTranscribe(blob);
              if (transcriptBox) transcriptBox.innerText = `"${text}"`;
              if (textFallback) textFallback.value = text;
              if (micStatus) micStatus.innerText = '⏳ Extracting delivery details...';

              const extracted = await apiExtract(text, 'delivery');
              if (micStatus) micStatus.innerText = '✅ Extracted! Neeche confirm karein.';

              renderConfirmationCard(confirmationContainer, extracted);
              confirmationContainer.scrollIntoView({ behavior: 'smooth' });
            } catch (err) {
              if (micStatus) micStatus.innerText = 'Tap karein aur bolna shuru karein';
              if (transcriptBox) {
                transcriptBox.innerHTML = `
                  <div style="color: var(--danger); font-size: 13px; font-weight:600;">
                    ❌ Error: ${escapeHtml(err.message)}
                  </div>
                  <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                    Aap keyboard fallback box mein likhkar bhi proceed kar sakte hain.
                  </div>
                `;
              }
            }
          },
          function onError(errMsg) {
            micBtn.classList.remove('recording');
            if (micStatus) micStatus.innerText = 'Tap karein aur bolna shuru karein';
            alert('Mic Error: ' + errMsg);
          },
          recordingTimer
        );
      }
    };

    if (btnExtractText && textFallback) {
      btnExtractText.onclick = async function () {
        const text = textFallback.value.trim();
        if (!text) {
          alert('Kripya text box mein kuch likhein.');
          return;
        }
        btnExtractText.disabled = true;
        btnExtractText.innerText = '⏳ Processing...';
        try {
          const extracted = await apiExtract(text, 'delivery');
          renderConfirmationCard(confirmationContainer, extracted);
          confirmationContainer.scrollIntoView({ behavior: 'smooth' });
        } catch (err) {
          alert('Extraction error: ' + err.message);
        } finally {
          btnExtractText.disabled = false;
          btnExtractText.innerText = 'Extract Karein ➔';
        }
      };
    }
  }

  function initPromisePage() {
    State.currentKind = 'promise';
    const micBtn = document.getElementById('mic-btn-promise');
    const micStatus = document.getElementById('mic-status-promise');
    const recordingTimer = document.getElementById('recording-timer-promise');
    const transcriptBox = document.getElementById('transcript-box-promise');
    const textFallback = document.getElementById('text-fallback-promise');
    const btnExtractText = document.getElementById('btn-extract-promise-text');
    const confirmationContainer = document.getElementById('confirmation-card-area-promise');

    if (!micBtn) return;

    micBtn.onclick = function () {
      if (State.isRecording) {
        stopRecording();
      } else {
        startRecording(
          function onStart() {
            micBtn.classList.add('recording');
            if (micStatus) micStatus.innerText = '🔴 Wada suni ja rahi hai... Tap to STOP';
            if (transcriptBox) transcriptBox.innerHTML = '<span style="color:var(--danger); font-weight:600;">Listening... (Wada boliye)</span>';
          },
          async function onStop(blob) {
            micBtn.classList.remove('recording');
            if (micStatus) micStatus.innerText = '⏳ Transcribing with Whisper...';

            try {
              const text = await apiTranscribe(blob);
              if (transcriptBox) transcriptBox.innerText = `"${text}"`;
              if (textFallback) textFallback.value = text;
              if (micStatus) micStatus.innerText = '⏳ Extracting promise details...';

              const extracted = await apiExtract(text, 'promise');
              if (micStatus) micStatus.innerText = '✅ Wada record ho gaya! Neeche confirm karein.';

              renderConfirmationCard(confirmationContainer, extracted);
              confirmationContainer.scrollIntoView({ behavior: 'smooth' });
            } catch (err) {
              if (micStatus) micStatus.innerText = 'Wada bolne ke liye tap karein';
              if (transcriptBox) {
                transcriptBox.innerHTML = `<span style="color:var(--danger); font-weight:600;">Error: ${escapeHtml(err.message)}</span>`;
              }
            }
          },
          function onError(errMsg) {
            micBtn.classList.remove('recording');
            alert('Mic Error: ' + errMsg);
          },
          recordingTimer
        );
      }
    };

    if (btnExtractText && textFallback) {
      btnExtractText.onclick = async function () {
        const text = textFallback.value.trim();
        if (!text) return;
        btnExtractText.disabled = true;
        try {
          const extracted = await apiExtract(text, 'promise');
          renderConfirmationCard(confirmationContainer, extracted);
          confirmationContainer.scrollIntoView({ behavior: 'smooth' });
        } catch (err) {
          alert('Extraction error: ' + err.message);
        } finally {
          btnExtractText.disabled = false;
        }
      };
    }
  }

  function initConfirmationStandalonePage() {
    const container = document.getElementById('standalone-confirmation-area');
    if (!container) return;

    const existing = loadCurrentDraft();
    if (existing) {
      renderConfirmationCard(container, {
        record: existing,
        readback_text: State.readbackText,
      });
    } else {
      fetch('/static/mock/extract-delivery.json')
        .then((r) => r.json())
        .then((mock) => {
          renderConfirmationCard(container, mock);
        })
        .catch((e) => {
          container.innerHTML = '<div class="alert alert-warning" style="background:#fef3c7; color:#b45309; padding:12px; border-radius:8px;">Koi pending confirmation record nahi mila.</div>';
        });
    }
  }

  function updateOfflineBanner() {
    const headerStatus = document.querySelector('.header-status');
    if (!headerStatus) return;

    if (!navigator.onLine) {
      headerStatus.innerHTML = '<span class="status-dot" style="background:#f59e0b;"></span><span>Offline</span>';
      headerStatus.style.background = '#fef3c7';
      headerStatus.style.color = '#b45309';
    } else {
      headerStatus.innerHTML = '<span class="status-dot"></span><span>Online</span>';
      headerStatus.style.background = 'var(--success-light)';
      headerStatus.style.color = 'var(--success)';
    }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Auto-init on DOMContentLoaded
  document.addEventListener('DOMContentLoaded', function () {
    updateOfflineBanner();
    window.addEventListener('online', updateOfflineBanner);
    window.addEventListener('offline', updateOfflineBanner);

    initDeliveryPage();
    initPromisePage();
    initConfirmationStandalonePage();
  });

  // Export functions for testing & global access
  const appExport = {
    State,
    startRecording,
    stopRecording,
    apiTranscribe,
    apiExtract,
    apiSaveRecord,
    renderConfirmationCard,
    saveOfflineDraft,
    loadCurrentDraft,
    clearCurrentDraft,
  };

  window.SupplierSaarthiApp = appExport;
  window.MunshiApp = appExport; // Compatibility alias
})();
