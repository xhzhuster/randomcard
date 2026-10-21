"""Mobile web interface for the random card selector."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, render_template_string, request

from card_selector import (
    SELECTION_COUNT,
    load_cards,
    select_cards_with_blocked,
    select_two_games,
)


BASE_DIR = Path(__file__).resolve().parent
CARDS_FILE = BASE_DIR / "cards.example.csv"
app = Flask(__name__)


PAGE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>随机卡牌</title>
  <style>
    :root { color-scheme: dark; font-family: system-ui, sans-serif; }
    body { margin: 0; background: #171923; color: #f4f4f5; }
    main { max-width: 760px; margin: auto; padding: 20px 14px 44px; }
    h1 { font-size: 1.65rem; margin: 0 0 8px; }
    h2 { font-size: 1.2rem; margin: 22px 0 8px; }
    p, label { color: #c9cad1; }
    .panel, .game { background: #242633; border: 1px solid #3b3e4e;
      border-radius: 14px; padding: 16px; margin-top: 14px; }
    button { width: 100%; border: 0; border-radius: 10px; padding: 13px;
      margin-top: 10px; background: #7567f8; color: white; font-size: 1rem; }
    button.secondary { background: #3b82f6; }
    textarea { box-sizing: border-box; width: 100%; min-height: 88px; margin-top: 8px;
      padding: 10px; border-radius: 9px; border: 1px solid #55596c;
      background: #171923; color: white; font-size: 1rem; }
    .error { color: #ff9c9c; white-space: pre-wrap; }
    .card { display: flex; justify-content: space-between; gap: 8px;
      padding: 8px 0; border-bottom: 1px solid #393c4b; }
    .card:last-child { border-bottom: 0; }
    .stats { color: #a8e6cf; margin-top: 12px; line-height: 1.7; }
    .hint { font-size: .9rem; }
  </style>
</head>
<body>
<main>
  <h1>51 张卡牌随机选择器</h1>
  <p class="hint">每场 10 张｜箭头平均 0.7–0.9｜攻击−防御=1</p>

  <section class="panel">
    <form method="post" action="/generate">
      <button type="submit">生成两场游戏</button>
    </form>
  </section>

  <section class="panel">
    <h2>单场重随机</h2>
    <p class="hint">输入正在进行中的 10 张卡牌名称，用逗号分隔。不可重复卡牌会自动避开。</p>
    <form method="post" action="/reroll">
      <textarea name="ongoing_cards" placeholder="例如：爱丽丝,八云紫,稗田阿求,...">{{ ongoing_cards }}</textarea>
      <button class="secondary" type="submit">重随机另一场</button>
    </form>
  </section>

  {% if error %}<section class="panel error">{{ error }}</section>{% endif %}
  {% for result in results %}
    <section class="game">
      <h2>{{ result.title }}</h2>
      {% for card in result.cards %}
        <div class="card"><span>{{ loop.index }}. {{ card.name }}</span>
          <span>箭头 {{ card.arrows }}｜攻 {{ card.attack }}｜防 {{ card.defense }}</span></div>
      {% endfor %}
      <div class="stats">
        箭头 {{ result.arrow_total }}（平均 {{ "%.1f"|format(result.arrow_average) }}）
        ｜攻击 {{ result.attack_total }}｜防御 {{ result.defense_total }}
        ｜攻击−防御 {{ result.difference }}<br>
        攻击牌 {{ result.attack_count }} 张｜防御牌 {{ result.defense_count }} 张
      </div>
    </section>
  {% endfor %}
</main>
</body>
</html>
"""


def format_result(title: str, cards) -> dict:
    attack_total = sum(card.attack for card in cards)
    defense_total = sum(card.defense for card in cards)
    return {
        "title": title,
        "cards": cards,
        "arrow_total": sum(card.arrows for card in cards),
        "arrow_average": sum(card.arrows for card in cards) / SELECTION_COUNT,
        "attack_total": attack_total,
        "defense_total": defense_total,
        "difference": attack_total - defense_total,
        "attack_count": sum(card.attack > 0 for card in cards),
        "defense_count": sum(card.defense > 0 for card in cards),
    }


def render_page(*, results=None, error="", ongoing_cards=""):
    return render_template_string(
        PAGE,
        results=results or [],
        error=error,
        ongoing_cards=ongoing_cards,
    )


@app.get("/")
def index():
    return render_page()


@app.post("/generate")
def generate():
    try:
        cards = load_cards(CARDS_FILE)
        selections = select_two_games(cards)
        results = [
            format_result(f"第 {index} 场", selection.cards)
            for index, selection in enumerate(selections, start=1)
        ]
        return render_page(results=results)
    except (OSError, ValueError) as error:
        return render_page(error=f"生成失败：{error}"), 400


@app.post("/reroll")
def reroll():
    ongoing_text = request.form.get("ongoing_cards", "")
    try:
        cards = load_cards(CARDS_FILE)
        names = [name.strip() for name in ongoing_text.split(",") if name.strip()]
        if len(names) != SELECTION_COUNT:
            raise ValueError(f"请输入正好 {SELECTION_COUNT} 个卡牌名称")
        if len(set(names)) != SELECTION_COUNT:
            raise ValueError("卡牌名称不能重复")
        card_by_name = {card.name: card for card in cards}
        unknown = [name for name in names if name not in card_by_name]
        if unknown:
            raise ValueError(f"未知卡牌：{', '.join(unknown)}")
        ongoing = tuple(card_by_name[name] for name in names)
        blocked = {card for card in ongoing if not card.repeatable}
        rerolled = select_cards_with_blocked(cards, blocked)
        results = [
            format_result("正在进行中的那一场", ongoing),
            format_result("重随机后的另一场", rerolled.cards),
        ]
        return render_page(results=results, ongoing_cards=ongoing_text)
    except (OSError, ValueError) as error:
        return render_page(error=f"重随机失败：{error}", ongoing_cards=ongoing_text), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
