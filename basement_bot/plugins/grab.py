import datetime
from random import randint

from discord.ext import commands
from sqlalchemy import Column, DateTime, Integer, String

from utils.database import DatabaseHandle
from utils.helpers import get_env_value, priv_response, tagged_response

db_handle = DatabaseHandle()

SEARCH_LIMIT = 50

COMMAND_PREFIX = get_env_value("COMMAND_PREFIX")


class Grab(db_handle.Base):
    __tablename__ = "grabs"

    pk = Column(Integer, primary_key=True)
    author_id = Column(String)
    channel = Column(String)
    message = Column(String)
    time = Column(DateTime, default=datetime.datetime.utcnow)


db_handle.create_all()


def setup(bot):
    bot.add_command(grab)
    bot.add_command(get_grabs)
    bot.add_command(random_grab)


@commands.command(
    name="grab",
    brief="Grab the last message from the mentioned user",
    description=(
        "Gets the last message of the mentioned user and saves it"
        " in the database for later retrieval."
    ),
    usage="[mentioned-user]",
    help=(
        "\nLimitations: The command will only look for a mentioned user."
        " Any additional plain text, other mentioned users, or @here/@everyone"
        " will be ignored."
    ),
)
async def grab(ctx):
    channel = str(ctx.message.channel.id)
    user_to_grab = ctx.message.mentions[0] if ctx.message.mentions else None

    if not user_to_grab:
        await priv_response(ctx, "You must tag a user to grab!")
        return

    if user_to_grab.bot:
        await priv_response(ctx, "Ain't gonna catch me slipping!")
        return

    grab_message = None
    async for message in ctx.channel.history(limit=SEARCH_LIMIT):
        if message.author == user_to_grab and not message.content.startswith(
            f"{COMMAND_PREFIX}grab"
        ):
            grab_message = message.content
            break

    if not grab_message:
        await priv_response(
            ctx, f"Could not find a recent essage from user {user_to_grab}"
        )

    db = db_handle.Session()

    try:
        if (
            db.query(Grab)
            .filter(
                Grab.author_id == str(user_to_grab.id),
                Grab.channel == channel,
                Grab.message == grab_message,
            )
            .count()
            != 0
        ):
            await priv_response(ctx, "That grab already exists!")
            return
        db.add(
            Grab(author_id=str(user_to_grab.id), channel=channel, message=grab_message,)
        )
        db.commit()
        await priv_response(ctx, f"Successfully saved: '*{grab_message}*'")
    except Exception:
        await priv_response(ctx, "I had an issue remembering that message!")


@commands.command(
    name="grabs",
    brief="Returns all grabbed messages of mentioned person",
    description="Returns all grabbed messages of mentioned person from the database.",
    usage="[mentioned-user]",
    help=(
        "\nLimitations: The command will only look for a mentioned user."
        " Any additional plain text, other mentioned users, or @here/@everyone"
        " will be ignored."
    ),
)
async def get_grabs(ctx):
    channel = str(ctx.message.channel.id)
    user_to_grab = ctx.message.mentions[0] if ctx.message.mentions else None

    if not user_to_grab:
        await priv_response(ctx, "You must tag a user to grab!")
        return

    if user_to_grab.bot:
        await priv_response(ctx, "Ain't gonna catch me slipping!")
        return

    db = db_handle.Session()

    try:
        grabs = db.query(Grab).filter(
            Grab.author_id == str(user_to_grab.id), Grab.channel == channel
        )
        if grabs:
            message = ""
            for grab_ in grabs[:-1]:
                message += f"'*{grab_.message}*', "
            if message:
                message += f"and '*{grabs[-1].message}*'"
            else:
                message = f"'*{grabs[-1].message}*'"
        else:
            message = f"No messages found for {user_to_grab}"
        await tagged_response(ctx, message)
    except Exception:
        return


@commands.command(
    name="grabr",
    brief="Returns a random grabbed message",
    description="Returns a random grabbed message of a random user or of a mentioned user from the database.",
    usage="[mentioned-user/blank]",
    help=(
        "\nLimitations: Any additional plain text, mentioned users, or @here/@everyone"
        " will be ignored."
    ),
)
async def random_grab(ctx):
    channel = str(ctx.message.channel.id)
    user_to_grab = ctx.message.mentions[0] if ctx.message.mentions else None

    if user_to_grab and user_to_grab.bot:
        await priv_response(ctx, "Ain't gonna catch me slipping!")
        return

    db = db_handle.Session()

    try:
        if user_to_grab:
            grabs = db.query(Grab).filter(
                Grab.author_id == str(user_to_grab.id), Grab.channel == channel
            )
        else:
            grabs = db.query(Grab).filter(Grab.channel == channel)

        if grabs:
            random_index = randint(0, grabs.count() - 1)
            message = f"'*{grabs[random_index].message}*'"
        else:
            await priv_response(
                f"No messages found for {user_to_grab or 'this channel'}"
            )
            return

        await tagged_response(ctx, message)
    except Exception:
        return