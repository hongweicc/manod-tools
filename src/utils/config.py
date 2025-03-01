from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import yaml
from pathlib import Path
import asyncio
from loguru import logger


@dataclass
class SettingsConfig:
    THREADS: int
    ATTEMPTS: int
    ACCOUNTS_RANGE: Tuple[int, int]
    EXACT_ACCOUNTS_TO_USE: List[int]
    PAUSE_BETWEEN_ATTEMPTS: Tuple[int, int]
    PAUSE_BETWEEN_SWAPS: Tuple[int, int]
    RANDOM_PAUSE_BETWEEN_ACCOUNTS: Tuple[int, int]
    RANDOM_PAUSE_BETWEEN_ACTIONS: Tuple[int, int]
    BROWSER_PAUSE_MULTIPLIER: float
    RANDOM_INITIALIZATION_PAUSE: Tuple[int, int]

@dataclass
class FlowConfig:
    TASKS: List[str]
    NUMBER_OF_SWAPS: Tuple[int, int]
    PERCENT_OF_BALANCE_TO_SWAP: Tuple[int, int]


@dataclass
class AprioriConfig:
    AMOUNT_TO_STAKE: Tuple[float, float]


@dataclass
class MagmaConfig:
    AMOUNT_TO_STAKE: Tuple[float, float]


@dataclass
class KintsuConfig:
    AMOUNT_TO_STAKE: Tuple[float, float]


@dataclass
class BimaConfig:
    LEND: bool
    PERCENT_OF_BALANCE_TO_LEND: Tuple[int, int]


@dataclass
class WalletInfo:
    account_index: int
    private_key: str
    address: str
    balance: float
    transactions: int


@dataclass
class WalletsConfig:
    wallets: List[WalletInfo] = field(default_factory=list)


@dataclass
class GaszipConfig:
    NETWORKS_TO_REFUEL_FROM: List[str]
    AMOUNT_TO_REFUEL: Tuple[float, float]
    MINIMUM_BALANCE_TO_REFUEL: float
    WAIT_FOR_FUNDS_TO_ARRIVE: bool
    MAX_WAIT_TIME: int


@dataclass
class ShmonadConfig:
    PERCENT_OF_BALANCE_TO_SWAP: Tuple[int, int]
    BUY_AND_STAKE_SHMON: bool
    UNSTAKE_AND_SELL_SHMON: bool


@dataclass
class AccountableConfig:
    NFT_PER_ACCOUNT_LIMIT: int


@dataclass
class OrbiterConfig:
    AMOUNT_TO_BRIDGE: Tuple[float, float]
    BRIDGE_ALL: bool
    WAIT_FOR_FUNDS_TO_ARRIVE: bool
    MAX_WAIT_TIME: int


@dataclass
class DisperseConfig:
    MIN_BALANCE_FOR_DISPERSE: Tuple[float, float]


@dataclass
class LilchogstarsConfig:
    MAX_AMOUNT_FOR_EACH_ACCOUNT: Tuple[int, int]


@dataclass
class DemaskConfig:
    MAX_AMOUNT_FOR_EACH_ACCOUNT: Tuple[int, int]


@dataclass
class MonadkingConfig:
    MAX_AMOUNT_FOR_EACH_ACCOUNT: Tuple[int, int]


@dataclass
class MagicEdenConfig:
    NFT_CONTRACTS: List[str]


@dataclass
class Config:
    SETTINGS: SettingsConfig
    FLOW: FlowConfig
    APRIORI: AprioriConfig
    MAGMA: MagmaConfig
    KINTSU: KintsuConfig
    BIMA: BimaConfig
    GASZIP: GaszipConfig
    SHMONAD: ShmonadConfig
    ACCOUNTABLE: AccountableConfig
    ORBITER: OrbiterConfig
    DISPERSE: DisperseConfig
    LILCHOGSTARS: LilchogstarsConfig
    DEMASK: DemaskConfig
    MONADKING: MonadkingConfig
    MAGICEDEN: MagicEdenConfig
    WALLETS: WalletsConfig = field(default_factory=WalletsConfig)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @classmethod
    def load(cls, path: str = "config.yaml") -> "Config":
        """
        从 YAML 文件加载配置。

        Args:
            path: YAML 文件路径，默认为 "config.yaml"。

        Returns:
            配置对象实例。

        Raises:
            FileNotFoundError: 如果配置文件不存在。
            yaml.YAMLError: 如果 YAML 文件格式错误。
        """
        config_path = Path(path)
        if not config_path.exists():
            logger.error(f"Configuration file not found: {path}")
            raise FileNotFoundError(f"Configuration file not found: {path}")

        try:
            with config_path.open("r", encoding="utf-8") as file:
                data = yaml.safe_load(file) or {}  # 空文件返回空字典
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML file {path}: {e}")
            raise

        try:
            return cls(
                SETTINGS=_create_settings_config(data.get("SETTINGS", {})),
                FLOW=_create_flow_config(data.get("FLOW", {})),
                APRIORI=_create_apriori_config(data.get("APRIORI", {})),
                MAGMA=_create_magma_config(data.get("MAGMA", {})),
                KINTSU=_create_kintsu_config(data.get("KINTSU", {})),
                BIMA=_create_bima_config(data.get("BIMA", {})),
                GASZIP=_create_gaszip_config(data.get("GASZIP", {})),
                SHMONAD=_create_shmonad_config(data.get("SHMONAD", {})),
                ACCOUNTABLE=_create_accountable_config(data.get("ACCOUNTABLE", {})),
                ORBITER=_create_orbiter_config(data.get("ORBITER", {})),
                DISPERSE=_create_disperse_config(data.get("DISPERSE", {})),
                LILCHOGSTARS=_create_lilchogstars_config(data.get("LILCHOGSTARS", {})),
                DEMASK=_create_demask_config(data.get("DEMASK", {})),
                MONADKING=_create_monadking_config(data.get("MONADKING", {})),
                MAGICEDEN=_create_magiceden_config(data.get("MAGICEDEN", {})),
            )
        except KeyError as e:
            logger.error(f"Missing required configuration field: {e}")
            raise


def _create_settings_config(data: dict) -> SettingsConfig:
    return SettingsConfig(
        THREADS=data.get("THREADS", 1),
        ATTEMPTS=data.get("ATTEMPTS", 3),
        ACCOUNTS_RANGE=tuple(data.get("ACCOUNTS_RANGE", [0, 0])),
        EXACT_ACCOUNTS_TO_USE=data.get("EXACT_ACCOUNTS_TO_USE", []),
        PAUSE_BETWEEN_ATTEMPTS=tuple(data.get("PAUSE_BETWEEN_ATTEMPTS", [5, 10])),
        PAUSE_BETWEEN_SWAPS=tuple(data.get("PAUSE_BETWEEN_SWAPS", [5, 10])),
        RANDOM_PAUSE_BETWEEN_ACCOUNTS=tuple(data.get("RANDOM_PAUSE_BETWEEN_ACCOUNTS", [5, 15])),
        RANDOM_PAUSE_BETWEEN_ACTIONS=tuple(data.get("RANDOM_PAUSE_BETWEEN_ACTIONS", [1, 3])),
        BROWSER_PAUSE_MULTIPLIER=data.get("BROWSER_PAUSE_MULTIPLIER", 1.0),
        RANDOM_INITIALIZATION_PAUSE=tuple(data.get("RANDOM_INITIALIZATION_PAUSE", [5, 10])),
    )


def _create_flow_config(data: dict) -> FlowConfig:
    return FlowConfig(
        TASKS=data.get("TASKS", []),
        NUMBER_OF_SWAPS=tuple(data.get("NUMBER_OF_SWAPS", [1, 3])),
        PERCENT_OF_BALANCE_TO_SWAP=tuple(data.get("PERCENT_OF_BALANCE_TO_SWAP", [10, 50])),
    )


def _create_apriori_config(data: dict) -> AprioriConfig:
    return AprioriConfig(
        AMOUNT_TO_STAKE=tuple(data.get("AMOUNT_TO_STAKE", [0.1, 1.0])),
    )


def _create_magma_config(data: dict) -> MagmaConfig:
    return MagmaConfig(
        AMOUNT_TO_STAKE=tuple(data.get("AMOUNT_TO_STAKE", [0.1, 1.0])),
    )


def _create_kintsu_config(data: dict) -> KintsuConfig:
    return KintsuConfig(
        AMOUNT_TO_STAKE=tuple(data.get("AMOUNT_TO_STAKE", [0.1, 1.0])),
    )


def _create_bima_config(data: dict) -> BimaConfig:
    return BimaConfig(
        LEND=data.get("LEND", False),
        PERCENT_OF_BALANCE_TO_LEND=tuple(data.get("PERCENT_OF_BALANCE_TO_LEND", [10, 50])),
    )


def _create_gaszip_config(data: dict) -> GaszipConfig:
    return GaszipConfig(
        NETWORKS_TO_REFUEL_FROM=data.get("NETWORKS_TO_REFUEL_FROM", []),
        AMOUNT_TO_REFUEL=tuple(data.get("AMOUNT_TO_REFUEL", [0.01, 0.05])),
        MINIMUM_BALANCE_TO_REFUEL=data.get("MINIMUM_BALANCE_TO_REFUEL", 0.1),
        WAIT_FOR_FUNDS_TO_ARRIVE=data.get("WAIT_FOR_FUNDS_TO_ARRIVE", True),
        MAX_WAIT_TIME=data.get("MAX_WAIT_TIME", 300),
    )


def _create_shmonad_config(data: dict) -> ShmonadConfig:
    return ShmonadConfig(
        PERCENT_OF_BALANCE_TO_SWAP=tuple(data.get("PERCENT_OF_BALANCE_TO_SWAP", [10, 50])),
        BUY_AND_STAKE_SHMON=data.get("BUY_AND_STAKE_SHMON", False),
        UNSTAKE_AND_SELL_SHMON=data.get("UNSTAKE_AND_SELL_SHMON", False),
    )


def _create_accountable_config(data: dict) -> AccountableConfig:
    return AccountableConfig(
        NFT_PER_ACCOUNT_LIMIT=data.get("NFT_PER_ACCOUNT_LIMIT", 1),
    )


def _create_orbiter_config(data: dict) -> OrbiterConfig:
    return OrbiterConfig(
        AMOUNT_TO_BRIDGE=tuple(data.get("AMOUNT_TO_BRIDGE", [0.1, 0.5])),
        BRIDGE_ALL=data.get("BRIDGE_ALL", False),
        WAIT_FOR_FUNDS_TO_ARRIVE=data.get("WAIT_FOR_FUNDS_TO_ARRIVE", True),
        MAX_WAIT_TIME=data.get("MAX_WAIT_TIME", 300),
    )


def _create_disperse_config(data: dict) -> DisperseConfig:
    return DisperseConfig(
        MIN_BALANCE_FOR_DISPERSE=tuple(data.get("MIN_BALANCE_FOR_DISPERSE", [0.1, 0.5])),
    )


def _create_lilchogstars_config(data: dict) -> LilchogstarsConfig:
    return LilchogstarsConfig(
        MAX_AMOUNT_FOR_EACH_ACCOUNT=tuple(data.get("MAX_AMOUNT_FOR_EACH_ACCOUNT", [1, 5])),
    )


def _create_demask_config(data: dict) -> DemaskConfig:
    return DemaskConfig(
        MAX_AMOUNT_FOR_EACH_ACCOUNT=tuple(data.get("MAX_AMOUNT_FOR_EACH_ACCOUNT", [1, 5])),
    )


def _create_monadking_config(data: dict) -> MonadkingConfig:
    return MonadkingConfig(
        MAX_AMOUNT_FOR_EACH_ACCOUNT=tuple(data.get("MAX_AMOUNT_FOR_EACH_ACCOUNT", [1, 5])),
    )


def _create_magiceden_config(data: dict) -> MagicEdenConfig:
    return MagicEdenConfig(
        NFT_CONTRACTS=data.get("NFT_CONTRACTS", []),
    )


def get_config(path: str = "config.yaml") -> Config:
    """
    获取配置单例实例。

    Args:
        path: YAML 文件路径，默认为 "config.yaml"。

    Returns:
        配置对象实例。
    """
    if not hasattr(get_config, "_config"):
        get_config._config = Config.load(path)
    return get_config._config


if __name__ == "__main__":
    # 示例测试
    config = get_config()
    print(config.SETTINGS.THREADS)
    print(config.FLOW.TASKS)