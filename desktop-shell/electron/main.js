const {
  app,
  BrowserWindow,
  Menu,
  Notification,
  Tray,
  dialog,
  nativeImage,
} = require("electron");
const { execFile, spawn } = require("child_process");
const path = require("path");
const { buildNotificationPlan, deriveShellStatus } = require("./shell-state");

const APP_TITLE = "热点信息采集系统";
const DEFAULT_ENTRY_URL = "http://127.0.0.1:38080/";
const DEFAULT_MANIFEST_URL = "http://127.0.0.1:38080/system/desktop-manifest";
const PROBE_ARGS = ["--probe", "--print-json"];
const START_ARGS = ["--no-browser"];
const REFRESH_INTERVAL_MS = 10000;
const POLL_INTERVAL_MS = 500;
const STARTUP_TIMEOUT_MS = 20000;
const TRAY_ICON_PATH = path.join(__dirname, "assets", "tray.png");

let mainWindow = null;
let tray = null;
let refreshTimer = null;
let refreshInFlight = null;
let isQuitting = false;
let lastKnownManifest = null;
let currentShellState = {
  running: false,
  authStatus: "missing",
  healthStatus: "ok",
  entryUrl: DEFAULT_ENTRY_URL,
  ...deriveShellStatus({ running: false, authStatus: "missing", healthStatus: "ok" }),
};

function resolveRuntimeRoot() {
  if (process.env.HOT_DESKTOP_RUNTIME_ROOT) {
    return path.resolve(process.env.HOT_DESKTOP_RUNTIME_ROOT);
  }
  return path.resolve(__dirname, "..", "..");
}

function resolveManifestUrl() {
  return process.env.HOT_DESKTOP_MANIFEST_URL || DEFAULT_MANIFEST_URL;
}

function buildLoadingHtml(message) {
  return `data:text/html;charset=utf-8,${encodeURIComponent(`<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>${APP_TITLE}</title>
  <style>
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: linear-gradient(135deg, #f6f1e8 0%, #e7ecef 100%);
      color: #16212c;
      font-family: "Microsoft YaHei UI", "PingFang SC", sans-serif;
    }
    main {
      width: min(560px, calc(100vw - 48px));
      padding: 28px 32px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.86);
      box-shadow: 0 18px 50px rgba(15, 39, 59, 0.12);
    }
    h1 {
      margin: 0 0 12px;
      font-size: 22px;
    }
    p {
      margin: 0;
      line-height: 1.7;
      white-space: pre-wrap;
    }
  </style>
</head>
<body>
  <main>
    <h1>${APP_TITLE}</h1>
    <p>${message}</p>
  </main>
</body>
</html>`)}`;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function runExecutable(filePath, args) {
  return new Promise((resolve, reject) => {
    execFile(filePath, args, { windowsHide: true }, (error, stdout, stderr) => {
      if (error) {
        reject(new Error(stderr || error.message));
        return;
      }
      resolve(stdout);
    });
  });
}

async function probeService(launcherPath) {
  try {
    const stdout = await runExecutable(launcherPath, PROBE_ARGS);
    return JSON.parse(stdout);
  } catch (error) {
    return {
      running: false,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

async function startService(launcherPath) {
  return new Promise((resolve, reject) => {
    const child = spawn(launcherPath, START_ARGS, {
      detached: true,
      stdio: "ignore",
      windowsHide: true,
    });
    child.once("error", reject);
    child.unref();
    resolve();
  });
}

async function fetchManifest(manifestUrl) {
  const response = await fetch(manifestUrl, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`manifest 请求失败: ${response.status}`);
  }
  const payload = await response.json();
  if (!payload?.service?.entry_url) {
    throw new Error("manifest 缺少 service.entry_url");
  }
  return payload;
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`请求失败: ${url} => ${response.status}`);
  }
  return response.json();
}

async function waitForManifest(manifestUrl) {
  const deadline = Date.now() + STARTUP_TIMEOUT_MS;
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      return await fetchManifest(manifestUrl);
    } catch (error) {
      lastError = error;
      await delay(POLL_INTERVAL_MS);
    }
  }
  throw lastError || new Error("等待 manifest 超时");
}

function buildRouteUrl(routePath) {
  const baseUrl = currentShellState.entryUrl || lastKnownManifest?.service?.entry_url || DEFAULT_ENTRY_URL;
  return new URL(routePath, baseUrl).toString();
}

function buildAuthStateUrl(entryUrl) {
  return new URL("/system/auth-state", entryUrl || DEFAULT_ENTRY_URL).toString();
}

function loadTrayIcon() {
  const icon = nativeImage.createFromPath(TRAY_ICON_PATH);
  if (icon.isEmpty()) {
    return nativeImage.createEmpty();
  }
  return icon.resize({ width: 16, height: 16 });
}

function showMainWindow(targetUrl = null) {
  if (!mainWindow || mainWindow.isDestroyed()) {
    mainWindow = createMainWindow();
    return;
  }
  if (targetUrl) {
    mainWindow.loadURL(targetUrl);
  }
  mainWindow.show();
  mainWindow.focus();
}

function updateTrayState(state) {
  if (!tray) {
    return;
  }

  tray.setToolTip(state.tooltip || `${APP_TITLE}: 未运行`);
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: `状态：${state.label || "未运行"}`, enabled: false },
      { type: "separator" },
      {
        label: "打开主界面",
        enabled: Boolean(state.running),
        click: () => showMainWindow(state.entryUrl || DEFAULT_ENTRY_URL),
      },
      {
        label: "打开账号态页",
        enabled: Boolean(state.running),
        click: () => showMainWindow(buildRouteUrl("/auth-state")),
      },
      { type: "separator" },
      {
        label: "启动服务",
        enabled: !state.running,
        click: async () => {
          await startServiceFromShell();
          await refreshShellState({ allowNotify: true });
        },
      },
      {
        label: "停止服务",
        enabled: Boolean(state.running),
        click: async () => {
          await stopServiceFromShell();
          await delay(800);
          await refreshShellState({ allowNotify: true });
        },
      },
      {
        label: "查看状态",
        click: async () => {
          await refreshShellState({ allowNotify: false });
        },
      },
      { type: "separator" },
      {
        label: "退出",
        click: () => {
          isQuitting = true;
          app.quit();
        },
      },
    ]),
  );
}

function showSystemNotification(plan) {
  if (!plan || !Notification.isSupported()) {
    return;
  }
  new Notification({
    title: plan.title,
    body: plan.body,
    silent: false,
  }).show();
}

function ensureTray() {
  if (tray) {
    return tray;
  }
  tray = new Tray(loadTrayIcon());
  tray.on("double-click", () => showMainWindow(currentShellState.entryUrl || DEFAULT_ENTRY_URL));
  tray.on("click", () => showMainWindow(currentShellState.entryUrl || DEFAULT_ENTRY_URL));
  updateTrayState(currentShellState);
  return tray;
}

async function collectShellState() {
  const runtimeRoot = resolveRuntimeRoot();
  const launcherPath = path.join(runtimeRoot, "HotCollectorLauncher.exe");
  const probe = await probeService(launcherPath);

  if (!probe.running) {
    return {
      running: false,
      authStatus: "missing",
      healthStatus: "ok",
      entryUrl: lastKnownManifest?.service?.entry_url || DEFAULT_ENTRY_URL,
      ...deriveShellStatus({ running: false, authStatus: "missing", healthStatus: "ok" }),
    };
  }

  const manifest = await fetchManifest(resolveManifestUrl());
  lastKnownManifest = manifest;
  const entryUrl = manifest.service.entry_url || DEFAULT_ENTRY_URL;
  const authState = await fetchJson(buildAuthStateUrl(entryUrl));
  const healthState = await fetchJson(manifest.service.health_url);

  return {
    running: true,
    authStatus: authState.status || "missing",
    healthStatus: healthState.status || "error",
    entryUrl,
    manifest,
    ...deriveShellStatus({
      running: true,
      authStatus: authState.status || "missing",
      healthStatus: healthState.status || "error",
    }),
  };
}

async function refreshShellState({ allowNotify = true } = {}) {
  if (refreshInFlight) {
    return refreshInFlight;
  }

  refreshInFlight = (async () => {
    const previousState = currentShellState;
    try {
      const nextState = await collectShellState();
      currentShellState = nextState;
      updateTrayState(nextState);
      if (allowNotify) {
        showSystemNotification(buildNotificationPlan(previousState, nextState));
      }
      return nextState;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

function buildControlCommand(control) {
  if (!control || !control.preferred_path) {
    throw new Error("control manifest 缺少 preferred_path");
  }

  const args = Array.isArray(control.preferred_args) ? control.preferred_args : [];
  switch (control.launch_mode) {
    case "batch-file":
      return { filePath: "cmd.exe", args: ["/c", control.preferred_path, ...args] };
    case "powershell-file":
      return {
        filePath: "powershell.exe",
        args: ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", control.preferred_path, ...args],
      };
    case "python-script":
      return { filePath: "python", args: [control.preferred_path, ...args] };
    case "native-executable":
    default:
      return { filePath: control.preferred_path, args };
  }
}

async function executeControl(control) {
  const command = buildControlCommand(control);
  return runExecutable(command.filePath, command.args);
}

async function startServiceFromShell() {
  const runtimeRoot = resolveRuntimeRoot();
  const launcherPath = path.join(runtimeRoot, "HotCollectorLauncher.exe");
  await startService(launcherPath);
}

async function stopServiceFromShell() {
  const manifest = lastKnownManifest || await fetchManifest(resolveManifestUrl());
  await executeControl(manifest.control.stop);
}

async function bootstrapWindow(window) {
  const runtimeRoot = resolveRuntimeRoot();
  const launcherPath = path.join(runtimeRoot, "HotCollectorLauncher.exe");
  const manifestUrl = resolveManifestUrl();

  window.loadURL(buildLoadingHtml("正在检查本地服务状态，并准备桌面壳主窗口。"));

  try {
    const probe = await probeService(launcherPath);
    if (!probe.running) {
      window.loadURL(buildLoadingHtml("本地服务未运行，正在以桌面模式启动内核。"));
      await startService(launcherPath);
    }

    window.loadURL(buildLoadingHtml("服务已启动，正在同步托盘状态并加载主界面。"));
    await waitForManifest(manifestUrl);
    const nextState = await refreshShellState({ allowNotify: false });
    await window.loadURL(nextState.entryUrl || DEFAULT_ENTRY_URL);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    window.loadURL(buildLoadingHtml(`桌面壳启动失败：${message}`));
    dialog.showErrorBox(APP_TITLE, `桌面壳启动失败。\n\n${message}`);
  }
}

function createMainWindow() {
  const window = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1100,
    minHeight: 760,
    autoHideMenuBar: true,
    show: false,
    backgroundColor: "#f6f1e8",
    title: APP_TITLE,
    webPreferences: {
      contextIsolation: true,
      sandbox: false,
    },
  });

  window.once("ready-to-show", () => {
    window.show();
  });

  window.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      window.hide();
    }
  });

  window.on("closed", () => {
    if (mainWindow === window) {
      mainWindow = null;
    }
  });

  bootstrapWindow(window);
  return window;
}

app.whenReady().then(() => {
  ensureTray();
  mainWindow = createMainWindow();
  refreshTimer = setInterval(() => {
    refreshShellState({ allowNotify: true }).catch(() => {});
  }, REFRESH_INTERVAL_MS);
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      mainWindow = createMainWindow();
    } else {
      showMainWindow(currentShellState.entryUrl || DEFAULT_ENTRY_URL);
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    // 保持托盘常驻；真实退出由托盘菜单控制。
  }
});

app.on("before-quit", () => {
  isQuitting = true;
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
});
