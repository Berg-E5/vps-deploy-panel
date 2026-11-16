# 参与开发

## 项目接入规则

一个新项目要进项目中心，必须先有官方部署文档、明确的许可证和系统兼容矩阵。

`skills/<project>/SKILL.md` 只提供工作流建议和前置条件说明，**不产生任何执行权限**。
真正会跑到远程服务器上的步骤必须写在 `app/catalog.py` 里，经过人工审核，并明确写出：

- 执行前的环境检查（系统版本、端口占用、是否已有安装）
- 每一条命令和它的超时
- 风险等级
- 验收条件 —— 怎么算装成功（服务在跑 + 带 Host 头真实请求自己的 vhost）

## 新安装器必须包含

- 模拟执行测试
- 针对脚本注入的阻断测试
- 针对不兼容环境的阻断测试
- 真实临时 VPS 上的验收（要有快照可回滚）
- 可审计的版本号与校验和
- 失败后的手工恢复步骤

## 不接受的改动

以下行为请不要通过 PR 引入：

- 关闭 SSH 主机密钥校验
- 默认把 Web 管理面暴露到公网
- 默认自动开启未经配置的代理服务
- 下载后不校验就直接执行远端 shell
- 让 AI 自主获取 VPS 的 root shell
- 在日志里打印认证密钥或密码

## 本地开发

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q          # 全量测试
node tests/ui_smoke.cjs            # 前端 smoke
python docs/site/build.py          # 重建文档站
```

Windows 上的 `pytest` 可能因为继承了宿主 site-packages 而报 `pydantic_core` 的 DLL 错误，
在 Linux 上跑更稳。

## 安全问题

不要在公开 issue 里贴真实的 VPS IP、SSH 密钥或任何认证信息。
请先建立私密报告渠道，修复细节在补丁发布后再公开。
