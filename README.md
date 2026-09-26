# 中试投料配平工作台（Stoichiometric Balancing Workbench）

全栈配平工作台：工艺化学师录入反应物与产物的元素组成，服务端用**精确有理数**
（`fractions.Fraction`）高斯消元求守恒矩阵的零空间，只在解**唯一且可全正**时
签发唯一原始整数系数，否则给出明确的不可认证原因。页面提供人工系数复核区，
逐元素验算；任何输入修改都会立即撤销旧证书。

## 为什么是精确有理数

- 浮点高斯消元会把近似零的枢轴当成真实约束，可能改变零空间维数；
  本项目全程 `Fraction` 精确运算，只有 `!= 0` 的严格非零才作枢轴。
- 自由变量不做任何人为挑选：零空间维数由消元后的枢轴列客观决定。
  维数 > 1 一律判 `UNDERDETERMINED`，多解体系不可能被伪装成唯一配方。

## 判定状态码

| 状态码 | 含义 |
| --- | --- |
| `BALANCED` | 零空间维数 = 1，生成向量可统一为全正；已按分母最小公倍数化为整数并除以整体最大公约数，返回**唯一原始系数**与逐元素两侧总数 |
| `NO_BALANCE` | 零空间维数 = 0，守恒方程无解 |
| `UNDERDETERMINED` | 零空间维数 > 1，存在多组配方，不签发唯一结论 |
| `NO_POSITIVE_BALANCE` | 维数 = 1，但唯一生成向量含零项（有化合物不参与）或无法统一为全正 |

## 目录结构

```
api/                 FastAPI + 精确有理数计算核心
  app/
    balancer.py      守恒矩阵、RREF 零空间、整数化、逐元素合计、人工复核
    elements.py      118 个 IUPAC 元素符号白名单
    schemas.py       Pydantic 请求模型（extra=forbid，StrictInt 拒绝布尔）
    validation.py    结构 + 语义校验，整份拒绝并返回稳定错误码
    main.py          /api/balance、/api/review、/health
  Dockerfile
web/                 React + TypeScript + Vite
  src/
    App.tsx          revision 机制：输入修改即撤销旧证书/旧复核
    components/      化合物矩阵编辑、守恒矩阵预览、结论、人工复核
    lib/             API 客户端、本地预检、元素符号表
  Dockerfile         多阶段构建，nginx 同源代理 /api → api:8000
tests/               pytest（含小矩阵整数穷举交叉验证）
e2e/                 Playwright（且仅有一条端到端流程）
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
# 后端：37 项，含对 3 万余个小矩阵的整数穷举核对
python3 -m pytest

# 端到端：唯一一条「录入 → 求解 → 复核 → 改输入撤销证书」流程
cd e2e
npm install
npx playwright install chromium
BASE_URL=http://localhost:5173 npx playwright test      # 本地开发
BASE_URL=http://localhost:8080 npx playwright test      # compose 环境
```

穷举交叉验证（`tests/test_exhaustive.py`）使用与被测代码**独立**的整数预言机：
秩由拉普拉斯行列式计算，秩 n−1 时的零向量由固定行集的带符号最大子式直接给出，
再与 Fraction RREF 的结果逐项比对，并枚举有界原始正整数解验证唯一性。

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

## 输入规则（违反任意一条整份拒绝，HTTP 422）

- 化合物 2–12 个；ID 为非空、唯一的 ASCII 字符串；
- `side` 只能是 `REACTANT` 或 `PRODUCT`；
- 组成为元素符号 → **正整数**的 JSON 映射（拒绝 0、负数、小数、布尔值）；
  元素符号必须属于 118 个 IUPAC 符号，组成不能为空；
- 全批不同元素总数不超过 20；
- 任何未知 JSON 字段一律拒绝。
