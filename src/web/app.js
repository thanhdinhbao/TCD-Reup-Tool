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
  skip_horizontal: true,
  scan_engine: 'both',
  min_duration: 20,
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

  // Threads & Scan Settings
  document.getElementById('input-threads').value = appState.threads || 500;
  const elScanEngine = document.getElementById('select-scan-engine');
  let currentEngine = appState.scan_engine || 'both';
  if (currentEngine === 'rss') currentEngine = 'ytdlp';
  if (elScanEngine) elScanEngine.value = currentEngine;
  const elMinDur = document.getElementById('input-min-duration');
  if (elMinDur) elMinDur.value = (appState.min_duration !== undefined) ? appState.min_duration : 20;

  // Bottom Toggles
  document.getElementById('chk-auto-upload-tiktok').checked = !!appState.auto_upload_tiktok;
  document.getElementById('chk-only-shorts').checked = !!appState.only_shorts;
  const elSkipH = document.getElementById('chk-skip-horizontal');
  if (elSkipH) elSkipH.checked = (appState.skip_horizontal !== undefined) ? !!appState.skip_horizontal : true;
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

  const globalCfg = appState.global_tiktok_config || {};
  const projConfigs = globalCfg.project_configs || {};
  const pGpm = projConfigs[appState.active_project] || {};
  const chSettings = (appState.tiktok_config && appState.tiktok_config.channels_config) || {};
  const gpmList = appState.gpm_profiles || [];

  const defaultPid = pGpm.profile_id || '';
  const defaultQuality = pGpm.quality || '720_fps';
  const defaultMode = pGpm.process_mode || 'direct';

  channels.forEach((ch, idx) => {
    const tr = document.createElement('tr');
    const cfg = chSettings[ch] || {};
    const pid = defaultPid || cfg.profile_id || '';
    const quality = defaultPid ? defaultQuality : (cfg.quality || '720_fps');
    const mode = defaultPid ? defaultMode : (cfg.process_mode || 'direct');

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
      if (res.only_shorts !== undefined) appState.only_shorts = res.only_shorts;
      if (res.skip_horizontal !== undefined) appState.skip_horizontal = res.skip_horizontal;
      if (res.scan_engine !== undefined) appState.scan_engine = res.scan_engine;
      if (res.min_duration !== undefined) appState.min_duration = res.min_duration;
      if (res.auto_upload_tiktok !== undefined) appState.auto_upload_tiktok = res.auto_upload_tiktok;
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
  const btnStartAll = document.getElementById('btn-start-all-projects');
  const btnStop = document.getElementById('btn-stop-automation');

  if (btnStart) {
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
        } else {
          alert(res.message || 'Không thể khởi động!');
        }
      } catch (err) {
        appendLog(`❌ Không thể khởi động automation: ${err.message || err}`, 'error');
      }
    });
  }

  if (btnStartAll) {
    btnStartAll.addEventListener('click', async () => {
      await saveCurrentProjectState();
      try {
        const res = await window.pywebview.api.start_all_projects();
        if (res.success) {
          setAutomationRunning(true);
        } else {
          alert(res.message || 'Không thể khởi động chạy tất cả dự án!');
        }
      } catch (err) {
        appendLog(`❌ Lỗi khởi động chạy tất cả dự án: ${err.message || err}`, 'error');
      }
    });
  }

  if (btnStop) {
    btnStop.addEventListener('click', async () => {
      try {
        await window.pywebview.api.stop_automation();
        setAutomationRunning(false);
      } catch (err) {
        appendLog(`❌ Không thể dừng automation: ${err.message || err}`, 'error');
      }
    });
  }

  // Setting toggles change -> auto save
  ['input-threads', 'chk-auto-upload-tiktok', 'chk-only-shorts', 'chk-skip-horizontal', 'select-scan-engine', 'input-min-duration'].forEach(id => {
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
  const btnStart = document.getElementById('btn-start-automation');
  const btnStartAll = document.getElementById('btn-start-all-projects');
  const btnStop = document.getElementById('btn-stop-automation');

  if (btnStart) {
    btnStart.disabled = running;
    if (running) {
      btnStart.classList.remove('btn-emerald');
      btnStart.classList.add('btn-secondary');
    } else {
      btnStart.classList.add('btn-emerald');
      btnStart.classList.remove('btn-secondary');
    }
  }

  if (btnStartAll) {
    btnStartAll.disabled = running;
    if (running) {
      btnStartAll.classList.remove('btn-primary');
      btnStartAll.classList.add('btn-secondary');
    } else {
      btnStartAll.classList.add('btn-primary');
      btnStartAll.classList.remove('btn-secondary');
    }
  }

  if (btnStop) {
    btnStop.disabled = !running;
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
  const elSkipH = document.getElementById('chk-skip-horizontal');
  if (elSkipH) appState.skip_horizontal = elSkipH.checked;
  const elScanEngine = document.getElementById('select-scan-engine');
  if (elScanEngine) appState.scan_engine = elScanEngine.value;
  const elMinDur = document.getElementById('input-min-duration');
  if (elMinDur) appState.min_duration = parseInt(elMinDur.value) || 0;

  try {
    await window.pywebview.api.save_project_state({
      channels: appState.channels,
      threads: appState.threads,
      use_proxy: appState.use_proxy,
      proxy_region: appState.proxy_region,
      auto_upload_tiktok: appState.auto_upload_tiktok,
      only_shorts: appState.only_shorts,
      skip_horizontal: appState.skip_horizontal,
      scan_engine: appState.scan_engine,
      min_duration: appState.min_duration
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

  // Modal 6: TikTok Config (Redesigned - Global Per-Project & GPM Mapping)
  const btnOpenTikTok = document.getElementById('btn-open-tiktok-config');
  if (btnOpenTikTok) {
    btnOpenTikTok.addEventListener('click', async () => {
      openModal('modal-tiktok-config');
      const countEl = document.getElementById('lbl-gpm-profiles-count');
      if (countEl) countEl.textContent = '⏳ Đang tự động quét GPM profiles...';

      try {
        // Tự động lưu trạng thái kênh hiện tại trước để đồng bộ số kênh mới nhất
        await saveCurrentProjectState();

        // Tự động quét và nạp profiles từ GPM Port 9495 không cần user bấm nút thủ công
        const [gpmRes, globalCfg, allProjs] = await Promise.all([
          window.pywebview.api.sync_gpm_profiles().catch(() => ({ profiles: [] })),
          window.pywebview.api.get_global_tiktok_config().catch(() => ({})),
          window.pywebview.api.get_all_projects_details().catch(() => [])
        ]);

        if (gpmRes && gpmRes.profiles) {
          appState.gpm_profiles = gpmRes.profiles;
        }
        if (globalCfg) {
          appState.global_tiktok_config = globalCfg;
        }
        if (allProjs && allProjs.length > 0) {
          appState.all_projects_details = allProjs;
        }
        renderTikTokConfigModal();
      } catch (err) {
        console.error('Error auto-loading GPM and TikTok configs:', err);
        renderTikTokConfigModal();
      }
    });
  }

  const btnSyncGpm = document.getElementById('btn-sync-gpm');
  if (btnSyncGpm) {
    btnSyncGpm.addEventListener('click', async () => {
      const res = await window.pywebview.api.sync_gpm_profiles();
      if (res.success) {
        appState.gpm_profiles = res.profiles;
        alert(`Đã nạp thành công ${res.profiles.length} profiles từ GPMLogin!`);
        renderTikTokConfigModal();
      } else {
        alert(`Lỗi kết nối GPMLogin: ${res.message}`);
      }
    });
  }

  const btnSaveTikTok = document.getElementById('btn-save-all-tiktok-config');
  if (btnSaveTikTok) {
    btnSaveTikTok.addEventListener('click', async () => {
      await saveTikTokConfigFromModal();
      closeModal('modal-tiktok-config');
      renderChannelsTable();
    });
  }

  // Quick Search for GPM Profile / Project
  const inputSearch = document.getElementById('input-search-gpm-project');
  if (inputSearch) {
    inputSearch.addEventListener('input', (e) => {
      filterTikTokProjectsTable(e.target.value.trim().toLowerCase());
    });
  }

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
// TIKTOK CONFIG MODAL LOGIC (GLOBAL PER-PROJECT)
// ==========================================

function filterTikTokProjectsTable(keyword) {
  const tbody = document.getElementById('tbody-tiktok-projects');
  if (!tbody) return;
  const rows = tbody.querySelectorAll('tr');
  let matched = 0;
  const kw = (keyword || '').toLowerCase().trim();

  rows.forEach(tr => {
    const pName = (tr.getAttribute('data-project') || '').toLowerCase();
    const sel = tr.querySelector('.sel-project-gpm-profile');
    const triggerText = tr.querySelector('.gpm-dropdown-trigger-text');
    const val = sel ? (sel.value || '').toLowerCase() : '';
    const label = triggerText ? (triggerText.textContent || '').toLowerCase() : '';

    if (!kw || pName.includes(kw) || label.includes(kw) || val.includes(kw)) {
      tr.style.display = '';
      matched++;
    } else {
      tr.style.display = 'none';
    }
  });

  const lbl = document.getElementById('lbl-search-match-count');
  if (lbl) {
    lbl.textContent = kw ? `(Hiển thị ${matched}/${rows.length} dự án)` : '';
  }
}

function renderTikTokConfigModal() {
  const tbody = document.getElementById('tbody-tiktok-projects');
  if (!tbody) return;
  tbody.innerHTML = '';

  const globalCfg = appState.global_tiktok_config || appState.tiktok_config || {};
  const elTimeout = document.getElementById('input-tiktok-upload-timeout');
  if (elTimeout) elTimeout.value = globalCfg.upload_timeout || 30;
  const elNextDelay = document.getElementById('input-tiktok-next-delay');
  if (elNextDelay) elNextDelay.value = globalCfg.next_video_delay || 180;
  const elGpmMode = document.getElementById('select-gpm-open-mode');
  if (elGpmMode) elGpmMode.value = globalCfg.gpm_open_mode || 'on_new_video';
  const elCaption = document.getElementById('select-caption-mode');
  if (elCaption) elCaption.value = globalCfg.caption_mode || 'keep_title';

  const gpmProfiles = appState.gpm_profiles || [];
  const elCount = document.getElementById('lbl-gpm-profiles-count');
  if (elCount) elCount.textContent = `Đã nạp ${gpmProfiles.length} profiles`;

  let projectsList = appState.all_projects_details || [];
  if (projectsList.length === 0 && appState.projects && appState.projects.length > 0) {
    projectsList = appState.projects.map(p => ({
      name: p,
      channel_count: (p === appState.active_project) ? (appState.channels || []).length : 0
    }));
  }

  if (projectsList.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-dim); padding: 24px;">Chưa có dự án nào trong hệ thống!</td></tr>`;
    return;
  }

  const projectConfigs = globalCfg.project_configs || {};

  projectsList.forEach((p, idx) => {
    const pName = p.name || `Dự án ${idx + 1}`;
    let chCount = 0;
    if (p.channel_count !== undefined && p.channel_count !== null) {
      chCount = p.channel_count;
    } else if (p.channels_count !== undefined && p.channels_count !== null) {
      chCount = p.channels_count;
    } else if (Array.isArray(p.channels)) {
      chCount = p.channels.length;
    }

    if (pName === appState.active_project && Array.isArray(appState.channels) && appState.channels.length > 0) {
      chCount = appState.channels.length;
    }

    const cur = projectConfigs[pName] || {};
    const selectedPid = cur.profile_id || '';
    const selectedQuality = cur.quality || '720_fps';
    const selectedFps = cur.fps || '120';
    const selectedMode = cur.process_mode || 'direct';

    // Xác định label hiển thị hiện tại của Profile
    let currentDisplayLabel = '-- Chưa gán Profile GPM --';
    const matchedProf = gpmProfiles.find(prof => prof.id === selectedPid);
    if (matchedProf) {
      currentDisplayLabel = `${matchedProf.name || 'Profile'} (${matchedProf.id.substring(0, 8)}...)`;
    } else if (selectedPid) {
      currentDisplayLabel = selectedPid;
    }

    // Build GPM Profiles list items cho Searchable Custom Dropdown
    let itemsHtml = '';
    gpmProfiles.forEach(prof => {
      const isSel = prof.id === selectedPid ? 'selected' : '';
      const label = `${prof.name || 'Profile'} (${prof.id.substring(0, 8)}...)`;
      itemsHtml += `
        <div class="gpm-dropdown-item ${isSel}" data-value="${prof.id}" data-label="${label}">
          <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${label}</span>
          ${isSel ? '<span style="color: var(--cyan); font-weight: bold; margin-left: 6px;">✓</span>' : ''}
        </div>
      `;
    });

    const isCurrentActive = pName === appState.active_project;
    const tr = document.createElement('tr');
    tr.setAttribute('data-project', pName);

    tr.innerHTML = `
      <td style="color: var(--text-dim); text-align: center; font-weight: 600;">${idx + 1}</td>
      <td>
        <div style="font-weight: 700; color: ${isCurrentActive ? 'var(--cyan)' : '#fff'}; font-size: 13px;">
          📁 ${pName} ${isCurrentActive ? '<span style="font-size: 10px; color: var(--emerald); font-weight: normal;">(Đang mở)</span>' : ''}
        </div>
        <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
          ${chCount > 0 ? `📺 ${chCount} kênh YouTube` : '<span style="color: var(--amber);">Chưa có kênh</span>'}
        </div>
      </td>
      <td>
        <!-- Searchable Custom Dropdown: Có ô tìm kiếm trực tiếp trong menu dropdown -->
        <div class="gpm-dropdown-wrapper" data-project="${pName}">
          <input type="hidden" class="sel-project-gpm-profile" data-project="${pName}" value="${selectedPid}">
          <div class="gpm-dropdown-trigger" data-project="${pName}">
            <span class="gpm-dropdown-trigger-text">${currentDisplayLabel}</span>
            <span class="gpm-dropdown-trigger-icon">▼</span>
          </div>
          <div class="gpm-dropdown-menu" data-project="${pName}">
            <div class="gpm-dropdown-search">
              <span class="gpm-dropdown-search-icon">🔍</span>
              <input type="text" class="gpm-search-input" data-project="${pName}" placeholder="Tìm kiếm profile..." autocomplete="off">
            </div>
            <div class="gpm-dropdown-items" data-project="${pName}">
              <div class="gpm-dropdown-item ${!selectedPid ? 'selected' : ''}" data-value="" data-label="-- Chưa gán Profile GPM --">
                <span>-- Chưa gán Profile GPM --</span>
                ${!selectedPid ? '<span style="color: var(--cyan); font-weight: bold; margin-left: 6px;">✓</span>' : ''}
              </div>
              ${itemsHtml}
            </div>
          </div>
        </div>
      </td>
      <td>
        <select class="select-control sel-project-quality" data-project="${pName}" style="width: 100%;">
          <option value="720" ${selectedQuality === '720' ? 'selected' : ''}>⚡ 720p (Siêu tốc)</option>
          <option value="1080" ${selectedQuality === '1080' ? 'selected' : ''}>🎬 1080p (Full HD)</option>
          <option value="720_fps" ${selectedQuality === '720_fps' ? 'selected' : ''}>🎞 720p Nén FPS</option>
        </select>
        <div class="fps-wrapper" data-project="${pName}" style="margin-top: 4px; display: ${selectedQuality === '720_fps' ? 'flex' : 'none'}; align-items: center; gap: 4px;">
          <span style="font-size: 11px; color: var(--cyan); font-weight: 600;">FPS:</span>
          <select class="select-control sel-project-fps" data-project="${pName}" style="font-size: 11px; padding: 2px 4px; width: 100%;">
            <option value="60" ${selectedFps === '60' ? 'selected' : ''}>60 FPS (scale 2)</option>
            <option value="120" ${selectedFps === '120' ? 'selected' : ''}>120 FPS (scale 6)</option>
            <option value="240" ${selectedFps === '240' ? 'selected' : ''}>240 FPS (scale 12)</option>
          </select>
        </div>
      </td>
      <td>
        <select class="select-control sel-project-process-mode" data-project="${pName}" style="width: 100%;">
          <option value="extend_61s" ${selectedMode === 'extend_61s' ? 'selected' : ''}>✂ Edit đủ 1m01s (≥61s FFmpeg)</option>
          <option value="direct" ${selectedMode === 'direct' ? 'selected' : ''}>⚡ Tải up luôn (Trực tiếp 0s)</option>
        </select>
      </td>
      <td style="text-align: center;">
        <div style="display: flex; gap: 4px; justify-content: center;">
          <button class="btn btn-emerald btn-sm btn-test-start-proj" data-project="${pName}">▶ Mở</button>
          <button class="btn btn-ruby btn-sm btn-test-stop-proj" data-project="${pName}">⏹ Đóng</button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Attach Custom Searchable Dropdown Interactions
  // 1. Toggle dropdown menu khi click trigger
  tbody.querySelectorAll('.gpm-dropdown-trigger').forEach(trigger => {
    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      const pName = trigger.getAttribute('data-project');
      const menu = tbody.querySelector(`.gpm-dropdown-menu[data-project="${CSS.escape(pName)}"]`);
      const isAlreadyActive = menu ? menu.classList.contains('active') : false;

      // Đóng tất cả menu khác
      document.querySelectorAll('.gpm-dropdown-menu.active').forEach(m => m.classList.remove('active'));
      document.querySelectorAll('.gpm-dropdown-trigger.active').forEach(t => t.classList.remove('active'));

      if (menu && !isAlreadyActive) {
        menu.classList.add('active');
        trigger.classList.add('active');

        // Reset search input & auto-focus
        const searchInput = menu.querySelector('.gpm-search-input');
        if (searchInput) {
          searchInput.value = '';
          menu.querySelectorAll('.gpm-dropdown-item').forEach(it => it.style.display = 'flex');
          setTimeout(() => searchInput.focus(), 60);
        }
      }
    });
  });

  // 2. Tìm kiếm bên trong dropdown
  tbody.querySelectorAll('.gpm-search-input').forEach(searchInput => {
    searchInput.addEventListener('click', (e) => e.stopPropagation());
    searchInput.addEventListener('input', (e) => {
      const pName = e.target.getAttribute('data-project');
      const kw = e.target.value.trim().toLowerCase();
      const menu = tbody.querySelector(`.gpm-dropdown-menu[data-project="${CSS.escape(pName)}"]`);
      if (!menu) return;

      const items = menu.querySelectorAll('.gpm-dropdown-item');
      let matched = 0;
      items.forEach(it => {
        const text = (it.getAttribute('data-label') || it.textContent || '').toLowerCase();
        const val = (it.getAttribute('data-value') || '').toLowerCase();
        if (!kw || text.includes(kw) || val.includes(kw)) {
          it.style.display = 'flex';
          matched++;
        } else {
          it.style.display = 'none';
        }
      });
    });

    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const pName = searchInput.getAttribute('data-project');
        const menu = tbody.querySelector(`.gpm-dropdown-menu[data-project="${CSS.escape(pName)}"]`);
        if (!menu) return;
        const visibleItems = Array.from(menu.querySelectorAll('.gpm-dropdown-item')).filter(it => it.style.display !== 'none');
        if (visibleItems.length > 0) {
          // Nếu có nhiều hơn 1 và item đầu là '-- Chưa gán --', ưu tiên item kết quả đầu tiên
          const targetItem = (visibleItems.length > 1 && visibleItems[0].getAttribute('data-value') === '') ? visibleItems[1] : visibleItems[0];
          targetItem.click();
        }
      }
    });
  });

  // 3. Chọn 1 item trong dropdown
  tbody.querySelectorAll('.gpm-dropdown-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.stopPropagation();
      const wrapper = item.closest('.gpm-dropdown-wrapper');
      if (!wrapper) return;
      const hiddenInput = wrapper.querySelector('.sel-project-gpm-profile');
      const triggerText = wrapper.querySelector('.gpm-dropdown-trigger-text');
      const menu = wrapper.querySelector('.gpm-dropdown-menu');
      const trigger = wrapper.querySelector('.gpm-dropdown-trigger');

      const val = item.getAttribute('data-value') || '';
      const label = item.getAttribute('data-label') || item.textContent.trim();

      if (hiddenInput) hiddenInput.value = val;
      if (triggerText) triggerText.textContent = label;

      wrapper.querySelectorAll('.gpm-dropdown-item').forEach(it => {
        it.classList.remove('selected');
        const check = it.querySelector('span:last-child');
        if (check && check.textContent.includes('✓')) check.remove();
      });

      item.classList.add('selected');
      if (!item.querySelector('span:last-child')?.textContent.includes('✓')) {
        item.insertAdjacentHTML('beforeend', '<span style="color: var(--cyan); font-weight: bold; margin-left: 6px;">✓</span>');
      }

      if (menu) menu.classList.remove('active');
      if (trigger) trigger.classList.remove('active');
    });
  });

  // 4. Click bên ngoài bảng tự động đóng mọi dropdown đang mở
  if (!window._gpmDropdownGlobalHandlerAttached) {
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.gpm-dropdown-wrapper')) {
        document.querySelectorAll('.gpm-dropdown-menu.active').forEach(m => m.classList.remove('active'));
        document.querySelectorAll('.gpm-dropdown-trigger.active').forEach(t => t.classList.remove('active'));
      }
    });
    window._gpmDropdownGlobalHandlerAttached = true;
  }

  // Attach change listeners for dynamic FPS dropdown display
  tbody.querySelectorAll('.sel-project-quality').forEach(sel => {
    sel.addEventListener('change', (e) => {
      const pName = e.target.getAttribute('data-project');
      const fpsWrap = tbody.querySelector(`.fps-wrapper[data-project="${CSS.escape(pName)}"]`);
      if (fpsWrap) {
        fpsWrap.style.display = e.target.value === '720_fps' ? 'flex' : 'none';
      }
    });
  });

  // Attach test start/stop button handlers
  tbody.querySelectorAll('.btn-test-start-proj').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const pName = e.target.getAttribute('data-project');
      const rowSel = tbody.querySelector(`.sel-project-gpm-profile[data-project="${CSS.escape(pName)}"]`);
      const pid = rowSel ? rowSel.value : '';
      if (!pid) {
        alert(`Vui lòng chọn Profile GPM cho dự án '${pName}' trước!`);
        return;
      }
      const res = await window.pywebview.api.test_start_gpm_profile(pid);
      if (res.success) {
        alert(`Đã khởi động GPM Profile [${pid}] cho dự án '${pName}' trên port ${res.port}`);
      } else {
        alert(`Lỗi mở GPM Profile: ${res.message}`);
      }
    });
  });

  tbody.querySelectorAll('.btn-test-stop-proj').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      const pName = e.target.getAttribute('data-project');
      const rowSel = tbody.querySelector(`.sel-project-gpm-profile[data-project="${CSS.escape(pName)}"]`);
      const pid = rowSel ? rowSel.value : '';
      if (!pid) {
        alert('Chưa chọn Profile GPM!');
        return;
      }
      await window.pywebview.api.test_stop_gpm_profile(pid);
      alert(`Đã gửi lệnh đóng GPM Profile [${pid}].`);
    });
  });

  // Re-apply current search filter if any
  const searchInput = document.getElementById('input-search-gpm-project');
  if (searchInput && searchInput.value) {
    filterTikTokProjectsTable(searchInput.value.trim().toLowerCase());
  }
}

async function saveTikTokConfigFromModal() {
  const globalCfg = appState.global_tiktok_config || {};
  globalCfg.upload_timeout = parseInt(document.getElementById('input-tiktok-upload-timeout').value) || 30;
  globalCfg.next_video_delay = parseInt(document.getElementById('input-tiktok-next-delay').value) || 180;
  const elGpmMode = document.getElementById('select-gpm-open-mode');
  if (elGpmMode) globalCfg.gpm_open_mode = elGpmMode.value;
  globalCfg.caption_mode = document.getElementById('select-caption-mode').value;

  const projectConfigs = {};

  document.querySelectorAll('#tbody-tiktok-projects tr').forEach(tr => {
    const pName = tr.getAttribute('data-project');
    if (!pName) return;

    const selGpm = tr.querySelector('.sel-project-gpm-profile');
    const selQuality = tr.querySelector('.sel-project-quality');
    const selFps = tr.querySelector('.sel-project-fps');
    const selMode = tr.querySelector('.sel-project-process-mode');

    const pid = selGpm ? selGpm.value : '';
    const match = (appState.gpm_profiles || []).find(p => p.id === pid);
    const pProfileName = match ? match.name : (pid ? pid.substring(0, 8) : '');

    projectConfigs[pName] = {
      profile_id: pid,
      profile_name: pProfileName,
      quality: selQuality ? selQuality.value : '720_fps',
      fps: selFps ? selFps.value : '120',
      process_mode: selMode ? selMode.value : 'direct'
    };
  });

  globalCfg.project_configs = projectConfigs;

  await window.pywebview.api.save_global_tiktok_config(globalCfg);
  appState.global_tiktok_config = globalCfg;
  appendLog(`💾 Đã lưu cấu hình TikTok Upload chung cho ${Object.keys(projectConfigs).length} dự án (1 Dự Án = 1 Profile GPM).`, 'success');
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
