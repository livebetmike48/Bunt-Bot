"""
Bunt Alert trigger conditions:
  - Runner on 2nd base (regardless of 1st/3rd) is occupied
  - 0 outs
  - Inning is Top 9, Bottom 9, Top 10, or Bottom 10
  - The batting team is tied or losing (not winning)
"""

QUALIFYING_INNINGS = {("Top", 9), ("Bottom", 9), ("Top", 10), ("Bottom", 10)}


def is_bunt_situation(half: str, inning: int, outs: int, second_occupied: bool,
                       batting_score: int, fielding_score: int) -> bool:
    if (half, inning) not in QUALIFYING_INNINGS:
        return False
    if outs != 0:
        return False
    if not second_occupied:
        return False
    if batting_score > fielding_score:
        return False  # batting team is winning -- no bunt alert
    return True
