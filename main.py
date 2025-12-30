from __future__ import annotations

import random
from typing import Dict, Tuple

from signalgame import Game, GameConfig


def autoplayer(game: Game) -> Dict[Tuple[int, int], int]:
    deployments: Dict[Tuple[int, int], int] = {}
    candidate_positions = [
        pos
        for pos, region in game.grid.items()
        if region.owner == game.grid[pos].owner and game._player_can_deploy(pos)
    ]
    random.shuffle(candidate_positions)
    remaining = game.config.player_reinforcements
    for pos in candidate_positions:
        if remaining <= 0:
            break
        commit = random.randint(1, remaining)
        deployments[pos] = deployments.get(pos, 0) + commit
        remaining -= commit
    return deployments


def run_demo(turns: int = 10, seed: int | None = 42) -> None:
    config = GameConfig(seed=seed)
    game = Game(config)
    for _ in range(turns):
        print(game.summary())
        print("\nİstihbarat:")
        for report in game.intel_report():
            print(f"- {report.region}: {report.signal}")
        deployments = autoplayer(game)
        game.apply_player_deployment(deployments)
        orders = game.enemy_orders()
        game.resolve_battles(orders)
        outcome = game.is_game_over()
        if outcome:
            print(outcome)
            break
        game.end_turn()
        print("\n---\n")


if __name__ == "__main__":
    run_demo()
