# 🛡️ 防止找回保护工具 (Recovery Protection Tool)

## 功能概述

防止找回保护工具是一个自动化的账号安全迁移系统，帮助号商快速将Telegram账号安全迁移并加固，降低被原持有人找回的风险。

## 核心功能

### 1. 自动化处理流程

完整的处理阶段：

1. **密码输入** - 用户先发送新密码（或输入 `auto` 自动生成）
2. **文件上传** - 上传 session 或 tdata 文件（ZIP压缩包）
3. **格式识别** - 自动识别文件格式并转换（TData → Session）
4. **账号连接** - 使用代理连接账号获取完整信息
5. **密码修改** - 使用用户提供的密码修改2FA（change_password阶段）
6. **设备清理** - 踢出所有其他设备（kick_devices阶段）
7. **验证码请求** - 请求登录验证码
8. **验证码获取** - 监听777000自动获取验证码
9. **新设备登录** - 使用验证码和新密码登录新设备
10. **验证失效** - 验证旧session是否已失效（verify_old_invalid阶段）
11. **结果打包** - 打包成功/失败的结果文件

### 2. 智能分类系统

处理结果自动分类到不同目录：

- **safe_sessions/** - 成功保护的账号
- **abnormal/** - 格式异常的账号
- **code_timeout/** - 验证码超时的账号
- **failed/** - 处理失败的账号
- **partial/** - 部分成功的账号

### 3. 详细报告生成

每次批处理生成三种报告：

- **TXT汇总报告** - 统计数据和概览
- **CSV详细报告** - 每个账号的详细信息
- **ZIP归档包** - 包含所有结果文件和报告

## 环境变量配置

在 `.env` 文件中添加以下配置：

```env
# 防止找回配置
RECOVERY_CONCURRENT=10                    # 并发处理数量
RECOVERY_CODE_TIMEOUT=300                 # 验证码超时时间（秒）
RECOVERY_PASSWORD_LENGTH=14               # 生成密码长度
RECOVERY_PASSWORD_SPECIALS=!@#$%^&*_-+=  # 密码特殊字符
RECOVERY_DEVICE_KILL_RETRIES=2            # 删除设备重试次数
RECOVERY_DEVICE_KILL_DELAY=1.0            # 删除设备延迟（秒）
RECOVERY_ENABLE_PROXY=true                # 是否启用代理
RECOVERY_PROXY_RETRIES=2                  # 代理重试次数
```

## 数据库结构

### recovery_logs 表

记录每个账号的每个阶段的处理日志：

```sql
CREATE TABLE recovery_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name TEXT,
    phone TEXT,
    stage TEXT,              -- load/connect_old/change_password/kick_devices/request_code/wait_code/sign_in_new/verify_old_invalid/package_result
    success INTEGER,
    error TEXT,
    detail TEXT,
    elapsed REAL,
    created_at TEXT
);
```

### recovery_summary 表

记录每次批处理的汇总信息：

```sql
CREATE TABLE recovery_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id TEXT,
    total INTEGER,
    success INTEGER,
    abnormal INTEGER,
    failed INTEGER,
    code_timeout INTEGER,
    partial INTEGER,
    created_at TEXT
);
```

## 使用方法

### 通过机器人界面

1. 启动机器人，点击主菜单的 **🛡️ 防止找回** 按钮
2. **发送新密码**（用于修改账号密码）
   - 直接输入您想设置的密码
   - 或发送 `auto` 使用自动生成的强密码
3. 上传包含session或TData文件的ZIP压缩包
4. 等待处理完成（可查看实时进度）
5. 下载生成的报告和结果文件

### 进度显示

处理过程中会显示实时进度：

```
🛡️ 防止找回进度

已处理: 15/50
成功: 12 | 失败: 2 | 超时: 0 | 异常: 1 | 部分: 0
平均耗时: 45.3s

⏳ 请稍候...
```

### 结果报告示例

**TXT汇总报告：**
```
防止找回批次报告 - 20240119_143022
==================================================

总数: 50
成功: 42
失败: 3
异常: 2
超时: 2
部分: 1
```

**CSV详细报告：**
```csv
账号,手机号,状态,失败原因,代理,密码(脱敏),总耗时
account1.session,+1234567890,success,,socks5 1.2.3.4:1080(ok 2.3s),abc***XYZ,47.5s
account2.session,+9876543210,timeout,等待验证码超时,Local(1.2s),,305.2s
```

## API 接口

### RecoveryProtectionManager 类

主要方法：

```python
# 批量运行防止找回（支持用户自定义密码）
async def run_batch(
    files: List[Tuple[str, str]], 
    progress_callback=None,
    user_password: str = ""  # 用户提供的新密码，为空则自动生成
) -> Dict

# 生成报告文件
def generate_reports(report_data: Dict) -> Tuple[str, str, str]

# 生成强密码
def generate_strong_password() -> str

# 脱敏显示密码
def mask_password(password: str) -> str

# 等待777000验证码
async def wait_for_code(
    old_client: TelegramClient, 
    phone: str, 
    timeout: int = 300
) -> Optional[str]

# 删除其他设备授权
async def remove_other_devices(
    client: TelegramClient
) -> Tuple[bool, str]

# 修改密码（新增）
async def _stage_change_password(
    client: TelegramClient,
    context: RecoveryAccountContext
) -> Tuple[bool, str]

# 踢出其他设备（新增）
async def _stage_kick_devices(
    client: TelegramClient,
    context: RecoveryAccountContext
) -> Tuple[bool, str]

# 验证旧会话失效（新增）
async def _stage_verify_old_invalid(
    old_session_path: str,
    context: RecoveryAccountContext
) -> Tuple[bool, str]
```

### RecoveryAccountContext 数据类

```python
@dataclass
class RecoveryAccountContext:
    original_path: str           # 原始文件路径
    old_session_path: str        # 旧session路径
    new_session_path: str        # 新session路径
    phone: str                   # 手机号
    proxy_used: str = ""         # 使用的代理
    new_password_masked: str = "" # 脱敏后的密码
    status: str = "pending"      # 状态: success/failed/abnormal/timeout/partial
    failure_reason: str = ""     # 失败原因
    
    # 新增字段
    user_provided_password: str = ""  # 用户提供的新密码
    old_device_info: Dict = {}        # 旧设备信息
    new_device_info: Dict = {}        # 新设备信息
    verification_code: str = ""       # 获取到的验证码
    code_wait_time: float = 0.0       # 等待验证码的时间
    old_session_valid: bool = True    # 旧会话是否仍有效
```

## 安全特性

### 1. 密码安全
- 使用 `secrets` 模块生成强密码
- 确保包含大小写字母、数字和特殊字符
- 脱敏显示（仅显示前3位和后3位）
- 完整密码不存储到数据库
- 支持用户自定义密码

### 2. 代理支持
- 自动代理重试机制
- 支持多种代理类型（HTTP/SOCKS4/SOCKS5）
- 失败自动回退到本地连接
- 详细的代理使用日志

### 3. 错误处理
- 每个阶段独立的错误捕获
- 详细的失败原因记录
- 自动分类异常情况
- 防止单个失败影响整体

## 目录结构

```
results/recovery/
├── safe_sessions/      # 成功保护的账号
├── abnormal/          # 格式异常的账号
├── code_timeout/      # 验证码超时的账号
├── failed/            # 处理失败的账号
├── partial/           # 部分成功的账号
└── reports/           # 批次报告
    ├── batch_YYYYMMDD_HHMMSS_summary.txt
    ├── batch_YYYYMMDD_HHMMSS_detail.csv
    └── batch_YYYYMMDD_HHMMSS_archives.zip
```

## 性能优化

- **并发处理**：使用 `asyncio.Semaphore` 控制并发数量
- **实时进度**：使用 `as_completed()` 实时更新进度
- **批量操作**：支持一次处理大量账号
- **资源管理**：自动清理临时文件和客户端连接

## 注意事项

1. **账号状态要求**
   - Session文件必须已授权且有效
   - 账号需要能够接收777000的验证码
   - 建议使用代理以避免频率限制

2. **处理时间**
   - 平均每个账号需要30-60秒
   - 取决于网络状况和验证码到达速度
   - 大批量处理建议分批进行

3. **错误处理**
   - 单个账号失败不影响其他账号
   - 失败账号会被分类并记录详细原因
   - 可以针对失败账号单独重试

4. **数据安全**
   - 所有密码都经过脱敏处理
   - 日志中不记录完整验证码
   - 代理失败原因限制80字符

## 故障排查

### 常见问题

**Q: 验证码超时怎么办？**
A: 检查账号是否能正常接收777000消息，可以尝试：
- 增加 `RECOVERY_CODE_TIMEOUT` 值
- 确认账号未被限制
- 手动测试777000消息接收

**Q: 代理连接失败？**
A: 检查：
- 代理配置是否正确
- 代理是否在线可用
- 尝试禁用代理使用本地连接
- 检查 `RECOVERY_ENABLE_PROXY` 配置

**Q: Session文件无效？**
A: 确认：
- Session文件是否完整
- 账号是否已登录
- API_ID 和 API_HASH 是否正确

## 更新日志

### v1.0.0 (2024-01-19)
- ✅ 初始版本发布
- ✅ 支持基础的账号连接验证
- ✅ 完整的报告生成系统
- ✅ 自动文件分类和归档
- ✅ 实时进度跟踪
- ⚠️ 验证码流程、2FA旋转和设备清理待完善

## 技术支持

如有问题或建议，请：
1. 查看日志输出了解详细错误信息
2. 检查数据库中的 recovery_logs 表
3. 查看生成的CSV报告了解失败原因
4. 联系开发者获取技术支持

## 许可证

与主项目保持一致
