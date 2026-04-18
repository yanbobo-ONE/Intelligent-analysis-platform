---
name: NL2SQL语义规则与测试清单
overview: 固化 NL2SQL 场景下的数量、排序、极值、位置、年度范围与规则级 SQL 重写方案，并提供可执行测试清单，作为后端解析、LLM 路由、prompt 约束和 SQL 后处理的统一基线。
todos:
  - id: semantic-rule-1
    content: "固化数量规则：前N条、返回N条、top N、中文数字数量解析"
    status: completed
  - id: semantic-rule-2
    content: "固化单条位置规则：第一个、最后一个、倒数第一个、末尾一个"
    status: completed
  - id: semantic-rule-3
    content: "固化极值规则：最大、最小、最高、最低，统一为单条极值记录"
    status: completed
  - id: semantic-rule-4
    content: "固化排序规则：从高到低 / 从低到高 / 升序 / 降序 与 SQL ORDER BY 映射"
    status: completed
  - id: semantic-rule-5
    content: "固化末尾语义：末尾 / 末尾的数据 解释为最小的那条数据"
    status: completed
  - id: semantic-rule-6
    content: "补齐真实测试清单：前2条、前3条、最后一条、倒数第一个、最大/最小、末尾"
    status: completed
  - id: semantic-rule-7
    content: "将语义规则接入后端 intent 解析、prompt 构造与 SQL 后处理"
    status: completed
  - id: semantic-rule-8
    content: "引入规则优先 + LLM 二分类混合路由，模糊句由 MiniMax-M2.7 分类"
    status: completed
  - id: semantic-rule-9
    content: "补充年度/年终/年末范围提示与 region/amount 维度指标提示"
    status: completed
  - id: semantic-rule-10
    content: "对年度销售额排名类问题增加规则级 SQL 重写模板，默认按 region 年度汇总排名"
    status: completed
---

# NL2SQL 语义规则与测试清单

## 目标

将 NL2SQL 场景中的自然语言意图固化为一套稳定、可执行、可测试的规则，减少模型自由发挥带来的歧义，确保 SQL 生成、结果条数、排序方向、极值记录、年度范围解释与前端展示完全一致。

## 规则总览

### 1. 数量规则
当用户明确表达“返回多少条”时，统一映射为 `LIMIT N`。

#### 直接数量
- `前N条`
- `前N个`
- `前N名`
- `返回N条`
- `取N条`
- `给我N条`
- `top N`

#### 中文数字
- `前两条`
- `前三条`
- `前十条`
- `返回前两名`
- `返回前一条`

#### 单条同义词
统一映射为 `LIMIT 1`：
- `第一个`
- `第一条`
- `最后一个`
- `最后一条`
- `倒数第一个`
- `倒数第一条`
- `末尾一个`
- `末尾一条`

#### 后N条 / 后N名
统一映射为尾部数量语义：
- `后20条`
- `后20名`
- `倒数后20条`
- `倒数后20名`

默认解释为：
- `LIMIT N`
- `ORDER BY ... ASC`

### 2. 排序规则
#### 降序（从高到低）
映射为 `ORDER BY ... DESC`：
- `从高到低`
- `最高`
- `最大`
- `排名靠前`
- `top`

#### 升序（从低到高）
映射为 `ORDER BY ... ASC`：
- `从低到高`
- `最小`
- `最低`
- `末尾`
- `后N条`
- `后N名`
- `最后N名`

### 3. 极值规则
当用户表达“最大 / 最小 / 最高 / 最低”时，按单条极值记录处理：
- `最大的那条` → `ORDER BY 指标 DESC LIMIT 1`
- `最小的那条` → `ORDER BY 指标 ASC LIMIT 1`
- `最高的一条` → `ORDER BY 指标 DESC LIMIT 1`
- `最低的一条` → `ORDER BY 指标 ASC LIMIT 1`

### 4. 末尾语义
按产品定义：
- `末尾`、`末尾的数据` 解释为 **最小的那条数据**
- 优先使用 `ORDER BY 指标 ASC LIMIT 1`

### 5. 年度范围语义
当问题中出现：
- `年度`
- `年终`
- `年末`

则默认增加：
- `time_scope = year`

当同时出现：
- `销售额 / 金额`
- `地区 / 区域 / 排名`

则增加：
- `metric_hint = amount`
- `dimension_hint = region`

### 6. 混合路由规则
#### 规则优先
先使用规则判断：
- 明显 NL2SQL
- 明显 CHAT
- 不明确时返回 `UNKNOWN`

#### LLM 二分类
若规则判断为 `UNKNOWN`，则调用同供应商模型：
- `MiniMax-M2.7`

分类输出仅允许：
- `NL2SQL`
- `CHAT`

### 7. 规则级 SQL 重写模板
对于以下高歧义但高频业务场景，不再依赖模型自由生成，而是直接走 SQL 模板：

#### 命中条件
同时满足：
- 包含 `年度 / 年终 / 年末`
- 包含 `销售额 / 金额`
- 包含 `前 / 后 / 最后 / 排名 / 最高 / 最低`
- 未明确要求：
  - `按年份`
  - `每年`
  - `各年份`
  - `按年分组`
  - `年份统计`
- 且维度提示已归一为 `region`

#### 模板含义
- 时间范围：当前年度
- 维度：`region`
- 指标：`SUM(amount)`
- 排序：由 `ASC / DESC` 决定
- 条数：由 `LIMIT N` 决定

#### 模板 SQL
前 N 名 / 销售额最高侧：
```sql
SELECT region, SUM(amount) AS total_amount
FROM sales_demo
WHERE strftime('%Y', created_at) = strftime('%Y', 'now')
GROUP BY region
ORDER BY total_amount DESC
LIMIT N;
```

后 N 名 / 最末侧：
```sql
SELECT region, SUM(amount) AS total_amount
FROM sales_demo
WHERE strftime('%Y', created_at) = strftime('%Y', 'now')
GROUP BY region
ORDER BY total_amount ASC
LIMIT N;
```

## 冲突优先级

当一句话同时出现多个意图时，优先级如下：

1. **规则级 SQL 模板命中**
2. **显式数量**：`前2条`、`返回3条`、`后20名`
3. **极值词**：`最大`、`最小`、`最高`、`最低`
4. **位置词**：`第一个`、`最后一个`、`倒数第一个`、`末尾`
5. **默认值**：`LIMIT 3`

示例：
- `按销售额从高到低返回前2条` → `DESC + LIMIT 2`
- `最小的那条` → `ASC + LIMIT 1`
- `末尾的数据` → `ASC + LIMIT 1`
- `年度销售额最高的前100条数据` → 命中年度地区销售额排名模板

## 后端执行链路

### 1. 先解析意图
后端统一意图解析提取：
- `limit`
- `sort_order`
- `extreme_type`
- `position_type`
- `time_scope`
- `dimension_hint`
- `metric_hint`

### 2. 先做规则路由
- 明显 NL2SQL → 直接进入 NL2SQL
- 明显 CHAT → 直接进入聊天提示
- 模糊句 → 交给 `MiniMax-M2.7` 二分类

### 3. 再判断是否命中模板重写
若命中年度销售额排名模板，则：
- 直接生成 SQL
- 不再调用 LLM 生成 SQL

### 4. 未命中模板再拼 prompt
将解析出的意图明确写入 prompt：
- 条数
- 排序方向
- 极值模式
- 单条模式
- 时间范围提示
- 维度提示
- 指标提示

### 5. 最后做 SQL 后处理
无论模型怎么输出，后端都再次兜底：
- 强制 `LIMIT N`
- 必要时补 `ORDER BY ASC/DESC`
- 保证 `trace.sql` 与意图一致

## 前端展示规则

- `answer_text` 必须动态生成，不写死业务结论
- `table_data` 条数必须与 `LIMIT` 一致
- 图表、表格、SQL 必须同步显示当前结果
- 切换会话时要清空旧结果，避免串会话
- 新建会话时要防止重复点击造成重复创建

## 最终测试清单

### 数量类
- `按销售额从高到低返回前2条` → `LIMIT 2`
- `按销售额从高到低返回前三条` → `LIMIT 3`
- `返回前两名` → `LIMIT 2`
- `按销售额从低到高返回后20条` → `ASC + LIMIT 20`
- `后20名` → `ASC + LIMIT 20`

### 位置类
- `第一个` → `LIMIT 1`
- `最后一个` → `LIMIT 1`
- `倒数第一个` → `LIMIT 1`
- `末尾一个` → `LIMIT 1`

### 极值类
- `最大的那条` → `ORDER BY ... DESC LIMIT 1`
- `最小的那条` → `ORDER BY ... ASC LIMIT 1`
- `最高的一条` → `ORDER BY ... DESC LIMIT 1`
- `最低的一条` → `ORDER BY ... ASC LIMIT 1`

### 末尾类
- `末尾的数据` → `ORDER BY ... ASC LIMIT 1`
- `末尾的一条` → `ORDER BY ... ASC LIMIT 1`

### 年度类
- `年度前100名` → 当前年度 + `GROUP BY region` + `DESC + LIMIT 100`
- `年度排名最后100名` → 当前年度 + `GROUP BY region` + `ASC + LIMIT 100`
- `年度销售额最高的前100条数据` → 命中规则级模板，默认 `GROUP BY region`
- `年终后20名` → 当前年度 + `GROUP BY region` + `ASC + LIMIT 20`

### 路由类
- 模糊句未命中规则时，调用 `MiniMax-M2.7` 做 NL2SQL/CHAT 二分类
- 明显问候、自我介绍类，直接走 CHAT
- 明显统计、查询、排序类，直接走 NL2SQL

## 验收标准

- 语义规则在后端统一生效
- 所有测试用例的 `trace.sql` 与 `table_data` 条数一致
- 年度销售额排名类问题优先按 `region` 维度解释
- 前端不再展示写死的业务结论
- 新增规则时先更新此文件，再实现代码
