# 中试投料配平工作台（Stoichiometric Balancing Workbench）

全栈配平工作台：工艺化学师录入反应物与产物的元素组成，服务端用**精确有理数**
（`fractions.Fraction`）高斯消元求守恒矩阵的零空间，只在解**唯一且可全正**时
签发唯一原始整数系数，否则给出明确的不可认证原因。页面提供人工系数复核区，
逐元素验算；任何输入修改都会立即撤销旧证书。

当原子守恒成立却存在多组可行系数时，可使用**比例约束配平入口**：填写一至两条
已批准的「化合物 A 系数 : 化合物 B 系数」正整数比例，服务端把每条比例
`q·c_A − p·c_B = 0` 作为精确有理数新约束行与守恒矩阵**共同消元**，只有约束后
零空间维数为一且能整体化为全正原始整数向量时才签发证书；约束互相矛盾、仍有
多解、唯一向量含零或异号分别对应下表四个状态，绝不挑选自由变量伪装唯一解。
人工复核在填写了比例时会同时检查系数是否满足所填比例。

## 为什么是精确有理数

- 浮点高斯消元会把近似零的枢轴当成真实约束，可能改变零空间维数；
  本项目全程 `Fraction` 精确运算，只有 `!= 0` 的严格非零才作枢轴。
- 自由变量不做任何人为挑选：零空间维数由消元后的枢轴列客观决定。
  维数 > 1 一律判 `UNDERDETERMINED`，多解体系不可能被伪装成唯一配方。

## 判定状态码

| 状态码 | 含义 |
| --- | --- |
| `BALANCED` | 零空间维数 = 1，生成向量可统一为全正；已按分母最小公倍数化为整数并除以整体最大公约数，返回**唯一原始系数**与逐元素两侧总数 |
| `NO_BALANCE` | 零空间维数 = 0，守恒方程无解（比例约束下：守恒与比例互相矛盾） |
| `UNDERDETERMINED` | 零空间维数 > 1，存在多组配方，不签发唯一结论（比例约束下：约束后仍有多解） |
| `NO_POSITIVE_BALANCE` | 维数 = 1，但唯一生成向量含零项（有化合物不参与）或无法统一为全正 |

## 目录结构

```
api/                 FastAPI + 精确有理数计算核心
  app/
    balancer.py      守恒矩阵、比例约束行、RREF 零空间、整数化、逐元素合计、人工复核
    elements.py      118 个 IUPAC 元素符号白名单
    schemas.py       Pydantic 请求模型（extra=forbid，StrictInt 拒绝布尔）
    validation.py    结构 + 语义校验，整份拒绝并返回稳定错误码
    main.py          /api/balance、/api/review、/api/balance/constrained、
                     /api/review/constrained、/health
  Dockerfile
web/                 React + TypeScript + Vite
  src/
    App.tsx          revision 机制：化合物或比例修改即撤销旧证书/旧复核
    components/      化合物矩阵编辑、比例约束录入、守恒矩阵预览、结论、人工复核
    lib/             API 客户端、本地预检、元素符号表
  Dockerfile         多阶段构建，nginx 同源代理 /api → api:8000
tests/               pytest（含小矩阵整数穷举交叉验证，含比例约束枚举核对）
e2e/                 Playwright（两条端到端流程）
docker-compose.yml   服务名：web（页面，宿主 8080）、api（内部 8000）
```

## 用 Docker Compose 运行

```bash
docker compose up --build
# 页面：http://localhost:8080
# 接口（经由 web 同源代理）：http://localhost:8080/health
```

## 本地开发

```bash
# 后端（Python 3.11）
pip install -r api/requirements-dev.txt
cd api && uvicorn app.main:app --reload --port 8000

# 前端（Node 20）
cd web
npm install
npm run dev                                 # http://localhost:5173，/api 已代理到 :8000
```

## 测试

```bash
# 后端：64 项，含对 3 万余个小矩阵的整数穷举核对（含比例约束枚举）
python3 -m pytest

# 端到端：「录入 → 求解 → 复核 → 改输入撤销证书」与
# 「多解 → 比例约束变唯一 → 复核检查比例 → 修改比例/化合物撤销证书」两条流程
cd e2e
npm install
npx playwright install chromium
BASE_URL=http://localhost:5173 npx playwright test      # 本地开发
BASE_URL=http://localhost:8080 npx playwright test      # compose 环境
```

穷举交叉验证（`tests/test_exhaustive.py`）使用与被测代码**独立**的整数预言机：
秩由拉普拉斯行列式计算，秩 n−1 时的零向量由固定行集的带符号最大子式直接给出，
再与 Fraction RREF 的结果逐项比对，并枚举有界原始正整数解验证唯一性。
比例约束的穷举核对（`tests/test_constrained_exhaustive.py`）复用同一整数预言机：
把比例行 `q·c_A − p·c_B = 0` 与守恒行堆叠后独立求秩、正性与整数化，
逐一比对约束后零空间维数、状态码与签发的原始整数向量，并验证签发系数
精确满足每条比例。

## HTTP 接口

### `POST /api/balance`

```json
{
  "compounds": [
    {"id": "H2",  "side": "REACTANT", "composition": {"H": 2}},
    {"id": "O2",  "side": "REACTANT", "composition": {"O": 2}},
    {"id": "H2O", "side": "PRODUCT",  "composition": {"H": 2, "O": 1}}
  ]
}
```

`BALANCED` 响应：

```json
{
  "status": "BALANCED",
  "nullity": 1,
  "elements": ["H", "O"],
  "compound_ids": ["H2", "O2", "H2O"],
  "coefficients": {"H2": 2, "O2": 1, "H2O": 2},
  "element_totals": [
    {"element": "H", "reactant": 4, "product": 4, "balanced": true},
    {"element": "O", "reactant": 2, "product": 2, "balanced": true}
  ],
  "equation": "2 H2 + O2 -> 2 H2O"
}
```

### `POST /api/review`

请求体在上述基础上增加 `coefficients`（ID → 人工填写的整数）。
服务端独立重新核算并返回：每个元素两侧合计与是否守恒、整体最大公约数、
是否最简、缺失/未知/非正系数 ID，以及机器可读的 `reasons`
（`NOT_CONSERVED`、`NOT_PRIMITIVE`、`MISSING_COEFFICIENTS`、
`UNKNOWN_COEFFICIENT_IDS`、`NON_POSITIVE_COEFFICIENT`）。

### `POST /api/balance/constrained`（比例约束配平入口）

请求体在 `/api/balance` 基础上增加 `ratios`（一至两条）：

```json
{
  "compounds": [
    {"id": "H2",   "side": "REACTANT", "composition": {"H": 2}},
    {"id": "O2",   "side": "REACTANT", "composition": {"O": 2}},
    {"id": "H2O",  "side": "PRODUCT",  "composition": {"H": 2, "O": 1}},
    {"id": "H2O2", "side": "PRODUCT",  "composition": {"H": 2, "O": 2}}
  ],
  "ratios": [
    {"a": "H2O", "b": "H2O2", "a_coefficient": 2, "b_coefficient": 1}
  ]
}
```

每条比例表示 `系数[a] : 系数[b] = a_coefficient : b_coefficient`，即精确约束行
`b_coefficient·c_a − a_coefficient·c_b = 0`，与守恒矩阵共同消元。响应在
`/api/balance` 的基础上原样回显 `ratios` 作为签发的比例依据；上例无比例时
`UNDERDETERMINED`（维数 2），加比例后：

```json
{
  "status": "BALANCED",
  "nullity": 1,
  "coefficients": {"H2": 3, "O2": 2, "H2O": 2, "H2O2": 1},
  "equation": "3 H2 + 2 O2 -> 2 H2O + H2O2",
  "ratios": [{"a": "H2O", "b": "H2O2", "a_coefficient": 2, "b_coefficient": 1}]
}
```

### `POST /api/review/constrained`

请求体在 `/api/review` 基础上增加同样的 `ratios`。响应包含原复核全部字段，
并追加：每条比例的逐项判定 `ratios[].satisfied`、被违反比例的下标列表
`violated_ratios`，以及新的机器可读原因 `RATIO_VIOLATED`（系数守恒但不满足
所填比例时复核不通过）。

无比例的 `/api/balance` 与 `/api/review` 请求及响应保持原样（向它们发送
`ratios` 字段会按未知字段被 422 拒绝）。

## 输入规则（违反任意一条整份拒绝，HTTP 422）

- 化合物 2–12 个；ID 为非空、唯一的 ASCII 字符串；
- `side` 只能是 `REACTANT` 或 `PRODUCT`；
- 组成为元素符号 → **正整数**的 JSON 映射（拒绝 0、负数、小数、布尔值）；
  元素符号必须属于 118 个 IUPAC 符号，组成不能为空；
- 全批不同元素总数不超过 20；
- 比例约束 1–2 条；`a`、`b` 必须引用两个不同的已录入化合物 ID，
  两个系数都必须是**正整数**（拒绝 0、负数、小数、布尔值）；
  比例互相矛盾不是输入错误，而是由求解器明确判 `NO_BALANCE`；
- 任何未知 JSON 字段一律拒绝。

比例相关错误码：`INVALID_RATIO_COUNT`、`EMPTY_RATIO_COMPOUND`、
`UNKNOWN_RATIO_COMPOUND`、`RATIO_SAME_COMPOUND`、`NON_POSITIVE_RATIO`。
