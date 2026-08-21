# 测试计划与策略

## 1. 测试目标

本项目针对新能源汽车销售系统的 REST API 开展接口级黑盒自动化测试，目标是：

- 验证公开接口、鉴权接口和客户业务接口的响应契约；
- 验证匿名访问拦截、客户越权访问拦截等基础权限边界；
- 覆盖试驾、订单、售后和 AI 导购的关键流程，并为订单提供跨角色交付闭环；
- 将会写入测试数据的场景与日常安全回归隔离；
- 在执行前确认被测环境可用，避免后端离线时出现“全部跳过但任务成功”的假绿；
- 对测试报告中的凭据和常见个人/业务标识进行脱敏。
- 通过显式开启的只读连接，辅助验证 API 与关键数据库记录状态一致。

## 2. 测试范围

| 模块 | 自动化范围 | 用例文件 |
| --- | --- | --- |
| 公开查询 | 品牌、车型、SKU、文章及可售库存结构 | `test_catalog.py` |
| 登录鉴权 | 无效凭据、客户登录及令牌返回 | `test_authentication.py` |
| 权限控制 | 匿名访问受保护接口、客户访问后台接口 | `test_permissions.py` |
| 客户查询 | 订单、试驾、售后列表及个人资料 | `test_customer_queries.py` |
| 试驾预约 | 创建、重复预约冲突、非法评分/状态 | `test_test_drive.py` |
| 订单交付 | 客户创建、定金、管理员配车、尾款、交付及副作用回查 | `test_orders.py` |
| 售后工单 | 客户创建工单并在列表中回查 | `test_after_sales.py` |
| AI 导购 | 鉴权、参数边界、回复与历史 | `test_ai_shopping_guide.py` |
| 数据库辅助校验 | 客户资料 API 与数据库非敏感状态字段一致性 | `test_database_consistency.py` |

## 3. 不在本阶段范围内

- Web 管理端和移动端 UI 自动化；
- 后端单元测试、代码覆盖率和其他白盒测试；
- 业务写入后的多表数据一致性与数据库性能分析；
- 压力、容量、稳定性和安全渗透测试；
- 真实支付渠道、短信、微信等第三方生产服务；
- 售后技师分配、耗材登记、完工和客户评价闭环；
- AI 推荐内容的语义质量评价。

## 4. 环境与测试数据

### 必需配置

| 配置 | 用途 |
| --- | --- |
| `EV_API_BASE_URL` | 专用测试环境 API 地址 |
| `EV_CUSTOMER_USERNAME` | 可轮换的客户测试账号 |
| `EV_CUSTOMER_PASSWORD` | 客户测试账号密码 |

可在未提交的 `config/env.yaml` 中配置同名字段，也可使用环境变量覆盖。

### 可选配置

| 配置 | 用途 |
| --- | --- |
| `EV_ADMIN_USERNAME` / `EV_ADMIN_PASSWORD` | 订单交付闭环必需；账号应具备订单、财务、库存和交付查询/操作权限 |
| `EV_FEISHU_WEBHOOK` | 飞书结果通知 |
| `EV_ALLURE_REPORT_URL` | 报告访问地址；输出前会移除敏感查询参数 |
| `EV_TEST_RUN_ID` | 测试运行标识；CI 可显式传入，未设置时自动生成 |
| `EV_ALLOW_INSECURE_HTTP=true` | 仅在可信隔离网络中允许远程 HTTP；公网/跨网络环境应使用 HTTPS |
| `EV_DB_HOST` / `EV_DB_PORT` / `EV_DB_NAME` | 显式数据库校验使用的隔离库连接信息 |
| `EV_DB_USERNAME` / `EV_DB_PASSWORD` | 专用 SELECT-only 账号；禁止使用 root |
| `EV_DB_SSL_CA` | 非回环数据库必填；用于验证 MySQL 服务证书和主机名 |

测试数据必须属于可重置的专用测试环境。不得连接生产环境，也不得使用真实客户资料。

写数据场景还需要在本地 `config/env.yaml` 的 `business_data` 中准备以下合成测试数据：

| 字段 | 要求 |
| --- | --- |
| `model_id` | 试驾创建场景必需，必须是可预约车型 |
| `sku_id` | 订单交付场景必需；其车型必须至少存在一辆状态为在库的匹配车辆 |
| `completed_test_drive_id_rating_0` | 评分 0 场景必需；执行前通过客户列表 API 验证属于当前客户、状态为已完成且尚未评价 |
| `completed_test_drive_id_rating_6` | 评分 6 场景必需；必须是另一条预约，并通过相同 API 前置校验 |
| `vin` | 售后环境要求绑定车辆时填写合成测试 VIN，否则可留空 |
| `nonexistent_order_id` | 可选；应是测试环境中确定不存在的正整数 |

业务数据在加载时转换为类型明确的 `BusinessData`，非法 ID 会在执行接口前直接报错，两个评分边界 ID 相同也会被拒绝。对应字段可通过 `EV_MODEL_ID`、`EV_SKU_ID`、`EV_COMPLETED_TEST_DRIVE_ID_RATING_0`、`EV_COMPLETED_TEST_DRIVE_ID_RATING_6`、`EV_TEST_VIN`、`EV_NONEXISTENT_ORDER_ID`、`EV_AI_QUESTION` 和 `EV_AI_MIN_REPLY_LENGTH` 覆盖。

每次执行共用一个 `EV_TEST_RUN_ID`。框架将它写入 `X-Test-Run-Id` 请求头，并为支持自由文本的写入数据添加 `[AUTO:<run_id>]` 前缀，以便在服务日志、报告和测试环境中定位同一次运行产生的数据。

## 5. 分层执行策略

### 5.1 用例收集检查

验证测试模块可导入、参数化场景可收集、标记表达式有效。该检查不访问后端，也不代表接口回归通过。

```bash
python -m pytest --collect-only -q
```

### 5.2 默认安全回归

用于日常检查和定时任务，排除主动写入数据的场景。

```bash
python run_api_tests.py --no-feishu -m "not destructive and not database"
```

### 5.3 写数据回归

只允许在专用且可重置的测试环境中人工开启。

```bash
python run_api_tests.py --no-feishu --run-destructive -m destructive
```

### 5.4 韧性场景


### 5.5 只读数据库校验

数据库校验默认关闭，只能连接隔离测试库。连接后框架检查实际授权，账号具有 `SELECT/USAGE` 之外权限或转授权能力时立即失败；非回环连接还必须使用可信 CA 完成 TLS 证书与主机名校验。

```bash
python run_api_tests.py --no-feishu --run-database-checks -m database
```

## 6. 主要测试方法

- 等价类：有效/无效登录、合法/非法评分等；
- 边界值：空消息、评分下界和上界之外的输入；
- 状态转换：订单创建、支付和回查；
- 错误推测：重复提交、不存在资源、越权访问；
- 契约检查：业务码、数据类型、分页结构和关键字段；
- 数据一致性：比较 API 与数据库中同一记录的非敏感状态字段；

## 7. 准入标准

- 被测服务健康检查通过；
- 专用测试账号和基础业务数据可用；
- 写数据任务已确认运行在可重置环境；
- 数据库校验使用专用 SELECT-only 账号；
- 本地配置和报告目录均未纳入版本控制。

## 8. 准出标准

- 目标选择器实际执行了至少一个测试，不能以“零执行”作为成功；
- 本次选定范围内的高风险场景无未解释失败；
- 失败项保留脱敏后的 JUnit/Allure 原始结果和日志；
- 写数据场景产生的数据已记录，必要时由测试环境统一重置；
- 报告中的账号、令牌和个人/业务标识通过人工复核后方可公开。
