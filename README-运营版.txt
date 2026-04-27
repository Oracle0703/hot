热点采集系统（运营版 / 离线发布版）
==================================

一、同事电脑首次使用
1. 先解压整个发布包，不要直接在压缩包里运行
2. 双击“安装依赖.bat”
3. 双击“启动系统.bat”
4. 稍等几秒，系统会自动打开浏览器
5. 如未自动打开，请手工访问 http://127.0.0.1:38080/
6. 打开“定时调度”页面，按需要填写钉钉、B站登录态等配置
7. 如需桌面壳窗口，也可双击“打开桌面版.bat”，关闭窗口后程序会最小化到托盘

二、你需要配置什么
1. 如果要用钉钉通知，请到网页“定时调度”里填写：
   ENABLE_DINGTALK_NOTIFIER=true
   DINGTALK_WEBHOOK=你的机器人Webhook
   DINGTALK_SECRET=
   DINGTALK_KEYWORD=热点报告
   WEEKLY_GRADE_PUSH_THRESHOLD=B+
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
3. 在“最近一周热点”页面里查看近 7 天内容，按需要给条目打人工评分
4. 如果要把人工筛过的条目发到群里，在“最近一周热点”页面点“批量推送达标项”
5. 在“历史报告”里下载结果
6. 在“定时调度”里设置每天自动执行时间

四、周榜页怎么用
1. 页面入口是“最近一周热点”或直接访问 http://127.0.0.1:38080/weekly
2. 页面只展示最近 7 天首次抓到的内容
3. “推荐评分”是系统参考分，不会自动发群
4. 真正决定能不能推送的是“人工评分”
5. 只有人工评分达到 WEEKLY_GRADE_PUSH_THRESHOLD 且之前没推送过的条目，才会进入“批量推送达标项”
6. 如果页面提示“当前没有达到阈值且未推送的内容”，说明这次没有可发条目
7. 已推送条目会显示推送时间，不会重复进入下一次批量推送

五、文件在哪里
1. 数据库：data\hot_topics.db
2. 报告：outputs\reports\
3. 共享报告：outputs\shared-reports\
4. 日志：logs\launcher.log
5. 周榜封面缓存：outputs\weekly-covers\

六、如何关闭
1. 双击“停止系统.bat”
2. 如果使用桌面壳，也可在托盘菜单里退出
3. 仅关闭桌面壳窗口时，程序默认仍在托盘中运行

七、如何查看当前状态
1. 如需确认系统是否还在运行，可双击“查看状态.bat”
2. 打开的窗口会输出一段 JSON，其中 `running=true` 表示本机实例仍在运行
3. 如果看到 `stale_pid_file=true`，说明旧 PID 文件已过期，可联系技术同学确认后清理

八、遇到问题先看哪里
1. 先看 logs\launcher.log
2. 如果系统页面能打开，但抓取失败，请把任务详情页和日志一起发给技术同学
3. 如果 B站任务提示登录失效或风控，先到“定时调度”页面点“打开浏览器登录并同步”再试
4. 如果周榜页没有内容，先确认最近 7 天内是否真的跑过采集任务
5. 如果周榜页不能推送，先确认 ENABLE_DINGTALK_NOTIFIER、DINGTALK_WEBHOOK、WEEKLY_GRADE_PUSH_THRESHOLD 是否已配置

九、依赖说明
1. 发布包已经内置 Python 运行环境与 Playwright 浏览器
2. “安装依赖.bat”主要用于补齐 Microsoft Visual C++ x64 运行库
3. 如果公司安全策略拦截运行库安装，请联系 IT 放行

十、快速打开或复制报告
1. 双击脚本或执行 scripts\open_latest_report.ps1，可直接打开报告目录
2. 执行 scripts\open_latest_report.ps1 -OpenDocx，可直接打开最新 DOCX
3. 执行 scripts\copy_latest_report.ps1 -Destination "目标目录"，可把最新报告复制到共享目录后再手动发群

十一、如何覆盖升级但保留原配置
1. 先双击“停止系统.bat”关闭旧版本
2. 技术同学会提供“升级包”，里面只包含程序文件，不包含 data、logs、outputs、playwright-browsers
3. 将升级包里的全部文件直接覆盖到现有安装目录
4. 不要手工删除现有安装目录下的 data、logs、outputs、playwright-browsers
5. 覆盖完成后，双击“启动系统.bat”启动新版本
6. 原有 data\app.env、data\hot_topics.db、outputs\reports、outputs\weekly-covers 会继续沿用，不需要重新配置

