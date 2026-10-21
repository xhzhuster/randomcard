"""Randomly select 10 cards from a 51-card pool with balance rules."""

from __future__ import annotations

import argparse
import csv
import math
import random
from dataclasses import dataclass
from pathlib import Path


CARD_COUNT = 51
SELECTION_COUNT = 10
GAME_COUNT = 2
REPEATABLE_CARD_COUNT = 9
MIN_ARROW_AVERAGE = 0.7
MAX_ARROW_AVERAGE = 0.9
MIN_ARROW_TOTAL = int(MIN_ARROW_AVERAGE * SELECTION_COUNT)
MAX_ARROW_TOTAL = int(MAX_ARROW_AVERAGE * SELECTION_COUNT)
ATTACK_DEFENSE_BALANCED_DIFFERENCES = (1,)
MAX_ATTACK_CARDS = 4
MAX_DEFENSE_CARDS = 2


@dataclass(frozen=True)
class Card:
    name: str
    arrows: int
    attack: int
    defense: int
    repeatable: bool


@dataclass(frozen=True)
class Selection:
    cards: tuple[Card, ...]
    arrow_total: int
    attack_total: int
    defense_total: int
    score: float


def load_cards(path: Path) -> list[Card]:
    """Load and validate cards from a CSV file."""
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    required = {"name", "arrows", "attack", "defense", "repeatable"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("CSV 必须包含列：name, arrows, attack, defense, repeatable")
    if len(rows) != CARD_COUNT:
        raise ValueError(f"卡牌数量必须正好是 {CARD_COUNT} 张，当前为 {len(rows)} 张")

    cards: list[Card] = []
    names: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        name = row["name"].strip()
        if not name or name in names:
            raise ValueError(f"第 {row_number} 行的卡牌名称为空或重复")
        try:
            card = Card(
                name=name,
                arrows=int(row["arrows"]),
                attack=int(row["attack"]),
                defense=int(row["defense"]),
                repeatable=row["repeatable"].strip() in {"1", "true", "True"},
            )
        except (TypeError, ValueError) as error:
            raise ValueError(f"第 {row_number} 行的数值字段必须是整数") from error
        if not 0 <= card.arrows <= 2:
            raise ValueError(f"第 {row_number} 行的 arrows 必须是 0、1 或 2")
        if not 0 <= card.attack <= 2:
            raise ValueError(f"第 {row_number} 行的 attack 必须是 0、1 或 2")
        if not 0 <= card.defense <= 2:
            raise ValueError(f"第 {row_number} 行的 defense 必须是 0、1 或 2")
        if card.attack > 0 and card.defense > 0:
            raise ValueError(f"第 {row_number} 行的 attack 和 defense 必须互斥")
        cards.append(card)
        names.add(name)
    if sum(card.repeatable for card in cards) != REPEATABLE_CARD_COUNT:
        raise ValueError(f"repeatable=1 的卡牌必须正好是 {REPEATABLE_CARD_COUNT} 张")
    return cards


def _targets(cards: list[Card]) -> tuple[float, float, float]:
    """Use the arrow range and a neutral attack-defense difference as targets."""
    return (
        (MIN_ARROW_TOTAL + MAX_ARROW_TOTAL) / 2,
        0.0,
        0.0,
    )


def _score(
    cards: tuple[Card, ...],
    targets: tuple[float, float, float],
    arrow_weight: float,
    combat_weight: float,
) -> tuple[float, int, int, int]:
    arrow_total = sum(card.arrows for card in cards)
    attack_total = sum(card.attack for card in cards)
    defense_total = sum(card.defense for card in cards)
    attack_card_count = sum(card.attack > 0 for card in cards)
    defense_card_count = sum(card.defense > 0 for card in cards)
    if MIN_ARROW_TOTAL <= arrow_total <= MAX_ARROW_TOTAL:
        arrow_error = 0.0
    else:
        arrow_error = (
            min(abs(arrow_total - MIN_ARROW_TOTAL), abs(arrow_total - MAX_ARROW_TOTAL))
            / MAX_ARROW_TOTAL
        )
    attack_defense_difference = attack_total - defense_total
    if attack_defense_difference in ATTACK_DEFENSE_BALANCED_DIFFERENCES:
        combat_error = 0.0
    else:
        distance = min(
            abs(attack_defense_difference - difference)
            for difference in ATTACK_DEFENSE_BALANCED_DIFFERENCES
        )
        combat_error = distance / max(SELECTION_COUNT, 1)
    count_error = (
        max(0, attack_card_count - MAX_ATTACK_CARDS)
        + max(0, defense_card_count - MAX_DEFENSE_CARDS)
    )
    return (
        arrow_weight * arrow_error + combat_weight * combat_error + 100 * count_error,
        arrow_total,
        attack_total,
        defense_total,
    )


def select_cards(
    cards: list[Card],
    *,
    seed: int | None = None,
    iterations: int = 20_000,
    arrow_weight: float = 1.0,
    combat_weight: float = 1.0,
) -> Selection:
    """Find a balanced hand while retaining randomness between equal-quality hands."""
    if len(cards) != CARD_COUNT:
        raise ValueError(f"选择器要求 {CARD_COUNT} 张卡牌")
    if iterations < 1:
        raise ValueError("iterations 必须大于 0")
    if arrow_weight < 0 or combat_weight < 0 or arrow_weight + combat_weight == 0:
        raise ValueError("至少有一个平衡规则权重必须大于 0")

    rng = random.Random(seed)
    targets = _targets(cards)
    current = tuple(rng.sample(cards, SELECTION_COUNT))
    current_score = _score(current, targets, arrow_weight, combat_weight)
    best = (current, current_score)

    temperature = 0.08
    for _ in range(iterations):
        inside = rng.randrange(SELECTION_COUNT)
        outside = rng.choice([card for card in cards if card not in current])
        candidate_list = list(current)
        candidate_list[inside] = outside
        candidate = tuple(candidate_list)
        candidate_score = _score(candidate, targets, arrow_weight, combat_weight)
        delta = candidate_score[0] - current_score[0]
        if delta <= 0 or rng.random() < math.exp(-delta / temperature):
            current, current_score = candidate, candidate_score
        if current_score[0] < best[1][0]:
            best = (current, current_score)

    cards_found, totals = best
    return Selection(
        cards=tuple(sorted(cards_found, key=lambda card: card.name)),
        arrow_total=totals[1],
        attack_total=totals[2],
        defense_total=totals[3],
        score=totals[0],
    )


def select_cards_with_blocked(
    cards: list[Card],
    blocked_nonrepeatable: set[Card],
    *,
    seed: int | None = None,
    iterations: int = 20_000,
    arrow_weight: float = 1.0,
    combat_weight: float = 1.0,
) -> Selection:
    """Re-random one game while excluding non-repeatable cards used by another game."""
    if len(cards) != CARD_COUNT:
        raise ValueError(f"选择器要求 {CARD_COUNT} 张卡牌")
    if iterations < 1:
        raise ValueError("iterations 必须大于 0")
    if arrow_weight < 0 or combat_weight < 0 or arrow_weight + combat_weight == 0:
        raise ValueError("至少有一个平衡规则权重必须大于 0")
    if any(card.repeatable for card in blocked_nonrepeatable):
        raise ValueError("blocked_nonrepeatable 中不应包含可重复卡牌")

    available_cards = [card for card in cards if card not in blocked_nonrepeatable]
    if len(available_cards) < SELECTION_COUNT:
        raise ValueError("可用卡牌不足 10 张，无法重随机")

    rng = random.Random(seed)
    targets = _targets(cards)
    current = tuple(rng.sample(available_cards, SELECTION_COUNT))
    current_score = _score(current, targets, arrow_weight, combat_weight)
    best = (current, current_score)

    temperature = 0.08
    for _ in range(iterations):
        inside = rng.randrange(SELECTION_COUNT)
        outside = rng.choice([card for card in available_cards if card not in current])
        candidate_list = list(current)
        candidate_list[inside] = outside
        candidate = tuple(candidate_list)
        candidate_score = _score(candidate, targets, arrow_weight, combat_weight)
        delta = candidate_score[0] - current_score[0]
        if delta <= 0 or rng.random() < math.exp(-delta / temperature):
            current, current_score = candidate, candidate_score
        if current_score[0] < best[1][0]:
            best = (current, current_score)

    cards_found, totals = best
    return Selection(
        cards=tuple(sorted(cards_found, key=lambda card: card.name)),
        arrow_total=totals[1],
        attack_total=totals[2],
        defense_total=totals[3],
        score=totals[0],
    )


def _selection_from_cards(
    cards: tuple[Card, ...],
    targets: tuple[float, float, float],
    arrow_weight: float,
    combat_weight: float,
) -> Selection:
    totals = _score(cards, targets, arrow_weight, combat_weight)
    return Selection(
        cards=tuple(sorted(cards, key=lambda card: card.name)),
        arrow_total=totals[1],
        attack_total=totals[2],
        defense_total=totals[3],
        score=totals[0],
    )


def select_two_games(
    cards: list[Card],
    *,
    seed: int | None = None,
    iterations: int = 40_000,
    arrow_weight: float = 1.0,
    combat_weight: float = 1.0,
) -> tuple[Selection, Selection]:
    """Select two balanced games while sharing only explicitly repeatable cards."""
    if len(cards) != CARD_COUNT:
        raise ValueError(f"选择器要求 {CARD_COUNT} 张卡牌")
    if sum(card.repeatable for card in cards) != REPEATABLE_CARD_COUNT:
        raise ValueError(f"可重复卡牌必须正好是 {REPEATABLE_CARD_COUNT} 张")
    if iterations < 1:
        raise ValueError("iterations 必须大于 0")

    rng = random.Random(seed)
    targets = _targets(cards)
    first = tuple(rng.sample(cards, SELECTION_COUNT))
    allowed_second = [
        card for card in cards
        if card.repeatable or card not in first
    ]
    second = tuple(rng.sample(allowed_second, SELECTION_COUNT))
    current = [first, second]
    current_scores = [
        _score(hand, targets, arrow_weight, combat_weight) for hand in current
    ]
    best = (tuple(current[0]), tuple(current[1]), sum(score[0] for score in current_scores))

    temperature = 0.08
    for _ in range(iterations):
        game_index = rng.randrange(GAME_COUNT)
        other = current[1 - game_index]
        used_elsewhere = set(other)
        eligible = [
            card for card in cards
            if card not in current[game_index]
            and (card.repeatable or card not in used_elsewhere)
        ]
        if not eligible:
            continue
        card_index = rng.randrange(SELECTION_COUNT)
        candidate_hand = list(current[game_index])
        candidate_hand[card_index] = rng.choice(eligible)
        candidate = tuple(candidate_hand)
        candidate_score = _score(candidate, targets, arrow_weight, combat_weight)
        delta = candidate_score[0] - current_scores[game_index][0]
        if delta <= 0 or rng.random() < math.exp(-delta / temperature):
            current[game_index] = candidate
            current_scores[game_index] = candidate_score
        total_score = sum(score[0] for score in current_scores)
        if total_score < best[2]:
            best = (tuple(current[0]), tuple(current[1]), total_score)

    return (
        _selection_from_cards(best[0], targets, arrow_weight, combat_weight),
        _selection_from_cards(best[1], targets, arrow_weight, combat_weight),
    )


def _parse_ongoing_cards(value: str, cards: list[Card]) -> tuple[Card, ...]:
    names = [name.strip() for name in value.split(",") if name.strip()]
    if len(names) != SELECTION_COUNT:
        raise ValueError(f"--ongoing-cards 必须提供 {SELECTION_COUNT} 张卡牌名称")
    if len(set(names)) != SELECTION_COUNT:
        raise ValueError("--ongoing-cards 里有重复卡牌名称")

    card_map = {card.name: card for card in cards}
    ongoing_cards: list[Card] = []
    unknown: list[str] = []
    for name in names:
        card = card_map.get(name)
        if card is None:
            unknown.append(name)
        else:
            ongoing_cards.append(card)
    if unknown:
        raise ValueError(f"--ongoing-cards 存在未知卡牌：{', '.join(unknown)}")
    return tuple(ongoing_cards)


def _print_selection(title: str, selection: Selection) -> None:
    print(title)
    for index, card in enumerate(selection.cards, start=1):
        print(f"{index:2}. {card.name} | 箭头 {card.arrows} | 攻击 {card.attack} | 防御 {card.defense}")
    arrow_average = selection.arrow_total / SELECTION_COUNT
    attack_defense_difference = selection.attack_total - selection.defense_total
    attack_card_count = sum(card.attack > 0 for card in selection.cards)
    defense_card_count = sum(card.defense > 0 for card in selection.cards)
    print(
        f"合计：箭头={selection.arrow_total}（平均 {arrow_average:.1f}），"
        f"攻击={selection.attack_total}，防御={selection.defense_total}，"
        f"攻击-防御={attack_defense_difference}"
    )
    print(f"牌数：攻击牌={attack_card_count}（最多 {MAX_ATTACK_CARDS}），"
          f"防御牌={defense_card_count}（最多 {MAX_DEFENSE_CARDS}）")
    print(f"平衡分数（越低越好）：{selection.score:.4f}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="从 51 张卡牌中随机挑选 10 张平衡卡组")
    parser.add_argument("csv_file", type=Path, help="卡牌 CSV 文件")
    parser.add_argument("--seed", type=int, help="随机种子；相同种子得到可复现结果")
    parser.add_argument("--iterations", type=int, default=20_000)
    parser.add_argument("--arrow-weight", type=float, default=1.0)
    parser.add_argument("--combat-weight", type=float, default=1.0)
    parser.add_argument(
        "--ongoing-cards",
        help="正在进行中的那一场 10 张卡牌名称，使用逗号分隔。程序会重随机另一场并避开其中不可重复卡牌。",
    )
    args = parser.parse_args()
    cards = load_cards(args.csv_file)
    if args.ongoing_cards:
        ongoing_cards = _parse_ongoing_cards(args.ongoing_cards, cards)
        blocked_nonrepeatable = {card for card in ongoing_cards if not card.repeatable}
        rerolled = select_cards_with_blocked(
            cards,
            blocked_nonrepeatable,
            seed=args.seed,
            iterations=args.iterations,
            arrow_weight=args.arrow_weight,
            combat_weight=args.combat_weight,
        )
        ongoing_selection = _selection_from_cards(
            ongoing_cards,
            _targets(cards),
            args.arrow_weight,
            args.combat_weight,
        )
        _print_selection("正在进行中的那一场（输入）：", ongoing_selection)
        _print_selection("重随机后的另一场：", rerolled)

        ongoing_nonrepeatable_names = {card.name for card in ongoing_cards if not card.repeatable}
        rerolled_names = {card.name for card in rerolled.cards}
        conflicted = sorted(ongoing_nonrepeatable_names & rerolled_names)
        if conflicted:
            raise RuntimeError(
                "重随机结果错误：出现了与进行中卡组冲突的不可重复卡牌："
                + ", ".join(conflicted)
            )
        print("冲突检查：通过（未使用进行中卡组里的不可重复卡牌）")
        return

    selections = select_two_games(
        cards,
        seed=args.seed,
        iterations=args.iterations,
        arrow_weight=args.arrow_weight,
        combat_weight=args.combat_weight,
    )
    for game_index, selection in enumerate(selections, start=1):
        _print_selection(f"第 {game_index} 场选中的 10 张卡牌：", selection)


if __name__ == "__main__":
    main()
