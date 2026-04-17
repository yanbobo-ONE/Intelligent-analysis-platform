---
name: NL2SQL语义规则与测试清单
overview: 固化 NL2SQL 场景下的数量、排序、极值与位置语义规则，并提供可执行的测试清单，作为后端解析、prompt 约束和 SQL 后处理的统一基线。
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
---

# NL2SQL 语义规则与测试清单

## 目标

将 NL2SQL 场景中的自然语言意图固化为一套稳定、可执行、可测试的规则，减少模型自由发挥带来的歧义，确保 SQL 生成、结果条数、排序方向、极值记录与前端展示完全一致。

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

## 冲突优先级

当一句话同时出现多个意图时，优先级如下：

1. **显式数量**：`前2条`、`返回3条`
2. **极值词**：`最大`、`最小`、`最高`、`最低`
3. **位置词**：`第一个`、`最后一个`、`倒数第一个`、`末尾`
4. **默认值**：`LIMIT 3`

示例：
- `按销售额从高到低返回前2条` → `DESC + LIMIT 2`
- `最小的那条` → `ASC + LIMIT 1`
- `末尾的数据` → `ASC + LIMIT 1`

## 后端执行链路

### 1. 先解析意图
建议在后端引入统一的意图解析函数：
- 提取 `limit`
- 提取 `sort_order`
- 提取 `extreme_type`
- 判断是否是位置类单条查询

### 2. 再拼接 prompt
将解析出的意图明确写入 prompt：
- 条数
- 排序方向
- 极值模式
- 单条模式

让模型只补齐 SQL 语法，不负责猜意图。

### 3. 最后做 SQL 后处理
无论模型怎么输出，后端都要再次兜底：
- 强制 `LIMIT N`
- 必要时补 `ORDER BY ASC/DESC`
- 保证 `trace.sql` 与意图一致

## 前端展示规则

- `answer_text` 必须动态生成，不写死业务结论
- `table_data` 条数必须与 `LIMIT` 一致
- 图表、表格、SQL 必须同步显示当前结果
- 切换会话时要清空旧结果，避免串会话

## 最终测试清单

### 数量类
- `按销售额从高到低返回前2条` → `LIMIT 2`
- `按销售额从高到低返回前三条` → `LIMIT 3`
- `返回前两名` → `LIMIT 2`

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

## 验收标准

- 语义规则在后端统一生效
- 所有测试用例的 `trace.sql` 与 `table_data` 条数一致
- 前端不再展示写死的业务结论
- 新增规则时先更新此文件，再实现代码
