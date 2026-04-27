const APP_TITLE = "热点信息采集系统";

function deriveShellStatus({ running, authStatus, healthStatus }) {
  if (!running) {
    return {
      key: "stopped",
      label: "未运行",
      tooltip: `${APP_TITLE}: 未运行`,
    };
  }

  if (healthStatus === "error") {
    return {
      key: "health-error",
      label: "健康异常",
      tooltip: `${APP_TITLE}: 健康异常`,
    };
  }

  if (authStatus === "error") {
    return {
      key: "auth-error",
      label: "账号态异常",
      tooltip: `${APP_TITLE}: 账号态异常`,
    };
  }

  if (authStatus === "warning") {
    return {
      key: "auth-warning",
      label: "账号态告警",
      tooltip: `${APP_TITLE}: 账号态告警`,
    };
  }

  if (authStatus === "missing") {
    return {
      key: "auth-missing",
      label: "账号态未配置",
      tooltip: `${APP_TITLE}: 账号态未配置`,
    };
  }

  return {
    key: "running",
    label: "运行中",
    tooltip: `${APP_TITLE}: 运行中`,
  };
}

function buildNotificationPlan(previousState, nextState) {
  if (!previousState || !nextState) {
    return null;
  }

  if (!previousState.running && nextState.running) {
    if (nextState.key === "health-error") {
      return {
        key: "health-error",
        title: `${APP_TITLE} 健康异常`,
        body: "服务已启动，但健康检查未通过，请打开主界面排查。",
      };
    }
    if (nextState.key === "auth-warning" || nextState.key === "auth-error") {
      return {
        key: nextState.key,
        title: `${APP_TITLE} 账号态异常`,
        body: "本地服务已启动，但账号态需要处理，请前往账号态页或调度页检查。",
      };
    }
    return {
      key: "service-started",
      title: `${APP_TITLE} 已启动`,
      body: "本地服务已启动，可以开始查看主界面或账号态页面。",
    };
  }

  if (previousState.key === nextState.key) {
    return null;
  }

  if (nextState.key === "health-error") {
    return {
      key: "health-error",
      title: `${APP_TITLE} 健康异常`,
      body: "系统健康检查返回异常，请及时查看主界面或日志。",
    };
  }

  if (nextState.key === "auth-warning" || nextState.key === "auth-error") {
    return {
      key: nextState.key,
      title: `${APP_TITLE} 账号态告警`,
      body: "B站登录态可能缺失或失效，请前往账号态页或调度页重新同步。",
    };
  }

  if (
    (previousState.key === "health-error"
      || previousState.key === "auth-warning"
      || previousState.key === "auth-error")
    && nextState.key === "running"
  ) {
    return {
      key: "recovered",
      title: `${APP_TITLE} 状态已恢复`,
      body: "系统健康或账号态已恢复到正常状态。",
    };
  }

  return null;
}

module.exports = {
  deriveShellStatus,
  buildNotificationPlan,
};
