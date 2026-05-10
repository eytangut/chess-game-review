"""Tactical pattern detection using python-chess board state."""

import chess


# ─────────────────────────── Piece value helpers ──────────────────────────────

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}


def _pv(piece_type):
    return PIECE_VALUES.get(piece_type, 0)


# ─────────────────────────── Piece tactics ────────────────────────────────────

def detect_fork(board, move):
    """
    Detect if `move` creates a fork (one piece attacks 2+ enemy pieces).

    Returns True if the moving piece attacks two or more enemy pieces after the move.
    """
    b = board.copy()
    b.push(move)

    attacker_sq = move.to_square
    attacker = b.piece_at(attacker_sq)
    if attacker is None:
        return False

    attacker_color = attacker.color
    opponent_color = not attacker_color

    # Find squares attacked by the moved piece
    attacked_squares = b.attacks(attacker_sq)

    # Count valuable enemy pieces attacked (exclude pawns from fork targets for quality)
    targets = []
    for sq in attacked_squares:
        piece = b.piece_at(sq)
        if piece and piece.color == opponent_color:
            targets.append(piece.piece_type)

    # A fork requires attacking 2+ pieces; at least one should be valuable
    if len(targets) >= 2:
        valuable = [pt for pt in targets if pt != chess.PAWN or len(targets) > 2]
        return len(valuable) >= 2

    return False


def detect_pin(board, move):
    """
    Detect if `move` creates a pin (a piece is pinned to the king or a higher-value piece).

    Returns True if the opponent has a piece pinned after the move.
    """
    b = board.copy()
    b.push(move)

    # After the move it's the opponent's turn; check if any of their pieces are pinned
    opponent_color = b.turn  # it's now opponent's turn
    king_sq = b.king(opponent_color)
    if king_sq is None:
        return False

    for sq in chess.SQUARES:
        piece = b.piece_at(sq)
        if piece and piece.color == opponent_color and piece.piece_type != chess.KING:
            if b.is_pinned(opponent_color, sq):
                return True

    return False


def detect_skewer(board, move):
    """
    Detect if `move` creates a skewer (high-value piece forced to move, exposing lower-value behind).
    """
    b = board.copy()
    b.push(move)

    attacker_sq = move.to_square
    attacker = b.piece_at(attacker_sq)
    if attacker is None:
        return False

    # Skewers are created by sliding pieces
    if attacker.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return False

    opponent_color = not attacker.color
    rays = list(b.attacks(attacker_sq))

    for sq in rays:
        front_piece = b.piece_at(sq)
        if front_piece and front_piece.color == opponent_color:
            # Look for a less valuable piece behind it along the same ray
            direction = _ray_direction(attacker_sq, sq)
            if direction is None:
                continue
            behind_sq = sq + direction
            while 0 <= behind_sq <= 63:
                behind_piece = b.piece_at(behind_sq)
                if behind_piece:
                    if (behind_piece.color == opponent_color and
                            _pv(front_piece.piece_type) > _pv(behind_piece.piece_type)):
                        return True
                    break
                # Validate we stay on the same file/rank/diagonal
                if not _same_ray(attacker_sq, sq, behind_sq):
                    break
                behind_sq += direction

    return False


def _ray_direction(from_sq, to_sq):
    """Return the rank/file delta direction from from_sq toward to_sq."""
    from_rank, from_file = divmod(from_sq, 8)
    to_rank, to_file = divmod(to_sq, 8)
    dr = (to_rank - from_rank)
    df = (to_file - from_file)
    # Normalize to unit direction
    if dr != 0:
        dr = dr // abs(dr)
    if df != 0:
        df = df // abs(df)
    return dr * 8 + df


def _same_ray(origin, waypoint, target):
    """Check if target is on the same ray from origin through waypoint."""
    o_rank, o_file = divmod(origin, 8)
    w_rank, w_file = divmod(waypoint, 8)
    t_rank, t_file = divmod(target, 8)
    # Direction from origin to waypoint
    dr1 = w_rank - o_rank
    df1 = w_file - o_file
    # Direction from origin to target
    dr2 = t_rank - o_rank
    df2 = t_file - o_file
    if dr1 == 0 and df1 == 0:
        return False
    if dr1 == 0:
        return dr2 == 0 and (df2 * df1 > 0)
    if df1 == 0:
        return df2 == 0 and (dr2 * dr1 > 0)
    # Diagonal
    if abs(dr1) != abs(df1):
        return False
    return (dr2 * df1 == df2 * dr1) and (dr2 * dr1 >= 0)


def detect_discovered_attack(board, move):
    """
    Detect if `move` reveals an attack from a piece behind the moving piece.

    Returns True if a sliding piece's line of attack is unveiled by the move.
    """
    b_before = board.copy()
    b_after = board.copy()
    b_after.push(move)

    moving_color = board.turn
    opponent_color = not moving_color

    # Look for attacks gained on opponent's pieces after the move
    for sq in chess.SQUARES:
        target = b_after.piece_at(sq)
        if not target or target.color != opponent_color:
            continue
        # Was this square already attacked before the move?
        if b_before.is_attacked_by(moving_color, sq):
            continue
        # Is it attacked now?
        if b_after.is_attacked_by(moving_color, sq):
            # The moved piece itself might be the attacker, check for other attackers
            attackers_after = b_after.attackers(moving_color, sq)
            if move.to_square in attackers_after:
                # Moving piece attacks it - filter
                others = attackers_after - chess.SquareSet([move.to_square])
                if others:
                    return True
            else:
                return True

    return False


def detect_double_check(board, move):
    """
    Detect if `move` delivers a double check (two pieces check the king simultaneously).
    """
    b = board.copy()
    b.push(move)
    if not b.is_check():
        return False
    # Double check: king is in check from two pieces
    checkers = b.checkers()
    return len(list(checkers)) >= 2


def detect_overloaded_piece(board):
    """
    Detect if any piece is overloaded (defending two or more pieces simultaneously).

    Returns list of (square, piece) tuples for overloaded pieces.
    """
    overloaded = []
    for color in [chess.WHITE, chess.BLACK]:
        opponent = not color
        # Find all pieces of `color`
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if not piece or piece.color != color:
                continue
            if piece.piece_type == chess.KING:
                continue
            # Count how many own pieces this piece defends that are attacked
            defended_and_attacked = []
            for def_sq in chess.SQUARES:
                defended = board.piece_at(def_sq)
                if not defended or defended.color != color or def_sq == sq:
                    continue
                if sq in board.attackers(color, def_sq) and board.is_attacked_by(opponent, def_sq):
                    defended_and_attacked.append(def_sq)
            if len(defended_and_attacked) >= 2:
                overloaded.append((sq, piece))

    return overloaded


def detect_hanging_piece(board):
    """
    Detect undefended attacked pieces.

    Returns list of (square, piece) tuples for hanging pieces.
    """
    hanging = []
    for color in [chess.WHITE, chess.BLACK]:
        opponent = not color
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if not piece or piece.color != color:
                continue
            if piece.piece_type == chess.KING:
                continue
            # Attacked by opponent and not defended
            if board.is_attacked_by(opponent, sq) and not board.is_attacked_by(color, sq):
                hanging.append((sq, piece))

    return hanging


def detect_trapped_piece(board, piece_square):
    """
    Detect if the piece at `piece_square` has no safe squares to move to.

    Returns True if piece is trapped.
    """
    piece = board.piece_at(piece_square)
    if piece is None:
        return False

    opponent_color = not piece.color
    # Find all legal moves for this piece
    legal_destinations = []
    for move in board.legal_moves:
        if move.from_square == piece_square:
            legal_destinations.append(move.to_square)

    if not legal_destinations:
        return True  # No moves at all

    # Check if all destinations are attacked by opponent
    b = board.copy()
    # Temporarily remove the piece to find attacks
    safe_squares = []
    for dest in legal_destinations:
        b2 = board.copy()
        b2.push(chess.Move(piece_square, dest))
        if not b2.is_attacked_by(opponent_color, dest):
            safe_squares.append(dest)

    return len(safe_squares) == 0


# ─────────────────────────── King safety ─────────────────────────────────────

def detect_back_rank_weakness(board, color):
    """
    Detect back rank mate threat: king on back rank with no escape squares behind own pawns.
    """
    king_sq = board.king(color)
    if king_sq is None:
        return False

    back_rank = 0 if color == chess.WHITE else 7
    king_rank = chess.square_rank(king_sq)
    if king_rank != back_rank:
        return False

    # Check if the back rank is blocked by own pawns
    king_file = chess.square_file(king_sq)
    forward_dir = 1 if color == chess.WHITE else -1
    escape_rank = king_rank + forward_dir

    if escape_rank < 0 or escape_rank > 7:
        return False

    # Check adjacent squares on the escape rank
    blocked = 0
    for df in [-1, 0, 1]:
        ef = king_file + df
        if 0 <= ef <= 7:
            escape_sq = chess.square(ef, escape_rank)
            piece = board.piece_at(escape_sq)
            if piece and piece.color == color and piece.piece_type == chess.PAWN:
                blocked += 1

    # Also check if opponent's rook/queen can get to the back rank
    opponent = not color
    back_rank_attacked = any(
        board.is_attacked_by(opponent, chess.square(f, back_rank))
        for f in range(8)
    )

    return blocked >= 2 and back_rank_attacked


def detect_weak_king_shelter(board, color):
    """
    Detect missing pawn cover near the king (weak king shelter after castling).
    """
    king_sq = board.king(color)
    if king_sq is None:
        return False

    king_file = chess.square_file(king_sq)
    king_rank = chess.square_rank(king_sq)
    forward_dir = 1 if color == chess.WHITE else -1

    missing_pawns = 0
    for df in [-1, 0, 1]:
        f = king_file + df
        if 0 <= f <= 7:
            shelter_sq = chess.square(f, king_rank + forward_dir) if 0 <= king_rank + forward_dir <= 7 else None
            if shelter_sq is not None:
                piece = board.piece_at(shelter_sq)
                if not piece or piece.piece_type != chess.PAWN or piece.color != color:
                    missing_pawns += 1

    return missing_pawns >= 2


def detect_king_in_center(board, color, move_number):
    """
    Detect if a king has failed to castle by move 15.
    """
    if move_number <= 15:
        king_sq = board.king(color)
        if king_sq is None:
            return False
        king_file = chess.square_file(king_sq)
        # King in center files (c, d, e, f = files 2-5)
        return 2 <= king_file <= 5
    return False


# ─────────────────────────── Pawn structure ──────────────────────────────────

def detect_isolated_pawn(board, color):
    """
    Detect isolated pawns (no friendly pawns on adjacent files).

    Returns list of squares with isolated pawns.
    """
    isolated = []
    pawn_files = set()
    for sq in board.pieces(chess.PAWN, color):
        pawn_files.add(chess.square_file(sq))

    for sq in board.pieces(chess.PAWN, color):
        f = chess.square_file(sq)
        if (f - 1) not in pawn_files and (f + 1) not in pawn_files:
            isolated.append(sq)

    return isolated


def detect_doubled_pawns(board, color):
    """
    Detect doubled pawns (two pawns on the same file).

    Returns list of (file, squares) tuples.
    """
    from collections import defaultdict
    file_pawns = defaultdict(list)
    for sq in board.pieces(chess.PAWN, color):
        file_pawns[chess.square_file(sq)].append(sq)

    return [(f, sqs) for f, sqs in file_pawns.items() if len(sqs) >= 2]


def detect_passed_pawn(board, color):
    """
    Detect passed pawns (no enemy pawns can stop them from promoting).

    Returns list of squares with passed pawns.
    """
    passed = []
    opponent = not color

    for sq in board.pieces(chess.PAWN, color):
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        is_passed = True

        # Direction of pawn advance
        if color == chess.WHITE:
            ranks_ahead = range(r + 1, 8)
        else:
            ranks_ahead = range(r - 1, -1, -1)

        for ahead_rank in ranks_ahead:
            for df in [-1, 0, 1]:
                check_f = f + df
                if 0 <= check_f <= 7:
                    check_sq = chess.square(check_f, ahead_rank)
                    piece = board.piece_at(check_sq)
                    if piece and piece.piece_type == chess.PAWN and piece.color == opponent:
                        is_passed = False
                        break
            if not is_passed:
                break

        if is_passed:
            passed.append(sq)

    return passed


def detect_pawn_islands(board, color):
    """
    Count pawn islands (groups of connected pawns).

    Returns the number of pawn islands.
    """
    pawn_files = sorted(set(chess.square_file(sq) for sq in board.pieces(chess.PAWN, color)))
    if not pawn_files:
        return 0

    islands = 1
    for i in range(1, len(pawn_files)):
        if pawn_files[i] > pawn_files[i - 1] + 1:
            islands += 1

    return islands


def detect_connected_passed_pawns(board, color):
    """
    Detect connected passed pawns (two or more passed pawns on adjacent files).

    Returns list of squares.
    """
    passed = detect_passed_pawn(board, color)
    if len(passed) < 2:
        return []

    passed_files = {chess.square_file(sq): sq for sq in passed}
    connected = set()

    for f, sq in passed_files.items():
        if f + 1 in passed_files or f - 1 in passed_files:
            connected.add(sq)

    return list(connected)


# ─────────────────────────── Strategic patterns ──────────────────────────────

def detect_open_file_rook(board, color):
    """
    Detect rooks on open or half-open files.

    Returns list of (square, is_fully_open) tuples.
    """
    result = []
    opponent = not color

    for sq in board.pieces(chess.ROOK, color):
        f = chess.square_file(sq)
        # Check if file has no pawns of either color (open) or only enemy pawns (half-open)
        own_pawn_on_file = any(
            chess.square_file(p) == f for p in board.pieces(chess.PAWN, color)
        )
        if own_pawn_on_file:
            continue

        enemy_pawn_on_file = any(
            chess.square_file(p) == f for p in board.pieces(chess.PAWN, opponent)
        )
        result.append((sq, not enemy_pawn_on_file))  # (square, is_fully_open)

    return result


def detect_rook_seventh_rank(board, color):
    """
    Detect rooks on the 7th rank (2nd rank from opponent's perspective).

    Returns list of squares.
    """
    seventh_rank = 6 if color == chess.WHITE else 1
    result = []

    for sq in board.pieces(chess.ROOK, color):
        if chess.square_rank(sq) == seventh_rank:
            result.append(sq)

    return result


def detect_outpost_knight(board, color):
    """
    Detect knights on outpost squares (5th/6th rank, can't be chased by enemy pawns).

    Returns list of squares with outpost knights.
    """
    opponent = not color
    outpost_ranks = [4, 5] if color == chess.WHITE else [2, 3]
    result = []

    for sq in board.pieces(chess.KNIGHT, color):
        rank = chess.square_rank(sq)
        if rank not in outpost_ranks:
            continue

        f = chess.square_file(sq)
        # Check if enemy pawns can attack this square
        can_be_chased = False
        # Enemy pawns attack diagonally: black pawns attack downward (rank-1 from black's perspective)
        # A black pawn on rank r attacks squares on rank r-1; a white pawn on rank r attacks r+1
        # For a white knight on rank r, we check for enemy (black) pawns on rank r+1 that could attack it
        # For a black knight on rank r, we check for enemy (white) pawns on rank r-1
        pawn_attack_ranks = [rank + 1] if color == chess.WHITE else [rank - 1]
        for pr in pawn_attack_ranks:
            if 0 <= pr <= 7:
                for df in [-1, 1]:
                    pf = f + df
                    if 0 <= pf <= 7:
                        pawn_sq = chess.square(pf, pr)
                        piece = board.piece_at(pawn_sq)
                        if piece and piece.piece_type == chess.PAWN and piece.color == opponent:
                            can_be_chased = True
                            break

        if not can_be_chased:
            result.append(sq)

    return result


def detect_bad_bishop(board, color):
    """
    Detect bad bishops (bishop with all own pawns on the same color squares as the bishop).

    Returns list of (square, bishop) for bad bishops.
    """
    result = []

    for sq in board.pieces(chess.BISHOP, color):
        # Determine bishop's square color (light or dark)
        bishop_on_light = (chess.square_rank(sq) + chess.square_file(sq)) % 2 == 0

        own_pawns = list(board.pieces(chess.PAWN, color))
        if not own_pawns:
            continue

        # Check how many own pawns are on the same color as bishop
        pawns_same_color = sum(
            1 for p in own_pawns
            if ((chess.square_rank(p) + chess.square_file(p)) % 2 == 0) == bishop_on_light
        )

        # Bad bishop: majority of pawns on same color as bishop
        if pawns_same_color >= len(own_pawns) * 0.7 and len(own_pawns) >= 3:
            result.append(sq)

    return result


def detect_bishop_pair(board, color):
    """
    Detect if `color` has the bishop pair.

    Returns True if both bishops are present.
    """
    bishops = list(board.pieces(chess.BISHOP, color))
    if len(bishops) < 2:
        return False

    # Check they are on different colored squares
    colors = set(
        (chess.square_rank(sq) + chess.square_file(sq)) % 2
        for sq in bishops
    )
    return len(colors) == 2


# ─────────────────────────── Main analysis function ──────────────────────────

def analyze_position_tactics(board, move=None):
    """
    Analyze a board position for tactical patterns.

    Args:
        board: chess.Board (position BEFORE the move)
        move: chess.Move being played (optional)

    Returns:
        List of {pattern, description, severity} dicts.
        severity: "high" | "medium" | "low"
    """
    patterns = []
    color = board.turn  # color about to move

    if move is not None:
        # Move-based tactics
        if detect_fork(board, move):
            patterns.append({
                "pattern": "fork",
                "description": "Fork: the moved piece attacks two or more enemy pieces.",
                "severity": "high",
            })
        if detect_pin(board, move):
            patterns.append({
                "pattern": "pin",
                "description": "Pin: an enemy piece is pinned to a more valuable piece or king.",
                "severity": "high",
            })
        if detect_skewer(board, move):
            patterns.append({
                "pattern": "skewer",
                "description": "Skewer: a high-value enemy piece is attacked and forced to reveal a less valuable piece behind it.",
                "severity": "high",
            })
        if detect_discovered_attack(board, move):
            patterns.append({
                "pattern": "discovered_attack",
                "description": "Discovered attack: moving a piece reveals an attack from a piece behind it.",
                "severity": "medium",
            })
        if detect_double_check(board, move):
            patterns.append({
                "pattern": "double_check",
                "description": "Double check: two pieces give check simultaneously.",
                "severity": "high",
            })

    # Position-based tactics
    hanging = detect_hanging_piece(board)
    if hanging:
        pieces_str = ", ".join(chess.piece_name(p.piece_type).title() for _, p in hanging[:3])
        patterns.append({
            "pattern": "hanging_piece",
            "description": f"Hanging piece(s): {pieces_str} is/are undefended and attacked.",
            "severity": "high",
        })

    overloaded = detect_overloaded_piece(board)
    if overloaded:
        patterns.append({
            "pattern": "overloaded_piece",
            "description": "Overloaded piece: a piece is defending two or more targets simultaneously.",
            "severity": "medium",
        })

    # King safety
    for c in [chess.WHITE, chess.BLACK]:
        c_name = "White" if c == chess.WHITE else "Black"
        if detect_back_rank_weakness(board, c):
            patterns.append({
                "pattern": "back_rank_weakness",
                "description": f"{c_name} has a back-rank weakness.",
                "severity": "high",
            })
        # Only check king shelter when king has castled (not on e-file)
        king_sq = board.king(c)
        if king_sq is not None and chess.square_file(king_sq) not in (3, 4):
            if detect_weak_king_shelter(board, c):
                patterns.append({
                    "pattern": "weak_king_shelter",
                    "description": f"{c_name}'s king has weak pawn shelter.",
                    "severity": "medium",
                })

    # Pawn structure
    for c in [chess.WHITE, chess.BLACK]:
        c_name = "White" if c == chess.WHITE else "Black"
        passed = detect_passed_pawn(board, c)
        if passed:
            patterns.append({
                "pattern": "passed_pawn",
                "description": f"{c_name} has {len(passed)} passed pawn(s).",
                "severity": "medium",
            })
        isolated = detect_isolated_pawn(board, c)
        if isolated:
            patterns.append({
                "pattern": "isolated_pawn",
                "description": f"{c_name} has {len(isolated)} isolated pawn(s).",
                "severity": "low",
            })

    # Strategic
    for c in [chess.WHITE, chess.BLACK]:
        c_name = "White" if c == chess.WHITE else "Black"
        rooks_7th = detect_rook_seventh_rank(board, c)
        if rooks_7th:
            patterns.append({
                "pattern": "rook_seventh_rank",
                "description": f"{c_name} has a rook on the 7th rank.",
                "severity": "medium",
            })
        outpost = detect_outpost_knight(board, c)
        if outpost:
            patterns.append({
                "pattern": "outpost_knight",
                "description": f"{c_name} has a knight on an outpost square.",
                "severity": "low",
            })

    return patterns
