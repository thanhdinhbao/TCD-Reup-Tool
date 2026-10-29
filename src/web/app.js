// TCD REUP TOOL — Webview Frontend Controller

let appState = {
  active_project: '',
  projects: [],
  channels: [],
  threads: 500,
  use_proxy: false,
  proxy_region: 'IP - Nhật Bản',
  auto_upload_tiktok: true,
  only_shorts: true,
  telegram_enabled: false,
  telegram_token: '',
  telegram_chat_ids: [],
  pool_total: 0,
  pool_remaining: 0,
  dead_keys_count: 0,
  schedule: [],
  schedule_mode: 'multi',
  tiktok_config: {
    channels_config: {},
    profiles: [],
    upload_timeout: 30,
    next_video_delay: 180,
    caption_mode: 'keep_title'
  },
  gpm_profiles: [],
  is_running: false
};

// ==========================================
// INITIALIZATION
// ==========================================

function waitForPywebview(callback) {
  if (window.pywebview && window.pywebview.api) {
    callback();
  } else {
    window.addEventListener('pywebviewready', callback);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  setupModalHandlers();
  setupUIEventListeners();

  waitForPywebview(async () => {
    appendLog('🚀 Hệ thống TCD REUP TOOL đã sẵn sàng kết nối Python backend.');
    await refreshAppState();
  });
});

async function refreshAppState() {
  try {
    const data = await window.pywebview.api.get_initial_state();
    Object.assign(appState, data);
    renderInitialUI();
  } catch (err) {
    console.error('Failed to get initial state:', err);
    appendLog(`❌ Lỗi kết nối backend: ${err.message || err}`, 'error');
  }
}

function renderInitialUI() {
  // Projects
  const projSelect = document.getElementById('project-select');
  projSelect.innerHTML = '';
  appState.projects.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p;
    opt.textContent = p;
    if (p === appState.active_project) opt.selected = true;
    projSelect.appendChild(opt);
  });

  // Proxy
  const chkProxy = document.getElementById('chk-use-proxy');
  if (chkProxy) chkProxy.checked = !!appState.use_proxy;
  const selRegion = document.getElementById('select-proxy-region');
  if (selRegion) selRegion.value = appState.proxy_region || 'IP - Nhật Bản';

  // Threads
  document.getElementById('input-threads').value = appState.threads || 500;

  // Bottom Toggles
  document.getElementById('chk-auto-upload-tiktok').checked = !!appState.auto_upload_tiktok;
  document.getElementById('chk-only-shorts').checked = !!appState.only_shorts;
  document.getElementById('chk-telegram-enabled').checked = !!appState.telegram_enabled;

  // Stats
  document.getElementById('stat-pool-total').textContent = appState.pool_total || 0;
  document.getElementById('stat-pool-remaining').textContent = appState.pool_remaining || 0;
  document.getElementById('stat-key-dead').textContent = `(${appState.dead_keys_count || 0})`;

  // Schedule badge
  updateScheduleBadge();

  // Channels Table
  renderChannelsTable();
}

function updateScheduleBadge() {
  const badge = document.getElementById('schedule-indicator');
  if (appState.schedule && appState.schedule.length > 0) {
    const slots = appState.schedule.map(s => `${s.start}-${s.end}`).join(', ');
    const modeText = appState.schedule_mode === 'single' ? 'Gộp' : 'Tách cụm';
    badge.textContent = `⏰ Lịch [${modeText}]: ${slots}`;
    badge.style.color = 'var(--emerald)';
  } else {
    badge.textContent = '⏰ Lịch: Tự do (24/7)';
    badge.style.color = 'var(--cyan)';
  }
}

// ==========================================
// CHANNELS TABLE (MAIN WINDOW)
// ==========================================

function renderChannelsTable() {
  const tbody = document.getElementById('channels-tbody');
  tbody.innerHTML = '';

  const channels = appState.channels || [];
  document.getElementById('badge-channel-count').textContent = `(${channels.length} kênh)`;

  if (channels.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-dim); padding: 18px;">Chưa có kênh YouTube nào trong dự án này. Hãy thêm link kênh phía trên.</td></tr>`;
    return;
  }

  const chSettings = (appState.tiktok_config && appState.tiktok_config.channels_config) || {};
  const gpmList = appState.gpm_profiles || [];

  channels.forEach((ch, idx) => {
    const tr = document.createElement('tr');
    const cfg = chSettings[ch] || {};
    const pid = cfg.profile_id;
    const quality = cfg.quality || '720';
    const mode = cfg.process_mode || 'extend_61s';

    let gpmName = '<span style="color: var(--amber);">Chưa gán GPM</span>';
    if (pid) {
      const match = gpmList.find(p => p.id === pid);
      const name = match ? match.name : pid.substring(0, 8);
      const modeLabel = mode === 'extend_61s' ? 'Edit 61s' : 'Up luôn';
      gpmName = `<span style="color: var(--cyan); font-weight: 600;">${name}</span> <span style="font-size: 10px; color: var(--emerald);">(${quality}p • ${modeLabel})</span>`;
    }

    tr.innerHTML = `
      <td style="text-align: center;"><input type="checkbox" class="chk-channel-item" data-url="${ch}"></td>
      <td style="color: var(--text-dim); font-weight: 600;">${idx + 1}</td>
      <td style="font-weight: 500; word-break: break-all;">${ch}</td>
      <td><span style="font-size: 11px;">${gpmName}</span></td>
      <td><span style="color: var(--emerald); font-size: 11px;">● Đang theo dõi</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// ==========================================
// UI EVENT LISTENERS
// ==========================================

function setupUIEventListeners() {
  // Project switch
  document.getElementById('project-select').addEventListener('change', async (e) => {
    const proj = e.target.value;
    try {
      const res = await window.pywebview.api.switch_project(proj);
      appState.active_project = res.active_project;
      appState.channels = res.channels;
      appState.schedule = res.schedule;
      if (res.tiktok_config) appState.tiktok_config = res.tiktok_config;
      renderInitialUI();
    } catch (err) {
      appendLog(`❌ Lỗi chuyển dự án: ${err.message || err}`, 'error');
    }
  });

  // Add channel
  document.getElementById('btn-add-channel').addEventListener('click', async () => {
    const input = document.getElementById('input-channel-url');
    const url = input.value.trim();
    if (!url) return;

    if (!appState.channels.includes(url)) {
      appState.channels.push(url);
      input.value = '';
      await saveCurrentProjectState();
      renderChannelsTable();
      appendLog(`➕ Đã thêm kênh: ${url}`);
    } else {
      alert('Kênh này đã có trong danh sách!');
    }
  });

  // Delete channel
  document.getElementById('btn-del-channel').addEventListener('click', async () => {
    const checked = Array.from(document.querySelectorAll('.chk-channel-item:checked')).map(el => el.getAttribute('data-url'));
    if (checked.length === 0) {
      alert('Vui lòng tích chọn kênh cần xóa!');
      return;
    }

    if (confirm(`Bạn có chắc chắn muốn xóa ${checked.length} kênh đã chọn?`)) {
      appState.channels = appState.channels.filter(ch => !checked.includes(ch));
      await saveCurrentProjectState();
      renderChannelsTable();
      appendLog(`🗑 Đã xóa ${checked.length} kênh.`);
    }
  });

  // Select all channels checkbox
  document.getElementById('chk-all-channels').addEventListener('change', (e) => {
    const checked = e.target.checked;
    document.querySelectorAll('.chk-channel-item').forEach(el => el.checked = checked);
  });

  // Clear logs
  document.getElementById('btn-clear-logs').addEventListener('click', () => {
    document.getElementById('terminal-logs').innerHTML = '<div class="watermark-overlay">[ ▶ TCD REUP TOOL ]</div>';
  });

  // Automation Start / Stop
  const btnStart = document.getElementById('btn-start-automation');
  const btnStop = document.getElementById('btn-stop-automation');

  btnStart.addEventListener('click', async () => {
    if (appState.channels.length === 0) {
      alert('Vui lòng thêm ít nhất một kênh YouTube trước khi bắt đầu!');
      return;
    }
    await saveCurrentProjectState();
    try {
      const res = await window.pywebview.api.start_automation();
      if (res.success) {
        setAutomationRunning(true);
      }
    } catch (err) {
      appendLog(`❌ Không thể khởi động automation: ${err.message || err}`, 'error');
    }
  });

  btnStop.addEventListener('click', async () => {
    try {
      await window.pywebview.api.stop_automation();
      setAutomationRunning(false);
    } catch (err) {
      appendLog(`❌ Không thể dừng automation: ${err.message || err}`, 'error');
    }
  });

  // Setting toggles change -> auto save
  ['input-threads', 'chk-auto-upload-tiktok', 'chk-only-shorts'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('change', () => {
        saveCurrentProjectState();
      });
    }
  });

  // Telegram toggle
  document.getElementById('chk-telegram-enabled').addEventListener('change', async (e) => {
    appState.telegram_enabled = e.target.checked;
    await window.pywebview.api.save_telegram_config(
      appState.telegram_token,
      (appState.telegram_chat_ids || []).join(','),
      appState.telegram_enabled
    );
  });

  // Test Tele
  document.getElementById('btn-test-tele').addEventListener('click', async () => {
    if (!appState.telegram_token) {
      openModal('modal-telegram-config');
      return;
    }
    const res = await window.pywebview.api.test_telegram(appState.telegram_token, (appState.telegram_chat_ids || []).join(','));
    if (res.success) {
      alert('Đã gửi tin nhắn test Telegram thành công!');
    } else {
      alert(`Lỗi Telegram: ${res.message}`);
    }
  });
}

function setAutomationRunning(running) {
  appState.is_running = running;
  document.getElementById('btn-start-automation').disabled = running;
  document.getElementById('btn-stop-automation').disabled = !running;
  if (running) {
    document.getElementById('btn-start-automation').classList.remove('btn-emerald');
    document.getElementById('btn-start-automation').classList.add('btn-secondary');
  } else {
    document.getElementById('btn-start-automation').classList.add('btn-emerald');
    document.getElementById('btn-start-automation').classList.remove('btn-secondary');
  }
}

async function saveCurrentProjectState() {
  const elThreads = document.getElementById('input-threads');
  if (elThreads) appState.threads = parseInt(elThreads.value) || 500;
  const elProxy = document.getElementById('chk-use-proxy');
  if (elProxy) appState.use_proxy = elProxy.checked;
  const elRegion = document.getElementById('select-proxy-region');
  if (elRegion) appState.proxy_region = elRegion.value;
  const elAuto = document.getElementById('chk-auto-upload-tiktok');
  if (elAuto) appState.auto_upload_tiktok = elAuto.checked;
  const elShorts = document.getElementById('chk-only-shorts');
  if (elShorts) appState.only_shorts = elShorts.checked;

  try {
    await window.pywebview.api.save_project_state({
      channels: appState.channels,
      threads: appState.threads,
      use_proxy: appState.use_proxy,
      proxy_region: appState.proxy_region,
      auto_upload_tiktok: appState.auto_upload_tiktok,
      only_shorts: appState.only_shorts
    });
  } catch (err) {
    console.error('Failed saving project state:', err);
  }
}

// ==========================================
// MODAL CONTROLS
// ==========================================

function openModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) el.classList.add('active');
}

function closeModal(modalId) {
  const el = document.getElementById(modalId);
  if (el) el.classList.remove('active');
}

function setupModalHandlers() {
  document.querySelectorAll('.modal-close-btn, .modal-close-trigger').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const modal = e.target.closest('.modal-overlay');
      if (modal) modal.classList.remove('active');
    });
  });

  // Modal 1: Create Project
  document.getElementById('btn-open-create-project').addEventListener('click', () => {
    document.getElementById('input-new-project-name').value = '';
    openModal('modal-create-project');
  });

  document.getElementById('btn-confirm-create-project').addEventListener('click', async () => {
    const name = document.getElementById('input-new-project-name').value.trim();
    if (!name) return;
    try {
      const res = await window.pywebview.api.create_project(name);
      if (res.success) {
        appState.active_project = res.active_project;
        appState.projects = res.projects;
        appState.channels = [];
        closeModal('modal-create-project');
        renderInitialUI();
      }
    } catch (err) {
      alert(`Lỗi tạo dự án: ${err.message || err}`);
    }
  });

  // Modal 2: Manage Projects
  document.getElementById('btn-open-manage-projects').addEventListener('click', () => {
    renderManageProjectsModal();
    openModal('modal-manage-projects');
  });

  document.getElementById('btn-goto-schedule-analysis').addEventListener('click', () => {
    closeModal('modal-manage-projects');
    openModal('modal-schedule-mode');
  });

  // Modal 3: Schedule Mode
  document.getElementById('btn-open-schedule-mode').addEventListener('click', () => {
    openModal('modal-schedule-mode');
  });

  document.querySelectorAll('.schedule-option-card').forEach(card => {
    card.addEventListener('click', () => {
      document.querySelectorAll('.schedule-option-card').forEach(c => c.classList.remove('selected'));
      card.classList.add('selected');
    });
  });

  document.getElementById('btn-run-schedule-analysis').addEventListener('click', async () => {
    const selected = document.querySelector('.schedule-option-card.selected');
    const mode = selected ? selected.getAttribute('data-mode') : 'multi';
    closeModal('modal-schedule-mode');
    appendLog(`⏳ Đang bắt đầu phân tích lịch YouTube bằng AI [${mode.toUpperCase()}]...`);

    try {
      const res = await window.pywebview.api.analyze_schedule(mode);
      if (res.success) {
        appState.schedule = res.schedule;
        appState.schedule_mode = mode;
        updateScheduleBadge();
        appendLog(`✅ Phân tích hoàn tất: ${res.summary || 'Chạy 24/7'}`, 'success');
      }
    } catch (err) {
      appendLog(`❌ Lỗi phân tích lịch: ${err.message || err}`, 'error');
    }
  });

  // Modal 4: API Pool
  document.getElementById('btn-open-api-pool').addEventListener('click', async () => {
    await refreshApiPoolData();
    openModal('modal-api-pool');
  });

  document.getElementById('btn-pool-refresh').addEventListener('click', refreshApiPoolData);

  document.getElementById('btn-pool-recover-garbage').addEventListener('click', async () => {
    const res = await window.pywebview.api.recover_garbage_api_keys();
    alert(`Đã thu hồi ${res.recovered} keys rác từ ${res.affected} kênh.`);
    await refreshApiPoolData();
  });

  document.getElementById('btn-pool-distribute-missing').addEventListener('click', async () => {
    const k = parseInt(document.getElementById('input-keys-per-channel').value) || 100;
    const res = await window.pywebview.api.distribute_api_keys('missing', k);
    alert(`Đã cấp bổ sung ${res.added_keys} API keys cho các kênh còn thiếu.`);
    await refreshApiPoolData();
  });

  document.getElementById('btn-pool-distribute-all').addEventListener('click', async () => {
    const k = parseInt(document.getElementById('input-keys-per-channel').value) || 100;
    if (confirm(`Bạn có chắc muốn xóa phân bổ cũ và chia lại toàn bộ ${k} keys cho mỗi kênh?`)) {
      const res = await window.pywebview.api.distribute_api_keys('all', k);
      alert(`Đã chia lại ${res.total_assigned} API keys cho toàn bộ các kênh.`);
      await refreshApiPoolData();
    }
  });

  document.getElementById('btn-pool-clean-bak').addEventListener('click', async () => {
    const count = await window.pywebview.api.clean_backup_files();
    alert(`Đã xóa ${count} file backup .bak tạm.`);
  });

  // Modal 5: Edit Pool
  document.getElementById('btn-open-edit-pool').addEventListener('click', () => {
    document.getElementById('textarea-master-pool').value = (appState.master_keys || []).join('\n');
    openModal('modal-edit-pool');
  });

  document.getElementById('btn-save-master-pool').addEventListener('click', async () => {
    const raw = document.getElementById('textarea-master-pool').value;
    const res = await window.pywebview.api.update_master_pool(raw);
    alert(`Đã cập nhật: Tổng ${res.total} keys (Mới thêm: ${res.added}).`);
    closeModal('modal-edit-pool');
    await refreshApiPoolData();
  });

  // Modal 6: TikTok Config (Redesigned)
  document.getElementById('btn-open-tiktok-config').addEventListener('click', async () => {
    renderTikTokConfigModal();
    openModal('modal-tiktok-config');
  });

  document.getElementById('btn-sync-gpm').addEventListener('click', async () => {
    const res = await window.pywebview.api.sync_gpm_profiles();
    if (res.success) {
      appState.gpm_profiles = res.profiles;
      alert(`Đã đồng bộ ${res.profiles.length} profiles từ GPMLogin!`);
      renderTikTokConfigModal();
    } else {
      alert(`Lỗi kết nối GPMLogin: ${res.message}`);
    }
  });

  document.getElementById('btn-save-all-tiktok-config').addEventListener('click', async () => {
    await saveTikTokConfigFromModal();
    closeModal('modal-tiktok-config');
    renderChannelsTable();
  });

  // Modal 7: Telegram Config
  document.getElementById('btn-open-telegram-config').addEventListener('click', () => {
    document.getElementById('input-telegram-token').value = appState.telegram_token || '';
    document.getElementById('input-telegram-chat-ids').value = (appState.telegram_chat_ids || []).join(', ');
    document.getElementById('modal-chk-telegram-enabled').checked = !!appState.telegram_enabled;
    openModal('modal-telegram-config');
  });

  document.getElementById('btn-save-telegram').addEventListener('click', async () => {
    const token = document.getElementById('input-telegram-token').value.trim();
    const chats = document.getElementById('input-telegram-chat-ids').value.trim();
    const enabled = document.getElementById('modal-chk-telegram-enabled').checked;

    await window.pywebview.api.save_telegram_config(token, chats, enabled);
    appState.telegram_token = token;
    appState.telegram_chat_ids = chats.split(',').map(s => s.trim()).filter(Boolean);
    appState.telegram_enabled = enabled;
    document.getElementById('chk-telegram-enabled').checked = enabled;
    closeModal('modal-telegram-config');
  });

  // Modal 8: License
  document.getElementById('btn-open-license').addEventListener('click', () => {
    openModal('modal-license');
  });
}

function renderManageProjectsModal() {
  const tbody = document.getElementById('projects-manage-tbody');
  tbody.innerHTML = '';

  appState.projects.forEach(p => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="font-weight: 600; color: ${p === appState.active_project ? 'var(--cyan)' : '#fff'};">${p} ${p === appState.active_project ? '(Đang chọn)' : ''}</td>
      <td style="text-align: center;">
        <button class="btn btn-ruby btn-sm btn-delete-proj" data-name="${p}">Xóa</button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  document.querySelectorAll('.btn-delete-proj').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const name = e.target.getAttribute('data-name');
      if (confirm(`Bạn có chắc muốn xóa dự án '${name}'?`)) {
        const res = await window.pywebview.api.delete_project(name);
        appState.projects = res.projects;
        appState.active_project = res.active_project;
        renderManageProjectsModal();
        renderInitialUI();
      }
    });
  });

  document.getElementById('lbl-active-project-name').textContent = appState.active_project;
  document.getElementById('lbl-active-project-stats').textContent = `Số kênh: ${(appState.channels || []).length}`;
  const slots = (appState.schedule || []).map(s => `${s.start}-${s.end}`).join(', ');
  document.getElementById('lbl-active-project-schedule').textContent = `Lịch tự động: ${slots || 'Chạy 24/7'}`;
}

async function refreshApiPoolData() {
  try {
    const data = await window.pywebview.api.get_api_pool_data();
    appState.master_keys = data.master_keys || [];
    document.getElementById('pool-modal-total').textContent = data.total_keys;
    document.getElementById('pool-modal-rem').textContent = data.remaining_keys;
    document.getElementById('stat-pool-total').textContent = data.total_keys;
    document.getElementById('stat-pool-remaining').textContent = data.remaining_keys;
    document.getElementById('stat-key-dead').textContent = `(${data.dead_keys_count})`;
    document.getElementById('lbl-last-distribution').textContent = `Lần chia gần nhất: ${data.last_distribution}`;

    const tbody = document.getElementById('scanned-channels-tbody');
    tbody.innerHTML = '';
    (data.scanned_channels || []).forEach((c, idx) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="color: var(--text-dim);">${idx + 1}</td>
        <td><code>${c.folder}</code></td>
        <td style="word-break: break-all;">${c.channel_url}</td>
        <td><span style="color: var(--cyan);">${c.project}</span></td>
        <td style="text-align: center; font-weight: bold; color: ${c.assigned_keys_count > 0 ? 'var(--emerald)' : 'var(--ruby)'};">${c.assigned_keys_count}</td>
        <td><span style="font-size: 11px; color: ${c.assigned_keys_count > 0 ? 'var(--emerald)' : 'var(--amber)'};">${c.assigned_keys_count > 0 ? '● Đã cấp' : '○ Chưa cấp'}</span></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Failed refreshing API pool data:', err);
  }
}

// ==========================================
// TIKTOK CONFIG MODAL LOGIC (REDESIGNED)
// ==========================================

function renderTikTokConfigModal() {
  const tbody = document.getElementById('tbody-tiktok-channels');
  tbody.innerHTML = '';

  const cfg = appState.tiktok_config || {};
  document.getElementById('input-tiktok-upload-timeout').value = cfg.upload_timeout || 30;
  document.getElementById('input-tiktok-next-delay').value = cfg.next_video_delay || 180;
  document.getElementById('select-caption-mode').value = cfg.caption_mode || 'keep_title';

  const gpmProfiles = appState.gpm_profiles || [];
  document.getElementById('lbl-gpm-profiles-count').textContent = `Đã nạp ${gpmProfiles.length} profiles`;

  const channels = appState.channels || [];
  if (channels.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 24px;">Dự án hiện tại chưa có kênh YouTube nào. Hãy thêm kênh ở màn hình chính!</td></tr>`;
    return;
  }

  const chSettings = cfg.channels_config || {};

  channels.forEach((ch, idx) => {
    const tr = document.createElement('tr');
    const cur = chSettings[ch] || {};
    const selectedPid = cur.profile_id || '';
    const selectedQuality = cur.quality || '720';
    const selectedMode = cur.process_mode || 'extend_61s';

    // Build GPM Profiles select options
    let gpmOptions = `<option value="">-- Chưa gán Profile GPM --</option>`;
    gpmProfiles.forEach(p => {
      const isSel = p.id === selectedPid ? 'selected' : '';
      const label = `${p.name || 'Profile'} (${p.id.substring(0, 8)}...)`;
      gpmOptions += `<option value="${p.id}" ${isSel}>${label}</option>`;
    });

    tr.innerHTML = `
      <td style="color: var(--text-dim); text-align: center;">${idx + 1}</td>
      <td style="word-break: break-all; font-weight: 500; font-size: 11.5px;">${ch}</td>
      <td>
        <select class="select-control sel-gpm-profile" data-ch="${ch}" style="width: 100%;">
          ${gpmOptions}
        </select>
      </td>
      <td>
        <select class="select-control sel-quality" data-ch="${ch}" style="width: 100%;">
          <option value="720" ${selectedQuality === '720' ? 'selected' : ''}>⚡ 720p (Siêu tốc)</option>
          <option value="1080" ${selectedQuality === '1080' ? 'selected' : ''}>🎬 1080p (Full HD)</option>
        </select>
      </td>
      <td>
        <select class="select-control sel-process-mode" data-ch="${ch}" style="width: 100%;">
          <option value="extend_61s" ${selectedMode === 'extend_61s' ? 'selected' : ''}>✂ Edit đủ 1m01s (≥61s FFmpeg)</option>
          <option value="direct" ${selectedMode === 'direct' ? 'selected' : ''}>⚡ Tải up luôn (Trực tiếp)</option>
        </select>
      </td>
      <td style="text-align: center;">
        <div style="display: flex; gap: 4px; justify-content: center;">
          <button class="btn btn-emerald btn-sm btn-test-start" data-ch="${ch}">▶ Mở</button>
          <button class="btn btn-ruby btn-sm btn-test-stop" data-ch="${ch}">⏹ Đóng</button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Attach test start/stop button handlers
  tbody.querySelectorAll('.btn-test-start').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const ch = e.target.getAttribute('data-ch');
      const rowSel = tbody.querySelector(`.sel-gpm-profile[data-ch="${CSS.escape(ch)}"]`);
      const pid = rowSel ? rowSel.value : '';
      if (!pid) {
        alert('Vui lòng chọn Profile GPM cho kênh này trước!');
        return;
      }
      const res = await window.pywebview.api.test_start_gpm_profile(pid);
      if (res.success) {
        alert(`Đã khởi động profile ${pid} trên port ${res.port}`);
      } else {
        alert(`Lỗi mở GPM: ${res.message}`);
      }
    });
  });

  tbody.querySelectorAll('.btn-test-stop').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const ch = e.target.getAttribute('data-ch');
      const rowSel = tbody.querySelector(`.sel-gpm-profile[data-ch="${CSS.escape(ch)}"]`);
      const pid = rowSel ? rowSel.value : '';
      if (!pid) {
        alert('Chưa chọn Profile GPM!');
        return;
      }
      await window.pywebview.api.test_stop_gpm_profile(pid);
      alert(`Đã gửi lệnh đóng GPM Profile.`);
    });
  });
}

async function saveTikTokConfigFromModal() {
  const cfg = appState.tiktok_config || {};
  cfg.upload_timeout = parseInt(document.getElementById('input-tiktok-upload-timeout').value) || 30;
  cfg.next_video_delay = parseInt(document.getElementById('input-tiktok-next-delay').value) || 180;
  cfg.caption_mode = document.getElementById('select-caption-mode').value;

  const channels_config = {};
  const profileToChannels = {};

  document.querySelectorAll('.sel-gpm-profile').forEach(sel => {
    const ch = sel.getAttribute('data-ch');
    const pid = sel.value;
    const qSel = document.querySelector(`.sel-quality[data-ch="${CSS.escape(ch)}"]`);
    const mSel = document.querySelector(`.sel-process-mode[data-ch="${CSS.escape(ch)}"]`);
    const q = qSel ? qSel.value : '720';
    const m = mSel ? mSel.value : 'extend_61s';

    channels_config[ch] = {
      profile_id: pid,
      quality: q,
      process_mode: m
    };

    if (pid) {
      if (!profileToChannels[pid]) profileToChannels[pid] = [];
      profileToChannels[pid].push(ch);
    }
  });

  cfg.channels_config = channels_config;

  // Build profiles list to maintain full backward compatibility
  cfg.profiles = Object.keys(profileToChannels).map(pid => {
    const match = (appState.gpm_profiles || []).find(p => p.id === pid);
    return {
      profile_id: pid,
      profile_name: match ? match.name : pid,
      assigned_channels: profileToChannels[pid]
    };
  });

  await window.pywebview.api.save_tiktok_config(cfg);
  appState.tiktok_config = cfg;
  appendLog(`💾 Đã lưu cấu hình TikTok Upload cho ${Object.keys(channels_config).length} kênh.`, 'success');
}

// ==========================================
// TERMINAL LOGS & QUEUE UPDATES (PY -> JS)
// ==========================================

function appendLog(message, type = 'normal') {
  const terminal = document.getElementById('terminal-logs');
  const now = new Date();
  const timeStr = [
    String(now.getHours()).padStart(2, '0'),
    String(now.getMinutes()).padStart(2, '0'),
    String(now.getSeconds()).padStart(2, '0')
  ].join(':');

  const div = document.createElement('div');
  div.className = 'log-entry';
  div.innerHTML = `
    <span class="log-time">[${timeStr}]</span>
    <span class="log-msg ${type}">${message}</span>
  `;
  terminal.appendChild(div);
  terminal.scrollTop = terminal.scrollHeight;
}

// Exposed global callbacks for pywebview evaluate_js
window.onAppLog = function(text) {
  let type = 'normal';
  if (text.includes('✨') || text.includes('✅') || text.includes('hoàn tất')) type = 'success';
  if (text.includes('⚠') || text.includes('Cảnh báo')) type = 'warn';
  if (text.includes('❌') || text.includes('Lỗi')) type = 'error';
  if (text.includes('🚀') || text.includes('▶') || text.includes('🔑') || text.includes('✂')) type = 'highlight';

  appendLog(text, type);
};

window.onQueueUpdate = function(jsonStr) {
  try {
    const item = typeof jsonStr === 'string' ? JSON.parse(jsonStr) : jsonStr;
    const tbody = document.getElementById('queue-tbody');

    if (tbody.querySelector('td[colspan="3"]')) {
      tbody.innerHTML = '';
    }

    let existingRow = document.getElementById(`queue-row-${item.id}`);
    if (!existingRow) {
      existingRow = document.createElement('tr');
      existingRow.id = `queue-row-${item.id}`;
      tbody.appendChild(existingRow);
    }

    existingRow.innerHTML = `
      <td style="font-weight: 500; font-size: 11.5px; word-break: break-all;">${item.title || item.id}</td>
      <td>
        <div style="font-size: 10px; color: var(--cyan); text-align: right;">${item.progress}%</div>
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" style="width: ${item.progress}%;"></div>
        </div>
      </td>
      <td><span style="color: var(--emerald); font-size: 11px;">${item.status}</span></td>
    `;
  } catch (e) {
    console.error('Error handling onQueueUpdate:', e);
  }
};

window.onAutomationStateChange = function(running) {
  setAutomationRunning(running);
};
