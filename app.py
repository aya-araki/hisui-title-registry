#!/usr/bin/env python3
"""hisuiタイトル管理台帳 — タイトル別の進捗・フォーマット・スケジュール管理 + 請求書発行"""
import glob
import json
import os
from datetime import date

from flask import Flask, request, jsonify, render_template_string

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
DATA_PATH = os.path.join(DATA_DIR, "titles.json")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
INVOICES_PATH = os.path.join(DATA_DIR, "invoices.json")
CONTE_DIR = os.path.expanduser("~/spotting_tool/conte")
STAFF_KEY = os.environ.get("STAFF_KEY", "")

app = Flask(__name__)


def _load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_titles():
    return _load_json(DATA_PATH)


def _save_titles(data):
    _save_json(DATA_PATH, data)


def _load_config():
    return _load_json(CONFIG_PATH)


def _save_config(data):
    _save_json(CONFIG_PATH, data)


def _load_invoices():
    data = _load_json(INVOICES_PATH)
    if isinstance(data, list):
        return data
    return data.get("invoices", [])


def _save_invoices(invoices):
    _save_json(INVOICES_PATH, {"invoices": invoices})


def _ocr_status(code):
    if not os.path.exists(CONTE_DIR):
        return []
    pattern = os.path.join(CONTE_DIR, f"{code}*.json")
    files = sorted(glob.glob(pattern))
    episodes = []
    for fp in files:
        name = os.path.splitext(os.path.basename(fp))[0]
        ep = name.replace(code, "")
        if ep:
            episodes.append(ep)
    return episodes


def _next_invoice_id(invoices, year_month):
    existing = [inv for inv in invoices if inv.get("id", "").startswith(year_month)]
    seq = len(existing) + 1
    return f"{year_month}-{seq:03d}"


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
HTML = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>hisuiタイトル管理台帳</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
:root {
  --bg:#111119; --bg2:#1c1c2e; --surface:#242438; --surface-hover:#2e2e46;
  --border:#33334d; --fg:#d4d4e8; --fg-muted:#8888a8;
  --accent:#c8a44e; --accent-dim:#9a7d3a;
  --green:#5cb87a; --green-dim:rgba(92,184,122,0.15);
  --yellow:#d4a853; --yellow-dim:rgba(212,168,83,0.15);
  --red:#d45353; --red-dim:rgba(212,83,83,0.12);
  --blue:#5b8fd4; --blue-dim:rgba(91,143,212,0.15);
}
body { font-family:-apple-system,"Helvetica Neue","Hiragino Sans",sans-serif; background:var(--bg); color:var(--fg); font-size:13px; line-height:1.5; }

/* --- Header + Tabs --- */
.header { padding:16px 32px 0; border-bottom:1px solid var(--border); }
.header-top { display:flex; align-items:baseline; gap:12px; margin-bottom:12px; }
.header h1 { font-size:18px; font-weight:700; letter-spacing:0.02em; color:var(--accent); }
.header .sub { color:var(--fg-muted); font-size:11px; }
.tabs { display:flex; gap:0; }
.tab-btn { padding:8px 20px; font-size:13px; font-weight:600; border:none; background:transparent; color:var(--fg-muted); cursor:pointer; border-bottom:2px solid transparent; font-family:inherit; }
.tab-btn:hover { color:var(--fg); }
.tab-btn.active { color:var(--accent); border-bottom-color:var(--accent); }
.tab-content { display:none; }
.tab-content.active { display:block; }

/* --- Buttons --- */
button { padding:6px 14px; border:1px solid var(--border); border-radius:4px; font-size:12px; font-weight:600; cursor:pointer; font-family:inherit; background:var(--surface); color:var(--fg); transition:background 0.15s; }
button:hover { background:var(--surface-hover); }
.btn-accent { background:var(--accent); color:var(--bg); border-color:var(--accent); }
.btn-accent:hover { filter:brightness(1.1); }
.btn-danger { background:transparent; color:var(--red); border-color:var(--red); }
.btn-danger:hover { background:var(--red-dim); }
.btn-green { background:var(--green); color:var(--bg); border-color:var(--green); }
.btn-green:hover { filter:brightness(1.1); }

.toolbar { padding:12px 32px; display:flex; gap:8px; border-bottom:1px solid var(--border); }
.main { padding:16px 32px; }

/* --- Title Cards --- */
.title-grid { display:flex; flex-direction:column; gap:12px; }
.title-card { background:var(--surface); border:1px solid var(--border); border-radius:6px; overflow:hidden; }
.title-card:hover { border-color:var(--accent-dim); }
.card-summary { display:grid; grid-template-columns:60px 1fr 80px 120px repeat(3,80px) 100px 40px; align-items:center; gap:12px; padding:12px 16px; cursor:pointer; user-select:none; }
.card-summary:hover { background:var(--surface-hover); }
.code { font-family:"SF Mono","Menlo",monospace; font-size:14px; font-weight:700; color:var(--accent); }
.title-name { font-size:14px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.client-name { font-size:11px; color:var(--fg-muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.ep-count { font-size:12px; color:var(--fg-muted); text-align:center; }
.progress-cell { display:flex; flex-direction:column; align-items:center; gap:3px; }
.progress-label { font-size:9px; text-transform:uppercase; letter-spacing:0.06em; color:var(--fg-muted); }
.progress-bar-wrap { width:100%; height:4px; background:var(--bg2); border-radius:2px; overflow:hidden; }
.progress-bar-fill { height:100%; border-radius:2px; transition:width 0.3s; }
.progress-num { font-size:11px; font-variant-numeric:tabular-nums; }
.format-summary { font-family:"SF Mono","Menlo",monospace; font-size:11px; color:var(--fg-muted); text-align:right; }
.chevron { text-align:center; color:var(--fg-muted); font-size:14px; transition:transform 0.2s; }
.title-card.open .chevron { transform:rotate(90deg); }
.card-detail { display:none; border-top:1px solid var(--border); padding:16px 20px; background:var(--bg2); }
.title-card.open .card-detail { display:block; }
.detail-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
.detail-section h3 { font-size:11px; text-transform:uppercase; letter-spacing:0.08em; color:var(--accent); margin-bottom:8px; padding-bottom:4px; border-bottom:1px solid var(--border); }
.field-row { display:flex; align-items:center; gap:8px; margin-bottom:6px; }
.field-label { font-size:11px; color:var(--fg-muted); min-width:90px; flex-shrink:0; }
.field-value { font-size:12px; color:var(--fg); }
.field-value a { color:var(--blue); text-decoration:none; }
.field-value a:hover { text-decoration:underline; }
.tag { display:inline-block; padding:1px 6px; border-radius:3px; font-size:10px; font-weight:600; }
.tag-yes { background:var(--green-dim); color:var(--green); }
.tag-no { background:var(--red-dim); color:var(--red); }
.ocr-chips { display:flex; flex-wrap:wrap; gap:4px; }
.ocr-chip { padding:2px 6px; border-radius:3px; font-size:10px; font-family:"SF Mono","Menlo",monospace; background:var(--green-dim); color:var(--green); }
.detail-actions { margin-top:12px; padding-top:12px; border-top:1px solid var(--border); display:flex; gap:8px; }
.notes-text { font-size:12px; color:var(--fg); white-space:pre-wrap; background:var(--surface); padding:6px 10px; border-radius:4px; }

/* --- Modal --- */
.modal-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:100; justify-content:center; align-items:flex-start; padding-top:40px; }
.modal-overlay.show { display:flex; }
.modal { background:var(--bg2); border:1px solid var(--border); border-radius:8px; width:600px; max-height:85vh; overflow-y:auto; padding:24px; }
.modal h2 { font-size:16px; margin-bottom:16px; color:var(--accent); }
.form-group { margin-bottom:12px; }
.form-group label { display:block; font-size:11px; color:var(--fg-muted); margin-bottom:3px; text-transform:uppercase; letter-spacing:0.04em; }
.form-group input[type=text],.form-group input[type=number],.form-group input[type=date],.form-group textarea,.form-group select {
  width:100%; background:var(--surface); border:1px solid var(--border); color:var(--fg); padding:7px 10px; border-radius:4px; font-size:13px; font-family:inherit; }
.form-group textarea { resize:vertical; min-height:50px; }
.form-group input:focus,.form-group textarea:focus,.form-group select:focus { outline:none; border-color:var(--accent); }
.form-group select { appearance:auto; }
.form-row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.form-row-3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:12px; }
.form-section { margin-top:16px; padding-top:12px; border-top:1px solid var(--border); }
.form-section h3 { font-size:12px; color:var(--accent); margin-bottom:10px; }
.toggle-row { display:flex; align-items:center; gap:10px; margin-bottom:8px; }
.toggle-row label.toggle-label { min-width:80px; text-transform:none; font-size:12px; color:var(--fg); margin-bottom:0; }
.toggle-row input[type=checkbox] { accent-color:var(--accent); width:16px; height:16px; }
.toggle-row input[type=number] { width:60px; background:var(--surface); border:1px solid var(--border); color:var(--fg); padding:4px 8px; border-radius:4px; font-size:12px; }
.toggle-row .sec-label { font-size:11px; color:var(--fg-muted); }
.modal-actions { margin-top:20px; display:flex; justify-content:flex-end; gap:8px; }
.empty-state { text-align:center; padding:60px 20px; color:var(--fg-muted); }
.empty-state p { font-size:14px; margin-bottom:16px; }

/* --- Invoice List --- */
.inv-table { width:100%; border-collapse:collapse; }
.inv-table th { font-size:11px; text-transform:uppercase; letter-spacing:0.06em; color:var(--fg-muted); text-align:left; padding:8px 12px; border-bottom:1px solid var(--border); }
.inv-table td { padding:8px 12px; border-bottom:1px solid var(--border); font-size:13px; }
.inv-table tr:hover td { background:var(--surface-hover); }
.inv-amount { font-variant-numeric:tabular-nums; text-align:right; }

/* --- Invoice Items Table --- */
.items-table { width:100%; border-collapse:collapse; margin:12px 0; }
.items-table th { font-size:11px; color:var(--fg-muted); text-align:left; padding:6px 8px; border-bottom:1px solid var(--border); }
.items-table td { padding:4px 8px; }
.items-table input { background:var(--surface); border:1px solid var(--border); color:var(--fg); padding:5px 8px; border-radius:3px; font-size:12px; font-family:inherit; }
.items-table input[type=text] { width:100%; }
.items-table input[type=number] { width:90px; text-align:right; font-variant-numeric:tabular-nums; }
.item-amount { font-size:13px; font-variant-numeric:tabular-nums; text-align:right; min-width:80px; color:var(--fg); }
.totals-section { display:flex; justify-content:flex-end; margin-top:8px; }
.totals-box { min-width:240px; }
.total-row { display:flex; justify-content:space-between; padding:4px 0; font-size:13px; font-variant-numeric:tabular-nums; }
.total-row.grand { font-size:15px; font-weight:700; color:var(--accent); border-top:2px solid var(--accent); padding-top:8px; margin-top:4px; }

/* --- Settings --- */
.settings-card { background:var(--surface); border:1px solid var(--border); border-radius:6px; padding:20px 24px; margin-bottom:16px; }
.settings-card h3 { font-size:13px; color:var(--accent); margin-bottom:12px; }
</style>
</head>
<body>

<div class="header">
  <div class="header-top">
    <h1>hisui タイトル管理台帳</h1>
    <span class="sub">株式会社飛翠</span>
  </div>
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('titles')">タイトル管理</button>
    <button class="tab-btn" onclick="switchTab('invoices')">請求書</button>
    <button class="tab-btn" onclick="switchTab('settings')">設定</button>
  </div>
</div>

<!-- ===================== TAB 1: TITLES ===================== -->
<div class="tab-content active" id="tab-titles">
  <div class="toolbar">
    <button class="btn-accent" onclick="openTitleModal()">+ タイトル追加</button>
    <button onclick="refreshAll()">更新</button>
  </div>
  <div class="main">
    <div class="title-grid" id="titleGrid">
      <div class="empty-state"><p>タイトルを追加してください</p></div>
    </div>
  </div>
</div>

<!-- ===================== TAB 2: INVOICES ===================== -->
<div class="tab-content" id="tab-invoices">
  <div class="toolbar">
    <button class="btn-accent" onclick="newInvoice()">+ 新規請求書</button>
  </div>
  <div class="main">
    <!-- Invoice List -->
    <div id="invoiceListView">
      <table class="inv-table" id="invoiceTable">
        <thead><tr><th>請求番号</th><th>請求日</th><th>請求先</th><th style="text-align:right">金額（税込）</th><th></th></tr></thead>
        <tbody id="invoiceListBody"></tbody>
      </table>
    </div>
    <!-- Invoice Create/Edit -->
    <div id="invoiceEditView" style="display:none">
      <div style="display:flex;gap:12px;align-items:center;margin-bottom:16px;">
        <button onclick="cancelInvoiceEdit()">← 戻る</button>
        <h2 style="font-size:16px;color:var(--accent)" id="invEditTitle">新規請求書</h2>
      </div>
      <div class="form-row-3">
        <div class="form-group">
          <label>請求先</label>
          <select id="invClient" onchange="onInvClientChange()"><option value="">選択...</option></select>
        </div>
        <div class="form-group">
          <label>請求日</label>
          <input type="date" id="invDate">
        </div>
        <div class="form-group">
          <label>請求番号</label>
          <input type="text" id="invId" placeholder="自動生成">
        </div>
      </div>
      <div class="form-group">
        <label>請求先名（印刷用・御中自動付与）</label>
        <input type="text" id="invClientFull" placeholder="株式会社○○">
      </div>

      <h3 style="font-size:12px;color:var(--accent);margin:16px 0 8px;">明細</h3>
      <table class="items-table">
        <thead><tr><th style="width:11%">PJT No</th><th style="width:22%">作品名</th><th style="width:13%">内容</th><th style="width:17%">単価</th><th style="width:10%">単位</th><th style="width:17%;text-align:right">金額</th><th style="width:5%"></th></tr></thead>
        <tbody id="invItemsBody"></tbody>
      </table>
      <button onclick="addInvItem()" style="margin-top:4px;font-size:11px;">+ 行追加</button>

      <div class="totals-section">
        <div class="totals-box">
          <div class="total-row"><span>小計</span><span id="invSubtotal">¥0</span></div>
          <div class="total-row"><span>消費税（<span id="invTaxRateLabel">10</span>%）</span><span id="invTax">¥0</span></div>
          <div class="total-row grand"><span>合計</span><span id="invTotal">¥0</span></div>
        </div>
      </div>

      <div class="form-group" style="margin-top:16px;">
        <label>備考</label>
        <textarea id="invRemarks" rows="2" placeholder="お支払い期限等"></textarea>
      </div>

      <div style="display:flex;gap:8px;margin-top:20px;">
        <button class="btn-accent" onclick="saveInvoice()">保存</button>
        <button class="btn-green" onclick="printInvoice()">印刷プレビュー</button>
      </div>
    </div>
  </div>
</div>

<!-- ===================== TAB 3: SETTINGS ===================== -->
<div class="tab-content" id="tab-settings">
  <div class="main">
    <div class="settings-card">
      <h3>会社情報</h3>
      <div class="form-row">
        <div class="form-group"><label>会社名</label><input type="text" id="cfgCompany" placeholder="株式会社飛翠"></div>
        <div class="form-group"><label>登録番号（インボイス）</label><input type="text" id="cfgRegNum" placeholder="T1234567890123"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>郵便番号</label><input type="text" id="cfgPostal" placeholder="〒000-0000"></div>
        <div class="form-group"><label>TEL</label><input type="text" id="cfgTel"></div>
      </div>
      <div class="form-group"><label>住所</label><input type="text" id="cfgAddress"></div>
    </div>
    <div class="settings-card">
      <h3>振込先</h3>
      <div class="form-row">
        <div class="form-group"><label>銀行名</label><input type="text" id="cfgBank"></div>
        <div class="form-group"><label>支店名</label><input type="text" id="cfgBranch"></div>
      </div>
      <div class="form-row-3">
        <div class="form-group">
          <label>口座種別</label>
          <select id="cfgAcctType"><option>普通</option><option>当座</option></select>
        </div>
        <div class="form-group"><label>口座番号</label><input type="text" id="cfgAcctNum"></div>
        <div class="form-group"><label>口座名義</label><input type="text" id="cfgAcctHolder"></div>
      </div>
    </div>
    <div class="settings-card">
      <h3>税率</h3>
      <div class="form-group" style="max-width:120px;">
        <label>消費税率（%）</label>
        <input type="number" id="cfgTaxRate" value="10" min="0" max="100">
      </div>
    </div>
    <button class="btn-accent" onclick="saveConfig()">設定を保存</button>
  </div>
</div>

<!-- ===================== TITLE MODAL ===================== -->
<div class="modal-overlay" id="titleModalOverlay" onclick="if(event.target===this)closeTitleModal()">
<div class="modal">
  <h2 id="titleModalTitle">タイトル追加</h2>
  <div class="form-row-3">
    <div class="form-group"><label>作品コード</label><input type="text" id="fCode" placeholder="SD, BKY等"></div>
    <div class="form-group"><label>タイトル名</label><input type="text" id="fTitle" placeholder="サカモトデイズ"></div>
    <div class="form-group"><label>請求先</label><input type="text" id="fClient" placeholder="制作会社名"></div>
  </div>
  <div class="form-row">
    <div class="form-group"><label>話数構成</label><input type="number" id="fEpisodes" min="1" value="12"></div>
    <div class="form-group"><label>編集費（1話単価）</label><input type="number" id="fFee" min="0" step="1000" placeholder="50000"></div>
  </div>
  <div class="form-row">
    <div class="form-group"><label>フォーマットリンク</label><input type="text" id="fFormatLink" placeholder="URL"></div>
    <div class="form-group"><label>Qシートリンク</label><input type="text" id="fQsheetLink" placeholder="URL"></div>
  </div>
  <div class="form-group"><label>スケジュール</label><input type="text" id="fSchedule" placeholder="放送開始日・納品締切等"></div>
  <div class="form-row">
    <div class="form-group"><label>納品進捗（話数）</label><input type="number" id="fDelivery" min="0" value="0"></div>
    <div class="form-group"><label>CT進捗（話数）</label><input type="number" id="fCt" min="0" value="0"></div>
  </div>
  <div class="form-section">
    <h3>フォーマット情報</h3>
    <div class="form-group"><label>本編尺</label><input type="text" id="fHonpen" placeholder="23:40"></div>
    <div class="toggle-row"><label class="toggle-label">サブタイトル</label><input type="checkbox" id="fSubtitle"><input type="number" id="fSubtitleSec" min="0" value="0" step="1"><span class="sec-label">秒</span></div>
    <div class="toggle-row"><label class="toggle-label">アイキャッチ</label><input type="checkbox" id="fEyecatch"><input type="number" id="fEyecatchSec" min="0" value="0" step="1"><span class="sec-label">秒</span></div>
    <div class="toggle-row"><label class="toggle-label">予告</label><input type="checkbox" id="fYokoku"><input type="number" id="fYokokuSec" min="0" value="0" step="1"><span class="sec-label">秒</span></div>
  </div>
  <div class="form-group" style="margin-top:12px;"><label>特記事項</label><textarea id="fNotes" rows="3" placeholder="フォーマット・作業上の注意点等"></textarea></div>
  <div class="modal-actions">
    <button onclick="closeTitleModal()">キャンセル</button>
    <button class="btn-accent" onclick="saveTitle()">保存</button>
  </div>
</div>
</div>

<script>
/* ===================== STATE ===================== */
const STAFF_MODE = {{ staff_mode }};
let titles = {};
let config = {};
let invoices = [];
let editingTitleCode = null;
let editingInvoiceIdx = -1;
let invItems = [];

/* ===================== TABS ===================== */
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.querySelector(`.tab-btn[onclick="switchTab('${name}')"]`).classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
  if (name === 'invoices') refreshInvoices();
  if (name === 'settings') loadConfigUI();
}

/* ===================== TITLES ===================== */
async function refreshAll() {
  const r = await fetch('/api/titles');
  titles = await r.json();
  renderTitles();
}

function renderTitles() {
  const grid = document.getElementById('titleGrid');
  const codes = Object.keys(titles).sort();
  if (!codes.length) { grid.innerHTML = '<div class="empty-state"><p>タイトルを追加してください</p></div>'; return; }
  grid.innerHTML = codes.map(code => {
    const t = titles[code];
    const total = t.total_episodes || 1;
    const delPct = Math.round((t.delivery_progress||0)/total*100);
    const ctPct = Math.round((t.ct_progress||0)/total*100);
    const ocrEps = t._ocr_episodes || [];
    const ocrPct = Math.round(ocrEps.length/total*100);
    const honpen = t.format?.honpen_jaku || '-';
    const pb = (label,num,tot,pct,color) => `<div class="progress-cell"><span class="progress-label">${label}</span><div class="progress-bar-wrap"><div class="progress-bar-fill" style="width:${pct}%;background:var(--${color})"></div></div><span class="progress-num">${num}/${tot}</span></div>`;
    const fmt = t.format || {};
    return `
    <div class="title-card" id="card-${code}">
      <div class="card-summary" onclick="toggleCard('${code}')">
        <span class="code">${code}</span>
        <span class="title-name">${esc(t.title||'')}</span>
        <span class="client-name">${esc(t.client||'')}</span>
        <span class="ep-count">全${total}話</span>
        ${pb('納品',t.delivery_progress||0,total,delPct,'green')}
        ${pb('CT',t.ct_progress||0,total,ctPct,'blue')}
        ${pb('OCR',ocrEps.length,total,ocrPct,'yellow')}
        <span class="format-summary">${honpen}</span>
        <span class="chevron">▸</span>
      </div>
      <div class="card-detail">
        <div class="detail-grid">
          <div class="detail-section">
            <h3>基本情報</h3>
            <div class="field-row"><span class="field-label">請求先</span><span class="field-value">${esc(t.client||'-')}</span></div>
            ${STAFF_MODE ? '' : '<div class="field-row"><span class="field-label">編集費</span><span class="field-value">'+(t.editing_fee ? '¥'+Number(t.editing_fee).toLocaleString()+'/話' : '-')+'</span></div>'}
            <div class="field-row"><span class="field-label">スケジュール</span><span class="field-value">${esc(t.schedule||'-')}</span></div>
            <div class="field-row"><span class="field-label">フォーマット</span><span class="field-value">${t.format_link ? '<a href="'+esc(t.format_link)+'" target="_blank">開く</a>' : '-'}</span></div>
            <div class="field-row"><span class="field-label">Qシート</span><span class="field-value">${t.qsheet_link ? '<a href="'+esc(t.qsheet_link)+'" target="_blank">開く</a>' : '-'}</span></div>
            <div class="field-row"><span class="field-label">OCR済み</span><span class="field-value">${ocrEps.length ? '<div class="ocr-chips">'+ocrEps.map(e=>'<span class="ocr-chip">'+e+'</span>').join('')+'</div>' : '<span style="color:var(--fg-muted)">なし</span>'}</span></div>
          </div>
          <div class="detail-section">
            <h3>フォーマット</h3>
            <div class="field-row"><span class="field-label">本編尺</span><span class="field-value">${fmt.honpen_jaku||'-'}</span></div>
            <div class="field-row"><span class="field-label">サブタイトル</span><span class="field-value">${fmt.subtitle?.enabled?'<span class="tag tag-yes">有 '+fmt.subtitle.seconds+'秒</span>':'<span class="tag tag-no">無</span>'}</span></div>
            <div class="field-row"><span class="field-label">アイキャッチ</span><span class="field-value">${fmt.eyecatch?.enabled?'<span class="tag tag-yes">有 '+fmt.eyecatch.seconds+'秒</span>':'<span class="tag tag-no">無</span>'}</span></div>
            <div class="field-row"><span class="field-label">予告</span><span class="field-value">${fmt.yokoku?.enabled?'<span class="tag tag-yes">有 '+fmt.yokoku.seconds+'秒</span>':'<span class="tag tag-no">無</span>'}</span></div>
          </div>
        </div>
        ${t.notes ? '<div style="margin-top:12px;"><span class="field-label">特記事項</span><div class="notes-text">'+esc(t.notes)+'</div></div>' : ''}
        <div class="detail-actions"><button onclick="editTitle('${code}')">編集</button><button class="btn-danger" onclick="deleteTitle('${code}')">削除</button></div>
      </div>
    </div>`;
  }).join('');
}

function esc(s) { const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function toggleCard(code) { document.getElementById('card-'+code)?.classList.toggle('open'); }

function openTitleModal(existing) {
  editingTitleCode = existing ? existing.code : null;
  document.getElementById('titleModalTitle').textContent = existing ? 'タイトル編集' : 'タイトル追加';
  const el = id => document.getElementById(id);
  el('fCode').value = existing?.code||''; el('fCode').disabled = !!existing;
  el('fTitle').value = existing?.title||'';
  el('fClient').value = existing?.client||'';
  el('fEpisodes').value = existing?.total_episodes||12;
  el('fFee').value = existing?.editing_fee||'';
  el('fFormatLink').value = existing?.format_link||'';
  el('fQsheetLink').value = existing?.qsheet_link||'';
  el('fSchedule').value = existing?.schedule||'';
  el('fDelivery').value = existing?.delivery_progress||0;
  el('fCt').value = existing?.ct_progress||0;
  const fmt = existing?.format||{};
  el('fHonpen').value = fmt.honpen_jaku||'';
  el('fSubtitle').checked = fmt.subtitle?.enabled||false;
  el('fSubtitleSec').value = fmt.subtitle?.seconds||0;
  el('fEyecatch').checked = fmt.eyecatch?.enabled||false;
  el('fEyecatchSec').value = fmt.eyecatch?.seconds||0;
  el('fYokoku').checked = fmt.yokoku?.enabled||false;
  el('fYokokuSec').value = fmt.yokoku?.seconds||0;
  el('fNotes').value = existing?.notes||'';
  el('titleModalOverlay').classList.add('show');
}
function closeTitleModal() { document.getElementById('titleModalOverlay').classList.remove('show'); editingTitleCode=null; }
function editTitle(code) { openTitleModal({code,...titles[code]}); }

async function saveTitle() {
  const el = id => document.getElementById(id);
  const code = (editingTitleCode||el('fCode').value).trim().toUpperCase();
  if (!code) { alert('作品コードを入力してください'); return; }
  const existingFee = editingTitleCode && titles[editingTitleCode] ? titles[editingTitleCode].editing_fee : 0;
  const data = {
    title: el('fTitle').value, client: el('fClient').value,
    total_episodes: parseInt(el('fEpisodes').value)||12,
    editing_fee: STAFF_MODE ? (existingFee||0) : (parseInt(el('fFee').value)||0),
    format_link: el('fFormatLink').value, qsheet_link: el('fQsheetLink').value,
    schedule: el('fSchedule').value,
    delivery_progress: parseInt(el('fDelivery').value)||0,
    ct_progress: parseInt(el('fCt').value)||0,
    format: {
      honpen_jaku: el('fHonpen').value,
      subtitle:{enabled:el('fSubtitle').checked, seconds:parseInt(el('fSubtitleSec').value)||0},
      eyecatch:{enabled:el('fEyecatch').checked, seconds:parseInt(el('fEyecatchSec').value)||0},
      yokoku:{enabled:el('fYokoku').checked, seconds:parseInt(el('fYokokuSec').value)||0},
    },
    notes: el('fNotes').value,
  };
  await fetch('/api/titles',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code,...data})});
  closeTitleModal(); refreshAll();
}

async function deleteTitle(code) {
  if (!confirm(code+' を削除しますか？')) return;
  await fetch('/api/titles/'+code,{method:'DELETE'}); refreshAll();
}

/* ===================== INVOICES ===================== */
async function refreshInvoices() {
  const r = await fetch('/api/invoices');
  invoices = await r.json();
  renderInvoiceList();
}

function renderInvoiceList() {
  const body = document.getElementById('invoiceListBody');
  if (!invoices.length) {
    body.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--fg-muted);padding:40px;">請求書がありません</td></tr>';
    return;
  }
  body.innerHTML = invoices.map((inv,i) => `<tr>
    <td style="font-family:monospace;">${esc(inv.id||'')}</td>
    <td>${esc(inv.date||'')}</td>
    <td>${esc(inv.client_full||inv.client||'')}</td>
    <td class="inv-amount">¥${(inv.total||0).toLocaleString()}</td>
    <td style="text-align:right">
      <button onclick="editInvoice(${i})" style="font-size:11px;padding:3px 8px;">編集</button>
      <button class="btn-green" onclick="printSavedInvoice(${i})" style="font-size:11px;padding:3px 8px;">印刷</button>
      <button class="btn-danger" onclick="deleteInvoice(${i})" style="font-size:11px;padding:3px 8px;">削除</button>
    </td>
  </tr>`).join('');
}

function newInvoice() {
  editingInvoiceIdx = -1;
  document.getElementById('invEditTitle').textContent = '新規請求書';
  document.getElementById('invDate').value = new Date().toISOString().slice(0,10);
  document.getElementById('invId').value = '';
  document.getElementById('invClient').value = '';
  document.getElementById('invClientFull').value = '';
  document.getElementById('invRemarks').value = '';
  invItems = [{pjt_no:'',title_name:'',content:'',qty:1,price:0}];
  populateClientDropdown();
  renderInvItems();
  calcInvTotals();
  showInvoiceEdit(true);
}

function editInvoice(idx) {
  editingInvoiceIdx = idx;
  const inv = invoices[idx];
  document.getElementById('invEditTitle').textContent = '請求書編集';
  document.getElementById('invDate').value = inv.date||'';
  document.getElementById('invId').value = inv.id||'';
  document.getElementById('invClientFull').value = inv.client_full||'';
  document.getElementById('invRemarks').value = inv.remarks||'';
  invItems = (inv.items||[]).map(it => ({...it}));
  if (!invItems.length) invItems=[{name:'',qty:1,price:0}];
  populateClientDropdown();
  document.getElementById('invClient').value = inv.client||'';
  renderInvItems();
  calcInvTotals();
  showInvoiceEdit(true);
}

function showInvoiceEdit(show) {
  document.getElementById('invoiceListView').style.display = show ? 'none' : '';
  document.getElementById('invoiceEditView').style.display = show ? '' : 'none';
}

function cancelInvoiceEdit() { showInvoiceEdit(false); refreshInvoices(); }

function populateClientDropdown() {
  const clients = [...new Set(Object.values(titles).map(t=>t.client).filter(Boolean))];
  const sel = document.getElementById('invClient');
  sel.innerHTML = '<option value="">選択...</option>' + clients.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join('');
}

function onInvClientChange() {
  const client = document.getElementById('invClient').value;
  if (!client) return;
  document.getElementById('invClientFull').value = client;
  const clientTitles = Object.entries(titles).filter(([_,t])=>t.client===client);
  invItems = clientTitles.map(([code,t]) => ({
    pjt_no: code,
    title_name: t.title||code,
    content: '編集',
    qty: 1,
    price: parseInt(t.editing_fee)||0,
  }));
  if (!invItems.length) invItems=[{pjt_no:'',title_name:'',content:'',qty:1,price:0}];
  renderInvItems();
  calcInvTotals();
}

function renderInvItems() {
  const body = document.getElementById('invItemsBody');
  body.innerHTML = invItems.map((it,i) => `<tr>
    <td><input type="text" value="${esc(it.pjt_no||'')}" onchange="invItems[${i}].pjt_no=this.value" style="width:100%"></td>
    <td><input type="text" value="${esc(it.title_name||it.name||'')}" onchange="invItems[${i}].title_name=this.value" style="width:100%"></td>
    <td><input type="text" value="${esc(it.content||'')}" onchange="invItems[${i}].content=this.value" style="width:100%"></td>
    <td><input type="number" value="${it.price}" min="0" step="1000" onchange="invItems[${i}].price=parseFloat(this.value)||0;calcInvTotals()"></td>
    <td><input type="number" value="${it.qty}" min="0" step="0.01" onchange="invItems[${i}].qty=parseFloat(this.value)||0;calcInvTotals()" style="width:70px"></td>
    <td class="item-amount">¥${Math.floor(it.qty*it.price).toLocaleString()}</td>
    <td><button onclick="removeInvItem(${i})" style="padding:2px 6px;font-size:10px;color:var(--red);border-color:var(--red);">×</button></td>
  </tr>`).join('');
}

function addInvItem() { invItems.push({pjt_no:'',title_name:'',content:'',qty:1,price:0}); renderInvItems(); }
function removeInvItem(i) { invItems.splice(i,1); if(!invItems.length) invItems=[{pjt_no:'',title_name:'',content:'',qty:1,price:0}]; renderInvItems(); calcInvTotals(); }

function calcInvTotals() {
  const sub = invItems.reduce((s,it) => s + (it.qty*it.price), 0);
  const rate = parseInt(document.getElementById('cfgTaxRate')?.value) || config.tax_rate || 10;
  const tax = Math.floor(sub * rate / 100);
  document.getElementById('invSubtotal').textContent = '¥'+sub.toLocaleString();
  document.getElementById('invTax').textContent = '¥'+tax.toLocaleString();
  document.getElementById('invTotal').textContent = '¥'+(sub+tax).toLocaleString();
  document.getElementById('invTaxRateLabel').textContent = rate;
  return {sub, tax, total: sub+tax, rate};
}

async function saveInvoice() {
  const {sub,tax,total,rate} = calcInvTotals();
  const inv = {
    id: document.getElementById('invId').value || null,
    date: document.getElementById('invDate').value,
    client: document.getElementById('invClient').value,
    client_full: document.getElementById('invClientFull').value,
    items: invItems.filter(it => it.title_name || it.pjt_no || it.name),
    subtotal: sub, tax, total, tax_rate: rate,
    remarks: document.getElementById('invRemarks').value,
  };
  const r = await fetch('/api/invoices',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({invoice:inv, index: editingInvoiceIdx})
  });
  const res = await r.json();
  if (res.id) document.getElementById('invId').value = res.id;
  editingInvoiceIdx = res.index ?? editingInvoiceIdx;
  alert('保存しました: ' + (res.id||''));
}

async function deleteInvoice(idx) {
  if (!confirm('削除しますか？')) return;
  await fetch('/api/invoices/'+idx,{method:'DELETE'});
  refreshInvoices();
}

function printSavedInvoice(idx) {
  window.open('/invoice/print/' + idx, '_blank');
}

async function printInvoice() {
  await saveInvoice();
  window.open('/invoice/print/' + editingInvoiceIdx, '_blank');
}

/* ===================== SETTINGS ===================== */
async function loadConfigUI() {
  const r = await fetch('/api/config');
  config = await r.json();
  const el = id => document.getElementById(id);
  el('cfgCompany').value = config.company_name||'';
  el('cfgRegNum').value = config.reg_num||'';
  el('cfgPostal').value = config.postal||'';
  el('cfgAddress').value = config.address||'';
  el('cfgTel').value = config.tel||'';
  el('cfgBank').value = config.bank_name||'';
  el('cfgBranch').value = config.branch_name||'';
  el('cfgAcctType').value = config.acct_type||'普通';
  el('cfgAcctNum').value = config.acct_num||'';
  el('cfgAcctHolder').value = config.acct_holder||'';
  el('cfgTaxRate').value = config.tax_rate||10;
}

async function saveConfig() {
  const el = id => document.getElementById(id);
  config = {
    company_name: el('cfgCompany').value,
    reg_num: el('cfgRegNum').value,
    postal: el('cfgPostal').value,
    address: el('cfgAddress').value,
    tel: el('cfgTel').value,
    bank_name: el('cfgBank').value,
    branch_name: el('cfgBranch').value,
    acct_type: el('cfgAcctType').value,
    acct_num: el('cfgAcctNum').value,
    acct_holder: el('cfgAcctHolder').value,
    tax_rate: parseInt(el('cfgTaxRate').value)||10,
  };
  await fetch('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(config)});
  alert('保存しました');
}

/* ===================== INIT ===================== */
if (STAFF_MODE) {
  document.querySelectorAll('.tab-btn').forEach(b => {
    if (b.textContent === '請求書' || b.textContent === '設定') b.style.display = 'none';
  });
  document.getElementById('fFee').closest('.form-group').style.display = 'none';
}
refreshAll();
fetch('/api/config').then(r=>r.json()).then(c => config=c);
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template_string(HTML, staff_mode="false")


@app.route("/staff")
def staff_view():
    if STAFF_KEY and request.args.get("key") != STAFF_KEY:
        return "アクセスキーが必要です", 403
    return render_template_string(HTML, staff_mode="true")


@app.route("/api/titles")
def api_titles():
    data = _load_titles()
    for code, t in data.items():
        t["_ocr_episodes"] = _ocr_status(code)
    return jsonify(data)


@app.route("/api/titles", methods=["POST"])
def api_save_title():
    body = request.json
    code = body.pop("code", "").strip().upper()
    if not code:
        return jsonify(error="code required"), 400
    data = _load_titles()
    data[code] = body
    _save_titles(data)
    return jsonify(ok=True)


@app.route("/api/titles/<code>", methods=["DELETE"])
def api_delete_title(code):
    data = _load_titles()
    data.pop(code.upper(), None)
    _save_titles(data)
    return jsonify(ok=True)


@app.route("/api/config")
def api_get_config():
    return jsonify(_load_config())


@app.route("/api/config", methods=["POST"])
def api_save_config():
    _save_config(request.json)
    return jsonify(ok=True)


@app.route("/api/invoices")
def api_get_invoices():
    return jsonify(_load_invoices())


@app.route("/api/invoices", methods=["POST"])
def api_save_invoice():
    body = request.json
    inv = body["invoice"]
    idx = body.get("index", -1)
    all_inv = _load_invoices()

    if not inv.get("id"):
        ym = (inv.get("date") or date.today().isoformat())[:7].replace("-", "")
        inv["id"] = _next_invoice_id(all_inv, ym)

    if idx >= 0 and idx < len(all_inv):
        all_inv[idx] = inv
    else:
        all_inv.append(inv)
        idx = len(all_inv) - 1

    _save_invoices(all_inv)
    return jsonify(ok=True, id=inv["id"], index=idx)


@app.route("/api/invoices/<int:idx>", methods=["DELETE"])
def api_delete_invoice(idx):
    all_inv = _load_invoices()
    if 0 <= idx < len(all_inv):
        all_inv.pop(idx)
        _save_invoices(all_inv)
    return jsonify(ok=True)


PRINT_HTML = r"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<title>請求書 {{ inv.id }}</title>
<style>
@page { size:A4; margin:20mm; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"Hiragino Mincho ProN","Yu Mincho","MS Mincho",serif; font-size:11pt; color:#222; line-height:1.6; background:#fff; }
.page { max-width:170mm; margin:0 auto; padding:20px; background:#fff; }
h1 { text-align:center; font-size:22pt; letter-spacing:0.3em; margin:20px 0 24px; font-weight:400; }
.date-line { text-align:right; font-size:10pt; margin-bottom:20px; }
.parties { display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:20px; }
.to { font-size:14pt; border-bottom:2px solid #222; padding-bottom:4px; }
.onchu { font-size:11pt; margin-left:8px; }
.from { text-align:right; font-size:9pt; line-height:1.8; }
.from .name { font-size:12pt; font-weight:600; margin-bottom:4px; }
.reg-num { font-size:8.5pt; color:#666; margin-top:2px; }
.statement { font-size:10pt; margin-bottom:4px; }
.total-box { background:#f5f0e8; border:2px solid #222; text-align:center; padding:12px; margin:0 0 20px; font-size:16pt; letter-spacing:0.1em; }
.total-box .label { font-size:10pt; color:#555; display:block; margin-bottom:4px; }
table.items { width:100%; border-collapse:collapse; margin:0; }
table.items th { background:#f0ebe0; border:1px solid #bbb; padding:6px 10px; font-size:9pt; font-weight:600; text-align:center; }
table.items td { border:1px solid #bbb; padding:5px 10px; font-size:10pt; }
table.items td.r { text-align:right; font-variant-numeric:tabular-nums; }
table.items td.c { text-align:center; }
table.items tr.empty td { height:22px; }
.bottom-wrap { display:flex; width:100%; margin-top:0; }
.bank-section { flex:1; border:1px solid #bbb; border-top:none; padding:14px 16px; font-size:9pt; line-height:1.9; }
.subtotals { border-collapse:collapse; }
.subtotals td { border:1px solid #bbb; padding:5px 14px; font-size:10pt; }
.subtotals td.lbl { background:#f0ebe0; text-align:center; min-width:100px; font-weight:600; font-size:9.5pt; }
.subtotals td.val { text-align:right; font-variant-numeric:tabular-nums; min-width:110px; }
.remarks { margin-top:16px; font-size:9.5pt; }
.remarks .rtitle { font-weight:600; margin-bottom:4px; }
.print-btn { display:block; margin:20px auto; padding:10px 30px; font-size:14px; cursor:pointer; background:#c8a44e; color:#111; border:none; border-radius:4px; font-weight:600; }
@media print { .print-btn { display:none !important; } body { -webkit-print-color-adjust:exact; print-color-adjust:exact; } }
</style></head><body>
<button class="print-btn" onclick="window.print()">このページを印刷</button>
<div class="page">
  <h1>ご請求書</h1>
  <div class="date-line">請求日：{{ inv._date_jp }}</div>
  <div class="parties">
    <div><div class="to">{{ inv.client_full or inv.client }}<span class="onchu">御中</span></div></div>
    <div class="from">
      <div class="name">{{ cfg.company_name }}</div>
      {% if cfg.reg_num %}<div class="reg-num">登録番号: {{ cfg.reg_num }}</div>{% endif %}
      <div>{{ cfg.postal }} {{ cfg.address }}</div>
      {% if cfg.tel %}<div>Tel: {{ cfg.tel }}</div>{% endif %}
    </div>
  </div>
  <p class="statement">下記の通りご請求申し上げます。</p>
  <div class="total-box">
    <span class="label">ご請求金額（税込）</span>
    &yen;{{ "{:,}".format(inv.total|int) }}-
  </div>
  <table class="items">
    <thead><tr>
      <th style="width:12%">PJT No</th>
      <th style="width:22%">作品名</th>
      <th style="width:13%">内容</th>
      <th style="width:18%">単価</th>
      <th style="width:10%">単位</th>
      <th style="width:18%">金額</th>
    </tr></thead>
    <tbody>
    {% for it in inv['items'] %}
      <tr>
        <td class="c">{{ it.pjt_no }}</td>
        <td>{{ it.title_name }}</td>
        <td class="c">{{ it.content }}</td>
        <td class="r">&yen;{{ "{:,}".format(it.price|int) }}</td>
        <td class="r">{{ it.qty }}</td>
        <td class="r">&yen;{{ "{:,}".format((it.qty * it.price)|int) }}</td>
      </tr>
    {% endfor %}
    {% set pad = 10 - inv['items']|length %}
    {% if pad > 0 %}{% for _ in range(pad) %}
      <tr class="empty"><td></td><td></td><td></td><td></td><td></td><td></td></tr>
    {% endfor %}{% endif %}
    </tbody>
  </table>
  <div class="bottom-wrap">
    <div class="bank-section">
      <div style="text-align:center;margin-bottom:8px;">お手数ですが、お支払は下記銀行口座へ<br>お振込み下さいます様、お願い申し上げます。<br>誠に勝手ながら振込手数料は御社でご負担ください。</div>
      {% if cfg.bank_name %}
      <div style="text-align:center;margin-top:6px;">{{ cfg.bank_name }}　{{ cfg.branch_name }}<br>{{ cfg.acct_type or '普通' }}預金　{{ cfg.acct_num }}<br>口座名義　{{ cfg.acct_holder }}</div>
      {% endif %}
    </div>
    <table class="subtotals">
      <tr><td class="lbl">小計</td><td class="val">&yen;{{ "{:,}".format(inv.subtotal|int) }}</td></tr>
      <tr><td class="lbl">消費税({{ inv.tax_rate or 10 }}%)</td><td class="val">&yen;{{ "{:,}".format(inv.tax|int) }}</td></tr>
      <tr><td class="lbl">合計金額</td><td class="val">&yen;{{ "{:,}".format(inv.total|int) }}</td></tr>
    </table>
  </div>
  {% if inv.remarks %}
  <div class="remarks"><div class="rtitle">備考</div>{{ inv.remarks }}</div>
  {% endif %}
</div>
</body></html>"""


@app.route("/invoice/print/<int:idx>")
def invoice_print(idx):
    all_inv = _load_invoices()
    if idx < 0 or idx >= len(all_inv):
        return "not found", 404
    inv = all_inv[idx]
    d = inv.get("date", "")
    if d and len(d) >= 10:
        parts = d.split("-")
        inv["_date_jp"] = f"{parts[0]}年{int(parts[1])}月{int(parts[2])}日"
    else:
        inv["_date_jp"] = d
    for it in inv.get("items", []):
        it.setdefault("pjt_no", "")
        it.setdefault("title_name", it.get("name", ""))
        it.setdefault("content", "")
        it.setdefault("price", 0)
        it.setdefault("qty", 0)
    return render_template_string(PRINT_HTML, inv=inv, cfg=_load_config())


def main():
    port = int(os.environ.get("PORT", 5112))
    print(f"hisuiタイトル管理台帳: http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
