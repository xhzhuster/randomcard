# 51 张卡牌随机选择器

程序一次从 51 张卡牌中随机生成两组卡牌，每组 10 张，并同时优化以下规则：

1. **箭头数量平衡**：每张卡的箭头只能是 `0`、`1` 或 `2`；所选 10 张的箭头平均值必须落在 `0.7–0.9`，也就是箭头总数为 `7–9`。
2. **攻击防御平衡**：攻击牌和防御牌互斥；攻击值只能是 `0–2`，防御值只能是 `0–2`。所选 10 张的攻击总值减去防御总值必须为 `1`。
3. **攻击防御牌数量限制**：防御牌不得超过 `2` 张，攻击牌不得超过 `4` 张。
4. **两场之间的重复限制**：CSV 中 `repeatable=1` 的 9 张卡牌可以在两场同时出现；其余卡牌在两场之间不得重复。

另外支持**单场重随机**：当一场已结束、另一场仍在进行时，可输入正在进行中的 10 张卡牌，程序会重随机另一场，并自动避开正在进行中那一场所占用的不可重复卡牌。

平衡分数越低越好。算法使用随机初始组合和随机交换搜索，因此每次运行通常会得到不同组合；使用相同 `--seed` 可以复现结果。

## 卡牌数据

复制并修改 [cards.example.csv](cards.example.csv)。CSV 必须有且只能按以下字段提供 51 张卡牌：

```text
name,arrows,attack,defense,repeatable
```

其中 `arrows` 必须是 `0`、`1` 或 `2`，`attack` 和 `defense` 必须是 `0`、`1` 或 `2`。单张卡牌的 `attack` 和 `defense` 不能同时大于 0，`name` 不能重复。`repeatable=1` 必须正好有 9 张。

## 运行

```powershell
python card_selector.py cards.example.csv
python card_selector.py cards.example.csv --seed 42
```

如果只重随机“已结束”的那一场，请传入“正在进行中”的卡牌名称（逗号分隔、共 10 张）：

```powershell
python card_selector.py cards.example.csv --ongoing-cards "卡牌01,卡牌02,卡牌03,卡牌04,卡牌05,卡牌06,卡牌07,卡牌08,卡牌09,卡牌10"
```

该模式会输出：

1. 正在进行中的那一场（你输入的卡组）
2. 重随机后的另一场
3. 冲突检查结果（确保没有使用进行中卡组里的不可重复卡牌）

## Android APK

项目已包含 [main.py](main.py) 手机界面和 [buildozer.spec](buildozer.spec) 打包配置。当前 [cards.example.csv](cards.example.csv) 会被固定内置到 APK 中，手机不需要再选择 CSV 文件。

在 Linux 或 WSL2 Ubuntu 中构建：

```bash
sudo apt update
sudo apt install -y python3-pip git zip unzip openjdk-17-jdk
python3 -m pip install --user buildozer cython
buildozer android debug
```

构建成功后，APK 通常位于 `bin/` 目录。将 APK 复制到 Android 手机并安装即可。

手机界面提供：

- 生成两场游戏
- 输入正在进行中的 10 张卡牌
- 重随机另一场
- 自动避开不可重复卡牌

可以调整两条规则的影响权重：

```powershell
python card_selector.py cards.example.csv --arrow-weight 2 --combat-weight 1
```

这表示箭头平衡的重要性是攻击/防御平衡的两倍。`--iterations` 越大，通常越容易找到更优组合，但运行时间也会增加。

## 部署为在线网页

项目已包含 [web_app.py](web_app.py)、[requirements.txt](requirements.txt) 和 [render.yaml](render.yaml)。
网页会读取同目录下的 [cards.example.csv](cards.example.csv)，提供“生成两场游戏”和“单场重随机”两个按钮。

### 使用 Render 部署

1. 将项目上传到 GitHub 仓库，至少包含：
   `web_app.py`、`card_selector.py`、`cards.example.csv`、`requirements.txt`、`render.yaml`。
2. 登录 Render，选择 **New → Blueprint**。
3. 选择该 GitHub 仓库并部署。
4. 部署完成后，Render 会提供一个 `onrender.com` 地址，手机直接打开即可。

如果不使用 Blueprint，也可以创建 Web Service，并填写：

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn web_app:app
```

### 本地先测试网页

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe .\web_app.py
```

然后浏览器打开：

```text
http://127.0.0.1:5000
```
