const test = require("node:test");
const assert = require("node:assert/strict");

const {
  deriveShellStatus,
  buildNotificationPlan,
} = require("./shell-state");

test("deriveShellStatus returns stopped when service is not running", () => {
  const state = deriveShellStatus({
    running: false,
    authStatus: "missing",
    healthStatus: "ok",
  });

  assert.equal(state.key, "stopped");
  assert.equal(state.label, "未运行");
  assert.match(state.tooltip, /未运行/);
});

test("deriveShellStatus prioritizes health errors over auth warnings", () => {
  const state = deriveShellStatus({
    running: true,
    authStatus: "warning",
    healthStatus: "error",
  });

  assert.equal(state.key, "health-error");
  assert.equal(state.label, "健康异常");
});

test("buildNotificationPlan emits service-started on stopped to running", () => {
  const plan = buildNotificationPlan(
    { key: "stopped", running: false },
    { key: "running", running: true, authStatus: "ok", healthStatus: "ok" },
  );

  assert.equal(plan.key, "service-started");
});

test("buildNotificationPlan suppresses duplicate auth warnings", () => {
  const plan = buildNotificationPlan(
    { key: "auth-warning", running: true, authStatus: "warning", healthStatus: "ok" },
    { key: "auth-warning", running: true, authStatus: "warning", healthStatus: "ok" },
  );

  assert.equal(plan, null);
});

test("buildNotificationPlan emits recovered after health error returns to ok", () => {
  const plan = buildNotificationPlan(
    { key: "health-error", running: true, authStatus: "ok", healthStatus: "error" },
    { key: "running", running: true, authStatus: "ok", healthStatus: "ok" },
  );

  assert.equal(plan.key, "recovered");
});
