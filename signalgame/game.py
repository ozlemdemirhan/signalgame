from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import random
from typing import Dict, Iterable, List, Optional, Tuple


class Owner(str, Enum):
    PLAYER = "player"
    ENEMY = "enemy"
    NEUTRAL = "neutral"


@dataclass
class Region:
    position: Tuple[int, int]
    owner: Owner = Owner.NEUTRAL
    enemy_count: int = 0
    player_count: int = 0
    is_frontline: bool = False
    is_active: bool = False

    def total(self) -> int:
        return self.enemy_count + self.player_count


@dataclass
class GameConfig:
    size: int = 5
    enemy_total: int = 100
    player_total: int = 80
    player_reinforcements: int = 10
    seed: Optional[int] = None


@dataclass
class IntelReport:
    region: Tuple[int, int]
    signal: str


@dataclass
class AttackOrder:
    source: Tuple[int, int]
    target: Tuple[int, int]
    troops: int


@dataclass
class BattleResult:
    target: Tuple[int, int]
    winner: Owner
    remaining: int
    attacker_losses: int
    defender_losses: int


@dataclass
class Game:
    config: GameConfig
    grid: Dict[Tuple[int, int], Region] = field(init=False)
    turn: int = 1

    def __post_init__(self) -> None:
        if self.config.seed is not None:
            random.seed(self.config.seed)
        self.grid = {}
        self._init_grid()
        self._distribute_initial_forces()
        self._refresh_frontlines()

    def _init_grid(self) -> None:
        for x in range(self.config.size):
            for y in range(self.config.size):
                self.grid[(x, y)] = Region(position=(x, y))

    def _neighbors(self, pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        x, y = pos
        neighbors = [
            (x - 1, y),
            (x + 1, y),
            (x, y - 1),
            (x, y + 1),
        ]
        return [p for p in neighbors if p in self.grid]

    def _init_owners(self) -> None:
        max_index = self.config.size - 1
        for (x, y), region in self.grid.items():
            if y == 0:
                region.owner = Owner.ENEMY
            elif y == max_index:
                region.owner = Owner.PLAYER
            else:
                region.owner = Owner.NEUTRAL

    def _distribute_initial_forces(self) -> None:
        self._init_owners()
        enemy_regions = [r for r in self.grid.values() if r.owner == Owner.ENEMY]
        player_regions = [r for r in self.grid.values() if r.owner == Owner.PLAYER]
        self._strategic_distribute(self.config.enemy_total, enemy_regions, Owner.ENEMY)
        self._strategic_distribute(self.config.player_total, player_regions, Owner.PLAYER)

    def _strategic_distribute(self, total: int, regions: List[Region], owner: Owner) -> None:
        if not regions:
            return
        weights = [1 + (abs(r.position[0] - (self.config.size // 2))) for r in regions]
        allocation = self._weighted_split(total, weights)
        for region, troops in zip(regions, allocation):
            if owner == Owner.ENEMY:
                region.enemy_count += troops
            else:
                region.player_count += troops
            region.is_active = True

    def _weighted_split(self, total: int, weights: List[int]) -> List[int]:
        total_weight = sum(weights)
        if total_weight == 0:
            return [0 for _ in weights]
        base = [int(total * (w / total_weight)) for w in weights]
        remainder = total - sum(base)
        for _ in range(remainder):
            base[random.randrange(len(base))] += 1
        return base

    def _refresh_frontlines(self) -> None:
        for region in self.grid.values():
            if region.owner == Owner.NEUTRAL:
                region.is_frontline = False
                continue
            neighbors = self._neighbors(region.position)
            region.is_frontline = any(self.grid[n].owner != region.owner for n in neighbors)

    def intel_report(self) -> List[IntelReport]:
        reports: List[IntelReport] = []
        for region in self.grid.values():
            if region.owner == Owner.ENEMY:
                if region.is_frontline and random.random() < 0.6:
                    reports.append(IntelReport(region.position, "Bu bölgede düşman hareketliliği var"))
                elif random.random() < 0.2:
                    reports.append(IntelReport(region.position, "Sinyal alındı"))
            elif region.owner == Owner.NEUTRAL and random.random() < 0.1:
                reports.append(IntelReport(region.position, "Yanıltıcı bilgi olabilir"))
        if not reports:
            random_region = random.choice(list(self.grid.values()))
            reports.append(IntelReport(random_region.position, "Sessizlik"))
        return reports

    def apply_player_deployment(self, deployments: Dict[Tuple[int, int], int]) -> None:
        remaining = self.config.player_reinforcements
        for pos, troops in deployments.items():
            if troops <= 0 or remaining <= 0:
                continue
            region = self.grid.get(pos)
            if not region:
                continue
            if not self._player_can_deploy(pos):
                continue
            troops_to_add = min(troops, remaining)
            region.player_count += troops_to_add
            region.is_active = True
            remaining -= troops_to_add

    def _player_can_deploy(self, pos: Tuple[int, int]) -> bool:
        region = self.grid[pos]
        if region.owner == Owner.PLAYER:
            return True
        return any(self.grid[n].owner == Owner.PLAYER for n in self._neighbors(pos))

    def enemy_orders(self) -> List[AttackOrder]:
        orders: List[AttackOrder] = []
        frontline = [r for r in self.grid.values() if r.owner == Owner.ENEMY and r.is_frontline]
        if not frontline:
            return orders
        random.shuffle(frontline)
        for region in frontline:
            targets = [
                self.grid[n]
                for n in self._neighbors(region.position)
                if self.grid[n].owner == Owner.PLAYER
            ]
            if not targets:
                continue
            target = min(targets, key=lambda r: r.player_count)
            if region.enemy_count <= 0:
                continue
            commit = max(1, int(region.enemy_count * random.uniform(0.3, 0.6)))
            orders.append(AttackOrder(region.position, target.position, commit))
        return orders

    def resolve_battles(self, orders: Iterable[AttackOrder]) -> List[BattleResult]:
        results: List[BattleResult] = []
        for order in orders:
            source = self.grid[order.source]
            target = self.grid[order.target]
            if source.owner != Owner.ENEMY or target.owner != Owner.PLAYER:
                continue
            troops = min(order.troops, source.enemy_count)
            if troops <= 0:
                continue
            source.enemy_count -= troops
            defender_start = target.player_count
            result = self._battle(troops, defender_start)
            if result.winner == Owner.ENEMY:
                target.owner = Owner.ENEMY
                target.enemy_count = result.remaining
                target.player_count = 0
            else:
                target.player_count = result.remaining
            target.is_active = True
            results.append(
                BattleResult(
                    target=target.position,
                    winner=result.winner,
                    remaining=result.remaining,
                    attacker_losses=troops - (result.remaining if result.winner == Owner.ENEMY else 0),
                    defender_losses=defender_start - (result.remaining if result.winner == Owner.PLAYER else 0),
                )
            )
        self._refresh_frontlines()
        return results

    def _battle(self, attackers: int, defenders: int) -> BattleResult:
        if attackers == defenders:
            remaining = max(2, int(defenders * 0.1))
            return BattleResult(
                target=(-1, -1),
                winner=Owner.PLAYER,
                remaining=remaining,
                attacker_losses=attackers,
                defender_losses=defenders - remaining,
            )
        if attackers > defenders:
            loss = self._loss_formula(attackers, defenders)
            remaining = max(0, attackers - loss)
            return BattleResult(
                target=(-1, -1),
                winner=Owner.ENEMY,
                remaining=remaining,
                attacker_losses=loss,
                defender_losses=defenders,
            )
        loss = self._loss_formula(defenders, attackers)
        remaining = max(0, defenders - loss)
        return BattleResult(
            target=(-1, -1),
            winner=Owner.PLAYER,
            remaining=remaining,
            attacker_losses=attackers,
            defender_losses=loss,
        )

    def _loss_formula(self, larger: int, smaller: int) -> int:
        if smaller == 0:
            return 0
        return max(1, int(smaller / (larger / smaller)))

    def is_game_over(self) -> Optional[str]:
        enemy_total = sum(r.enemy_count for r in self.grid.values())
        player_total = sum(r.player_count for r in self.grid.values())
        center = (self.config.size // 2, self.config.size // 2)
        center_owner = self.grid[center].owner
        player_regions = [r for r in self.grid.values() if r.owner == Owner.PLAYER]
        if enemy_total == 0:
            return "KAZANDIN: Düşman askeri kalmadı."
        if player_total == 0:
            return "KAYBETTIN: Tüm askerlerin öldü."
        if center_owner != Owner.PLAYER:
            return "KAYBETTIN: Merkez düştü."
        if len(player_regions) < 4:
            return "KAYBETTIN: 4 ana bölge kaybedildi."
        return None

    def end_turn(self) -> None:
        self.turn += 1
        self._refresh_frontlines()

    def summary(self) -> str:
        lines = [f"Turn {self.turn}"]
        for y in range(self.config.size):
            row = []
            for x in range(self.config.size):
                region = self.grid[(x, y)]
                if region.owner == Owner.PLAYER:
                    row.append(f"P{region.player_count:02d}")
                elif region.owner == Owner.ENEMY:
                    row.append(f"E{region.enemy_count:02d}")
                else:
                    row.append("N--")
            lines.append(" ".join(row))
        return "\n".join(lines)
