"""游戏A引擎 - 自定义异常类"""


class GameAError(Exception):
    """游戏A的基础异常类"""
    pass


class InvalidNumberError(GameAError):
    """报出的数字不合法（不在1-25范围内）"""
    def __init__(self, number: int, message: str = None):
        self.number = number
        super().__init__(message or f"数字 {number} 不在合法范围(1-25)内")


class NumberAlreadyCalledError(GameAError):
    """报出的数字已经被报过"""
    def __init__(self, number: int, message: str = None):
        self.number = number
        super().__init__(message or f"数字 {number} 已经被报过了")


class GameAlreadyFinishedError(GameAError):
    """游戏已经结束，不能再执行操作"""
    def __init__(self, message: str = None):
        super().__init__(message or "游戏已经结束")


class NotYourTurnError(GameAError):
    """不是当前玩家的回合"""
    def __init__(self, player_id: str, current_player: str, message: str = None):
        self.player_id = player_id
        self.current_player = current_player
        super().__init__(message or f"不是玩家 {player_id} 的回合，当前是 {current_player} 的回合")


class InvalidPlayerError(GameAError):
    """无效的玩家ID"""
    def __init__(self, player_id: str, message: str = None):
        self.player_id = player_id
        super().__init__(message or f"无效的玩家ID: {player_id}")
