热点采集系统（运营版 / 离线发布版）
==================================

一、同事电脑首次使用
1. 先解压整个发布包，不要直接在压缩包里运行
2. 双击“安装依赖.bat”
3. 双击“启动系统.bat”
4. 稍等几秒，系统会自动打开浏览器
5. 如未自动打开，请手工访问 http://127.0.0.1:38080/
6. 打开“定时调度”页面，按需要填写钉钉、B站登录态等配置

二、你需要配置什么
1. 如果要用钉钉通知，请到网页“定时调度”里填写：
   ENABLE_DINGTALK_NOTIFIER=true
   DINGTALK_WEBHOOK=你的机器人Webhook
   DINGTALK_SECRET=
   DINGTALK_KEYWORD=热点报告
2. 如果要抓 X，请填写：
   X_AUTH_TOKEN=你的 X auth_token
   X_CT0=你的 X ct0
3. 如果要抓 B站个人主页投稿视频（例如 https://space.bilibili.com/20411266），优先到网页“定时调度” -> “B站登录态”里点击“打开浏览器登录并同步”
4. 系统会打开本机浏览器，你在 B站页面完成登录后，系统会自动把最新登录态写入 data\app.env
5. 如果不方便打开浏览器，也可以在同一面板里直接粘贴完整 Cookie 字符串
6. B站这里直接粘贴整串 Cookie 值即可，不要手工加 `BILIBILI_COOKIE=` 前缀；如果误贴了，系统会自动识别
7. 缺少 `SESSDATA=` 的 Cookie 会被系统拒绝保存
8. 保存后立即生效，不需要重启系统

三、你平时只需要做的事
1. 在“采集源管理”里维护来源
2. 在首页点击“立即采集”
3. 在“历史报告”里下载结果
4. 在“定时调度”里设置每天自动执行时间

四、文件在哪里
1. 数据库：data\hot_topics.db
2. 报告：outputs\reports\
3. 共享报告：outputs\shared-reports\
4. 日志：logs\launcher.log

五、如何关闭
1. 双击“停止系统.bat”
2. 或直接关闭启动窗口

六、如何查看当前状态
1. 如需确认系统是否还在运行，可双击“查看状态.bat”
2. 打开的窗口会输出一段 JSON，其中 `running=true` 表示本机实例仍在运行
3. 如果看到 `stale_pid_file=true`，说明旧 PID 文件已过期，可联系技术同学确认后清理
七、遇到问题先看哪里
1. 先看 logs\launcher.log
2. 如果系统页面能打开，但抓取失败，请把任务详情页和日志一起发给技术同学
3. 如果 B站任务提示登录失效或风控，先到“定时调度”页面点“打开浏览器登录并同步”再试

八、依赖说明
1. 发布包已经内置 Python 运行环境与 Playwright 浏览器
2. “安装依赖.bat”主要用于补齐 Microsoft Visual C++ x64 运行库
3. 如果公司安全策略拦截运行库安装，请联系 IT 放行

九、快速打开或复制报告
1. 双击脚本或执行 scripts\open_latest_report.ps1，可直接打开报告目录
2. 执行 scripts\open_latest_report.ps1 -OpenDocx，可直接打开最新 DOCX
3. 执行 scripts\copy_latest_report.ps1 -Destination "目标目录"，可把最新报告复制到共享目录后再手动发群

十、如何覆盖升级但保留原配置
1. 先双击“停止系统.bat”关闭旧版本
2. 技术同学会提供“升级包”，里面只包含程序文件，不包含 data、logs、outputs、playwright-browsers
3. 将升级包里的全部文件直接覆盖到现有安装目录
4. 不要手工删除现有安装目录下的 data、logs、outputs、playwright-browsers
5. 覆盖完成后，双击“启动系统.bat”启动新版本
6. 原有 data\app.env、data\hot_topics.db、outputs\reports 会继续沿用，不需要重新配置

