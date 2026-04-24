from __future__ import annotations

from html import escape

_THEME_CSS = """
:root {
  --bg-dark: #091728;
  --bg-dark-soft: #10253d;
  --bg-light: #eef3f8;
  --surface: rgba(9, 23, 40, 0.72);
  --surface-light: #ffffff;
  --surface-muted: #f6f9fc;
  --border-dark: rgba(134, 195, 255, 0.18);
  --border-light: rgba(29, 67, 104, 0.14);
  --text-dark: #eaf4ff;
  --text-light: #16324d;
  --text-muted: #6d8298;
  --accent: #69bcff;
  --accent-strong: #2d8cff;
  --accent-soft: rgba(105, 188, 255, 0.14);
  --success: #2cb67d;
  --warning: #ffb454;
  --danger: #ef6461;
  --radius-lg: 24px;
  --radius-md: 18px;
  --radius-sm: 12px;
  --shadow-soft: 0 20px 60px rgba(7, 20, 34, 0.16);
  --shadow-card: 0 14px 34px rgba(17, 41, 67, 0.12);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
  background: var(--bg-light);
  color: var(--text-light);
}
a { color: inherit; text-decoration: none; }
.app-shell {
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(96, 179, 255, 0.18), transparent 30%),
    linear-gradient(180deg, #f4f8fc 0%, #eaf0f7 100%);
}
.theme-dark.app-shell {
  background:
    radial-gradient(circle at top left, rgba(104, 185, 255, 0.28), transparent 26%),
    radial-gradient(circle at top right, rgba(40, 111, 176, 0.22), transparent 30%),
    linear-gradient(180deg, #08131f 0%, #102339 50%, #132a40 100%);
  color: var(--text-dark);
}
.app-frame {
  max-width: 1240px;
  margin: 0 auto;
  padding: 32px 24px 56px;
}
.page-stack {
  display: grid;
  gap: 24px;
}
.page-hero {
  position: relative;
  overflow: hidden;
  border-radius: 32px;
  padding: 32px;
  border: 1px solid var(--border-dark);
  background: linear-gradient(135deg, rgba(14, 35, 56, 0.96), rgba(17, 49, 78, 0.88));
  box-shadow: var(--shadow-soft);
}
.page-hero::after {
  content: "";
  position: absolute;
  inset: 0;
  background-image: linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
  background-size: 24px 24px;
  opacity: 0.4;
  pointer-events: none;
}
.page-hero > * { position: relative; z-index: 1; }
.hero-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
  gap: 24px;
  align-items: stretch;
}
.hero-grid-featured {
  grid-template-columns: minmax(0, 1.18fr) minmax(320px, 0.82fr);
}
.featured-latest-job {
  display: grid;
  gap: 18px;
  align-content: start;
  border-radius: 28px;
  padding: 26px;
  background: linear-gradient(180deg, rgba(7, 18, 31, 0.84), rgba(11, 31, 52, 0.76));
  border: 1px solid rgba(129, 196, 255, 0.18);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 20px 44px rgba(4, 14, 24, 0.28);
}
.featured-kicker {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 7px 12px;
  border-radius: 999px;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #c9e8ff;
  background: rgba(105, 188, 255, 0.14);
}
.featured-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: start;
}
.featured-title {
  margin: 8px 0 0;
  font-size: clamp(24px, 3vw, 34px);
  line-height: 1.08;
  font-weight: 800;
  word-break: break-all;
}
.featured-summary {
  margin: 0;
  color: rgba(234, 244, 255, 0.8);
  line-height: 1.75;
}
.featured-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.featured-metric {
  border-radius: 18px;
  padding: 14px 16px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(132, 194, 255, 0.12);
}
.featured-metric strong {
  display: block;
  margin-top: 10px;
  font-size: 28px;
  line-height: 1;
}
.hero-side-stack {
  display: grid;
  gap: 18px;
  align-content: start;
}
.compact-stats-grid .stat-card {
  padding: 18px;
  min-height: 122px;
}
.result-hero .hero-actions {
  margin-top: 0;
}
.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(105, 188, 255, 0.12);
  color: #bfe4ff;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.page-title {
  margin: 16px 0 10px;
  font-size: clamp(30px, 5vw, 48px);
  line-height: 1.05;
  font-weight: 800;
}
.page-subtitle {
  margin: 0;
  color: rgba(234, 244, 255, 0.78);
  font-size: 16px;
  line-height: 1.7;
  max-width: 680px;
}
.hero-actions, .page-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 24px;
}
.hero-actions .inline-form {
  display: inline-flex;
}
.hero-actions .button,
.hero-actions button {
  height: 46px;
  padding: 0 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  white-space: nowrap;
}
.button, button {
  border: 0;
  border-radius: 999px;
  padding: 12px 18px;
  cursor: pointer;
  font: inherit;
  transition: transform .18s ease, box-shadow .18s ease, background-color .18s ease;
}
.button:hover, button:hover { transform: translateY(-1px); }
.button-primary, .button-primary button, button.button-primary {
  background: linear-gradient(135deg, #5eb7ff, #2e8eff);
  color: #06192a;
  box-shadow: 0 12px 28px rgba(46, 142, 255, 0.28);
}
.button-secondary {
  background: rgba(255, 255, 255, 0.08);
  color: inherit;
  border: 1px solid rgba(255, 255, 255, 0.12);
}
.theme-light .button-secondary, .theme-light button.button-secondary {
  background: #f3f7fb;
  color: var(--text-light);
  border: 1px solid var(--border-light);
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}
.stat-card {
  border-radius: var(--radius-md);
  padding: 20px;
  border: 1px solid var(--border-dark);
  background: rgba(10, 25, 42, 0.48);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
}
.theme-light .stat-card {
  background: var(--surface-light);
  border-color: var(--border-light);
  box-shadow: var(--shadow-card);
}
.stat-label {
  color: rgba(234, 244, 255, 0.68);
  font-size: 13px;
}
.theme-light .stat-label { color: var(--text-muted); }
.stat-value {
  margin-top: 10px;
  font-size: 34px;
  font-weight: 800;
  line-height: 1;
}
.stat-meta {
  margin-top: 8px;
  font-size: 13px;
  color: rgba(234, 244, 255, 0.74);
}
.theme-light .stat-meta { color: var(--text-muted); }
.page-header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: end;
  gap: 16px;
}
.page-header-copy h1 {
  margin: 8px 0 0;
  font-size: 34px;
  line-height: 1.15;
}
.page-header-copy p {
  margin: 10px 0 0;
  color: var(--text-muted);
  max-width: 760px;
  line-height: 1.7;
}
.panel {
  border-radius: 24px;
  background: var(--surface-light);
  border: 1px solid var(--border-light);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}
.theme-dark .panel {
  background: rgba(10, 25, 42, 0.7);
  border-color: var(--border-dark);
  box-shadow: var(--shadow-soft);
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 20px 22px 0;
}
.panel-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
}
.panel-body {
  padding: 20px 22px 22px;
}
.panel-body > :first-child { margin-top: 0; }
.panel-body > :last-child { margin-bottom: 0; }
.data-table-wrapper {
  width: 100%;
  overflow-x: auto;
  margin-top: 18px;
}
.data-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 880px;
}
.data-table th,
.data-table td {
  padding: 14px 12px;
  border-bottom: 1px solid var(--border-light);
  text-align: left;
  vertical-align: middle;
  font-size: 14px;
}
.theme-dark .data-table th,
.theme-dark .data-table td {
  border-bottom-color: var(--border-dark);
}
.data-table thead th {
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}
.theme-dark .data-table thead th {
  color: rgba(234, 244, 255, 0.68);
}
.data-table tbody tr:last-child td {
  border-bottom: 0;
}
.data-table tbody tr:hover {
  background: rgba(45, 140, 255, 0.04);
}
.theme-dark .data-table tbody tr:hover {
  background: rgba(105, 188, 255, 0.06);
}
.weekly-order-cell {
  width: 72px;
  font-weight: 700;
}
.weekly-title-link, .weekly-title-text {
  display: inline-block;
  line-height: 1.6;
  word-break: break-word;
}
.weekly-title-link {
  color: var(--accent-strong);
}
.theme-dark .weekly-title-link {
  color: #9dd4ff;
}
.weekly-cover {
  display: block;
  width: 144px;
  height: 82px;
  border-radius: 14px;
  object-fit: cover;
  border: 1px solid var(--border-light);
  background: #edf3f9;
}
.theme-dark .weekly-cover {
  border-color: var(--border-dark);
  background: rgba(7, 20, 34, 0.78);
}
.weekly-actions {
  display: grid;
  gap: 12px;
  margin-bottom: 16px;
}
.weekly-threshold-banner {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(45, 140, 255, 0.18);
  background: rgba(45, 140, 255, 0.08);
}
.theme-dark .weekly-threshold-banner {
  border-color: rgba(105, 188, 255, 0.24);
  background: rgba(105, 188, 255, 0.1);
}
.weekly-threshold-banner strong {
  font-size: 14px;
}
.weekly-threshold-banner span {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-muted);
}
.theme-dark .weekly-threshold-banner span {
  color: rgba(234, 244, 255, 0.8);
}
.weekly-bulk-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.weekly-bulk-label {
  font-size: 14px;
  font-weight: 700;
}
.weekly-push-form {
  margin: 12px 0 4px;
}
.weekly-grade-select {
  min-width: 88px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid var(--border-light);
  background: #f5f9fd;
  color: var(--text-light);
  font: inherit;
}
.theme-dark .weekly-grade-select {
  border-color: var(--border-dark);
  background: rgba(7, 20, 34, 0.9);
  color: var(--text-dark);
}
.weekly-status {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
}
.weekly-status-pending {
  background: rgba(255, 180, 84, 0.18);
  color: #94611d;
}
.weekly-status-sent {
  background: rgba(44, 182, 125, 0.14);
  color: #1b7e55;
}
.theme-dark .weekly-status-pending {
  color: #ffd89c;
}
.theme-dark .weekly-status-sent {
  color: #b9f0d5;
}
.status-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 30px;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
}
.badge-neutral { background: #e9f2fb; color: #285275; }
.badge-success { background: rgba(44, 182, 125, 0.15); color: #1b7e55; }
.badge-warning { background: rgba(255, 180, 84, 0.2); color: #94611d; }
.badge-danger { background: rgba(239, 100, 97, 0.16); color: #9d3431; }
.badge-info { background: rgba(105, 188, 255, 0.16); color: #205f96; }
.content-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(300px, 0.85fr);
  gap: 20px;
}
.recent-job-list, .quick-link-list, .source-grid {
  display: grid;
  gap: 14px;
}
.recent-jobs-timeline {
  position: relative;
  display: grid;
  gap: 14px;
}
.recent-jobs-timeline::before {
  content: "";
  position: absolute;
  left: 15px;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: linear-gradient(180deg, rgba(45, 140, 255, 0.36), rgba(45, 140, 255, 0.08));
}
.recent-job-item {
  position: relative;
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.recent-job-node {
  position: relative;
  z-index: 1;
  width: 32px;
  height: 32px;
  border-radius: 999px;
  border: 2px solid rgba(45, 140, 255, 0.18);
  background: #f3f8fd;
  box-shadow: 0 0 0 6px rgba(105, 188, 255, 0.08);
}
.recent-job-node.status-success { background: rgba(44, 182, 125, 0.16); border-color: rgba(44, 182, 125, 0.4); }
.recent-job-node.status-failed { background: rgba(239, 100, 97, 0.16); border-color: rgba(239, 100, 97, 0.42); }
.recent-job-node.status-pending, .recent-job-node.status-running, .recent-job-node.status-partial_success {
  background: rgba(255, 180, 84, 0.16);
  border-color: rgba(255, 180, 84, 0.42);
}
.recent-job-card, .resource-card, .mini-card {
  display: grid;
  gap: 10px;
  padding: 18px;
  border-radius: 18px;
  border: 1px solid var(--border-light);
  background: var(--surface-muted);
}
.recent-job-card.is-latest {
  background: linear-gradient(180deg, #f8fbff 0%, #eef6ff 100%);
  border-color: rgba(45, 140, 255, 0.26);
  box-shadow: 0 18px 34px rgba(45, 140, 255, 0.08);
}
.resource-card:hover, .recent-job-card:hover, .mini-card:hover {
  border-color: rgba(45, 140, 255, 0.28);
  transform: translateY(-1px);
  transition: transform .18s ease, border-color .18s ease;
}
.timeline-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.timeline-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  color: var(--text-muted);
  font-size: 14px;
}
.timeline-summary strong {
  color: var(--text-light);
  margin-left: 6px;
}
.resource-meta, .muted-text {
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1.6;
}
.kicker {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--text-muted);
}
.resource-card h3, .recent-job-item h3, .mini-card h3 { margin: 0; }
.theme-dark .recent-job-card, .theme-dark .resource-card, .theme-dark .mini-card {
  background: rgba(8, 23, 38, 0.72);
  border-color: var(--border-dark);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
}
.theme-dark .recent-job-card.is-latest {
  background: linear-gradient(180deg, rgba(12, 34, 56, 0.92) 0%, rgba(10, 27, 45, 0.86) 100%);
  border-color: rgba(105, 188, 255, 0.3);
  box-shadow: 0 20px 40px rgba(4, 14, 24, 0.32);
}
.theme-dark .timeline-summary,
.theme-dark .resource-meta,
.theme-dark .muted-text,
.theme-dark .kicker,
.theme-dark .field label,
.theme-dark .field span.label,
.theme-dark .helper-note {
  color: rgba(234, 244, 255, 0.72);
}
.theme-dark .timeline-summary strong {
  color: var(--text-dark);
}
.form-panel form, .scheduler-form {
  display: grid;
  gap: 18px;
}
.field-grid {
  display: grid;
  gap: 16px;
}
.field {
  display: grid;
  gap: 8px;
}
.field label, .field span.label {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-muted);
}
input[type='text'], input[type='url'], input[type='time'], input[name='entry_url'], input[name='search_keyword'], input[name='max_items'] {
  width: 100%;
  border-radius: 14px;
  border: 1px solid var(--border-light);
  background: #fbfdff;
  padding: 13px 14px;
  font: inherit;
  color: var(--text-light);
  outline: none;
  transition: border-color .18s ease, box-shadow .18s ease;
}
.theme-dark input[type='text'], .theme-dark input[type='url'], .theme-dark input[type='time'], .theme-dark input[name='entry_url'], .theme-dark input[name='search_keyword'], .theme-dark input[name='max_items'] {
  border-color: var(--border-dark);
  background: rgba(6, 18, 30, 0.82);
  color: var(--text-dark);
}
.theme-dark input::placeholder {
  color: rgba(234, 244, 255, 0.42);
}
input:focus {
  border-color: rgba(45, 140, 255, 0.5);
  box-shadow: 0 0 0 4px rgba(105, 188, 255, 0.14);
}
.inline-form {
  display: inline;
}
.checkbox-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--border-light);
  background: #f7fbff;
}
.theme-dark .checkbox-row {
  border-color: var(--border-dark);
  background: rgba(7, 20, 34, 0.76);
}
.job-detail-layout {
  display: grid;
  gap: 20px;
}
.job-detail-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.9fr);
  gap: 20px;
}
.progress-panel .metrics-compact {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}
.metric-tile {
  border-radius: 16px;
  padding: 14px;
  background: #f4f8fc;
  border: 1px solid var(--border-light);
}
.theme-dark .metric-tile {
  background: rgba(7, 20, 34, 0.76);
  border-color: var(--border-dark);
}
.metric-tile strong {
  display: block;
  margin-top: 8px;
  font-size: 26px;
}
.report-links {
  display: grid;
  gap: 10px;
}
.log-panel ul {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
}
.job-error {
  margin: 0 0 14px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(239, 100, 97, 0.1);
  color: #7e2f2c;
}
.theme-dark .job-error {
  background: rgba(239, 100, 97, 0.16);
  color: #ffd0cd;
  border: 1px solid rgba(239, 100, 97, 0.24);
}
.empty-state {
  padding: 28px;
  border-radius: 18px;
  border: 1px dashed rgba(45, 140, 255, 0.25);
  background: linear-gradient(180deg, rgba(255,255,255,0.7), rgba(242,247,252,0.9));
  color: var(--text-muted);
  text-align: center;
}
.theme-dark .empty-state {
  border-color: rgba(105, 188, 255, 0.24);
  background: linear-gradient(180deg, rgba(9, 24, 39, 0.88), rgba(7, 18, 30, 0.92));
  color: rgba(234, 244, 255, 0.72);
}
.helper-note {
  font-size: 14px;
  color: var(--text-muted);
  line-height: 1.7;
}
.diagnostic-summary {
  margin: 0 0 16px;
  padding: 16px;
  border-radius: 16px;
  background: rgba(45, 140, 255, 0.06);
  border: 1px solid rgba(45, 140, 255, 0.16);
}
.theme-dark .diagnostic-summary {
  background: rgba(105, 188, 255, 0.08);
  border-color: rgba(105, 188, 255, 0.18);
}
.diagnostic-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 700;
}
.diagnostic-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 10px;
}
.diagnostic-item {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(29, 67, 104, 0.1);
}
.theme-dark .diagnostic-item {
  background: rgba(7, 20, 34, 0.72);
  border-color: rgba(134, 195, 255, 0.12);
}
.diagnostic-label {
  font-size: 13px;
  font-weight: 700;
}
.diagnostic-detail {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-muted);
}
.theme-dark .diagnostic-detail {
  color: rgba(234, 244, 255, 0.76);
}
.diagnostic-error .diagnostic-label {
  color: #9d3431;
}
.theme-dark .diagnostic-error .diagnostic-label {
  color: #ffd0cd;
}
.diagnostic-warning .diagnostic-label {
  color: #94611d;
}
.theme-dark .diagnostic-warning .diagnostic-label {
  color: #ffd89c;
}
.report-preview {
  margin: 0;
  padding: 20px;
  border-radius: 18px;
  border: 1px solid var(--border-light);
  background: #f7fbff;
  color: var(--text-light);
  white-space: pre-wrap;
  word-break: break-word;
  overflow: auto;
  line-height: 1.7;
  font-family: monospace;
}
.theme-dark .report-preview {
  border-color: var(--border-dark);
  background: rgba(6, 18, 30, 0.88);
  color: rgba(234, 244, 255, 0.88);
}
@media (max-width: 920px) {
  .hero-grid, .hero-grid-featured, .content-grid, .job-detail-main {
    grid-template-columns: 1fr;
  }
  .featured-header {
    grid-template-columns: 1fr;
  }
  .app-frame { padding: 20px 16px 40px; }
  .page-hero { padding: 24px; }
  .page-title { font-size: 34px; }
}
"""


def render_page(*, title: str, content: str, body_class: str = "theme-light", page_class: str = "") -> str:
    page_class_attr = f" {escape(page_class)}" if page_class else ""
    return f"""
    <html>
      <head>
        <meta charset='utf-8' />
        <meta name='viewport' content='width=device-width, initial-scale=1' />
        <title>{escape(title)}</title>
        <style>{_THEME_CSS}</style>
      </head>
      <body class='app-shell {escape(body_class)}'>
        <main class='app-frame{page_class_attr}'>
          <div class='page-stack'>
            {content}
          </div>
        </main>
      </body>
    </html>
    """


def render_page_header(*, eyebrow: str, title: str, subtitle: str, actions: str = "") -> str:
    return f"""
    <section class='page-header'>
      <div class='page-header-copy'>
        <div class='eyebrow'>{escape(eyebrow)}</div>
        <h1>{escape(title)}</h1>
        <p>{escape(subtitle)}</p>
      </div>
      <div class='page-actions'>{actions}</div>
    </section>
    """


def render_stat_card(label: str, value: str, meta: str = "") -> str:
    meta_html = f"<div class='stat-meta'>{escape(meta)}</div>" if meta else ""
    return f"""
    <article class='stat-card'>
      <div class='stat-label'>{escape(label)}</div>
      <div class='stat-value'>{escape(value)}</div>
      {meta_html}
    </article>
    """


def render_badge(label: str, tone: str = "neutral") -> str:
    return f"<span class='status-badge badge-{escape(tone)}'>{escape(label)}</span>"


def render_panel(title: str, content: str, extra_class: str = "", actions: str = "") -> str:
    extra = f" {escape(extra_class)}" if extra_class else ""
    actions_html = f"<div>{actions}</div>" if actions else ""
    return f"""
    <section class='panel{extra}'>
      <div class='panel-header'>
        <h2 class='panel-title'>{escape(title)}</h2>
        {actions_html}
      </div>
      <div class='panel-body'>
        {content}
      </div>
    </section>
    """





