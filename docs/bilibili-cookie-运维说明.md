# B站 Cookie 获取与配置说明

## 适用场景

| 项目 | 说明 |
| --- | --- |
| 使用对象 | 运营、运维、实施同学 |
| 目标 | 获取可用于系统采集的 B站登录 Cookie |
| 配置入口 | 系统调度页 -> `B站登录态` |
| 推荐主流程 | 网页点击 `打开浏览器登录并同步` |

## 最终要粘贴的内容

在系统里填写时，只粘贴一整行 Cookie 值，不要加前缀，不要加引号，不要换行。

示例：

```text
SESSDATA=xxxx; bili_jct=xxxx; DedeUserID=xxxx; DedeUserID__ckMd5=xxxx; sid=xxxx; buvid3=xxxx; buvid4=xxxx
```

## 推荐方式：在系统网页里直接打开浏览器登录并同步

### 操作步骤

| 步骤 | 操作 |
| --- | --- |
| 1 | 打开系统调度页 `/scheduler` |
| 2 | 找到 `B站登录态` 面板 |
| 3 | 点击 `打开浏览器登录并同步` |
| 4 | 系统会打开本机真实浏览器，并复用运行目录下的持久化登录态 |
| 5 | 如果浏览器里还没登录，就在打开的 B站页面里完成登录/验证 |
| 6 | 系统检测到 `SESSDATA` 后，会自动保存浏览器状态，并把最新 Cookie 写入 `data/app.env` |
| 7 | 页面返回成功提示 `已从浏览器同步最新B站登录态` 后即可继续采集 |

### 说明

| 项目 | 说明 |
| --- | --- |
| 为什么优先推荐 | 比手工复制 Cookie 更稳，也能保留浏览器里的 storage state |
| 适用场景 | 手工复制容易漏字段，或主页采集命中 `-352/-412` 风控时 |
| 失败提示 | 如果页面提示登录超时，重新点一次按钮并在浏览器里完成登录 |

## 备用方式：浏览器控制台直接执行 JS

### 操作步骤

| 步骤 | 操作 |
| --- | --- |
| 1 | 用浏览器打开已登录的 B站页面，如 `https://www.bilibili.com/` |
| 2 | 按 `F12` 打开开发者工具 |
| 3 | 切到 `Console` 控制台 |
| 4 | 粘贴下面整段 JS 并回车执行 |
| 5 | 脚本会尽量读取当前可见 Cookie，并自动复制到剪贴板 |
| 6 | 把结果粘贴到系统调度页的 `B站登录态` 文本框并保存 |

### 控制台 JS

```js
(async () => {
  const pairs = [];
  const seen = new Set();

  const pushPair = (name, value) => {
    if (!name) return;
    const pair = `${name}=${value ?? ""}`.trim();
    if (!pair || seen.has(pair)) return;
    seen.add(pair);
    pairs.push(pair);
  };

  document.cookie
    .split(";")
    .map(v => v.trim())
    .filter(Boolean)
    .forEach(item => {
      const idx = item.indexOf("=");
      if (idx === -1) return;
      pushPair(item.slice(0, idx), item.slice(idx + 1));
    });

  if (window.cookieStore?.getAll) {
    try {
      const all = await window.cookieStore.getAll();
      all.forEach(({ name, value }) => pushPair(name, value));
    } catch (e) {}
  }

  const preferredOrder = [
    "SESSDATA",
    "bili_jct",
    "DedeUserID",
    "DedeUserID__ckMd5",
    "sid",
    "buvid3",
    "buvid4",
  ];

  const ordered = [];
  preferredOrder.forEach(name => {
    const hit = pairs.find(p => p.startsWith(name + "="));
    if (hit) ordered.push(hit);
  });
  pairs.forEach(p => {
    if (!ordered.includes(p)) ordered.push(p);
  });

  const result = ordered.join("; ");

  console.log("复制下面这整行到系统的 B站登录态：\n");
  console.log(result || "未读取到可见 Cookie");
  console.log("\n是否包含关键字段：", {
    SESSDATA: /(?:^|;\s*)SESSDATA=/.test(result),
    bili_jct: /(?:^|;\s*)bili_jct=/.test(result),
    DedeUserID: /(?:^|;\s*)DedeUserID=/.test(result),
  });

  if (result) {
    try {
      await navigator.clipboard.writeText(result);
      console.log("\n已复制到剪贴板");
    } catch (e) {
      if (typeof copy === "function") {
        copy(result);
        console.log("\n已通过 copy() 复制到剪贴板");
      } else {
        console.log("\n复制失败，请手动复制控制台输出");
      }
    }
  }
})();
```

## 怎么判断这份 Cookie 能不能用

| 判断项 | 结论 |
| --- | --- |
| 包含 `SESSDATA` | 必须有 |
| 包含 `bili_jct` | 建议有 |
| 包含 `DedeUserID` | 建议有 |
| 还能带上 `DedeUserID__ckMd5`、`sid`、`buvid3`、`buvid4` | 更稳 |
| 控制台输出里没有 `SESSDATA` | 这份 Cookie 基本不能用 |

## 重要限制

| 项目 | 说明 |
| --- | --- |
| `document.cookie` 限制 | 读不到 `HttpOnly` Cookie |
| 因此 JS 方案 | 只能作为快捷方式，不保证 100% 完整 |
| 如果系统仍报 `requires login` | 大概率是 Cookie 没拿全、已失效，或保存到了错误的运行目录 |

## 兜底方式：从 DevTools 的 Cookies 面板手工复制

如果控制台 JS 执行后缺少关键字段，改用下面方式。

### 操作步骤

| 步骤 | 操作 |
| --- | --- |
| 1 | 打开 B站页面并保持登录 |
| 2 | 按 `F12` |
| 3 | 进入 `Application` |
| 4 | 左侧展开 `Storage` -> `Cookies` |
| 5 | 点开 `https://www.bilibili.com` |
| 6 | 在右侧找到 `SESSDATA`、`bili_jct`、`DedeUserID` |
| 7 | 如果还有 `DedeUserID__ckMd5`、`sid`、`buvid3`、`buvid4`，也一并复制 |
| 8 | 按 `name=value; name=value` 的格式拼成一整行 |
| 9 | 粘贴到系统调度页 `B站登录态` 后保存 |

## 系统内填写要求

| 要求 | 说明 |
| --- | --- |
| 不要写成 `BILIBILI_COOKIE=...` | 调度页里只填值 |
| 如果误贴成 `BILIBILI_COOKIE=...` | 系统会自动识别并提取后面的 Cookie 值 |
| 不要换行 | 必须是一整行 |
| 不要加双引号或单引号 | 原样粘贴即可 |
| 必须包含 `SESSDATA=` | 缺少时系统会拒绝保存 |
| 保存后刷新页面检查 | 文本框中还能看到已保存内容，说明写入成功 |

## 排障建议

| 现象 | 优先排查 |
| --- | --- |
| 调度页提示 `Cookie 缺少 SESSDATA，系统未保存` | 说明粘贴进去的不是完整登录 Cookie，回到 B站重新复制 |
| `bilibili search page requires login` | Cookie 未读取到、未保存成功、缺关键字段、Cookie 已过期 |
| `请刷新 BILIBILI_COOKIE` | 先换最新 Cookie 再试 |
| `bilibili profile api hit risk control (风控): code=-352` | 新版本会优先回退到页面解析；如果仍失败，优先使用“打开浏览器登录并同步”刷新登录态 |
| `风控` | 更像出口 IP / 访问频率问题，不一定是 Cookie 本身问题；先减少频繁重试，再用浏览器同步登录态 |
| 明明改了 Cookie 但程序不生效 | 确认改的是实际运行版本对应的 `data/app.env` |

## 运行目录提醒

| 运行方式 | 配置文件位置 |
| --- | --- |
| 源码运行 | `data/app.env` |
| 发布版 EXE 运行 | `release/HotCollector/data/app.env` |

> 说明：正常使用时，优先在系统 `/scheduler` 页点击 `打开浏览器登录并同步`。只有浏览器同步不方便时，才退回到手工粘贴整串 Cookie 的方式。系统保存后会自动写入对应运行目录下的 `app.env`。 
