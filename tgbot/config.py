from dataclasses import dataclass

from environs import Env


@dataclass
class TgBot:
    """
    Creates the TgBot object from environment variables.
    """

    token: str
    admin_ids: list[int]
    use_redis: bool

    @staticmethod
    def from_env(env: Env, filtered: bool = False):
        """
        Creates the TgBot object from environment variables.
        """
        token_field_name = "BOT_TOKEN_FILTERED" if filtered else "BOT_TOKEN"
        admins_filed_name = "ADMINS_FILTERED" if filtered else "ADMINS"

        token = env.str(token_field_name)
        admin_ids = env.list(admins_filed_name, subcast=int)
        use_redis = env.bool("USE_REDIS")

        return TgBot(token=token, admin_ids=admin_ids, use_redis=use_redis)


@dataclass
class Config:
    """
    The main configuration class that integrates all the other configuration classes.

    This class holds the other configuration classes, providing a centralized point of access for all settings.

    Attributes
    ----------
    tg_bot : TgBot
        Holds the settings related to the Telegram Bot.
    misc : Miscellaneous
        Holds the values for miscellaneous settings.
    db : Optional[DbConfig]
        Holds the settings specific to the database (default is None).
    redis : Optional[RedisConfig]
        Holds the settings specific to Redis (default is None).
    """

    tg_bot: TgBot
    tg_bot_filtered: TgBot


def load_config(path: str = None) -> Config:
    """
    This function takes an optional file path as input and returns a Config object.
    :param path: The path of env file from where to load the configuration variables.
    It reads environment variables from a .env file if provided, else from the process environment.
    :return: Config object with attributes set as per environment variables.
    """

    # Create an Env object.
    # The Env object will be used to read environment variables.
    env = Env()
    env.read_env(path)

    return Config(
        tg_bot=TgBot.from_env(env),
        tg_bot_filtered=TgBot.from_env(env, filtered=True),
    )
