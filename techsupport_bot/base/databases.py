"""This file stores all of the postgres table declarations
All models can be used by any extension
"""

import datetime


def setup_models(bot):
    """A function to setup all of the postgres tables
    This is stored in bot.models variable

    Args:
        bot (TechSupportBot): The bot object to register the databases to
    """

    class DuckUser(bot.db.Model):
        """The postgres table for ducks
        Currently used in duck.py"""

        __tablename__ = "duckusers"

        pk = bot.db.Column(bot.db.Integer, primary_key=True, autoincrement=True)
        author_id = bot.db.Column(bot.db.String)
        guild_id = bot.db.Column(bot.db.String)
        befriend_count = bot.db.Column(bot.db.Integer, default=0)
        kill_count = bot.db.Column(bot.db.Integer, default=0)
        updated = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)
        speed_record = bot.db.Column(bot.db.Float, default=80.0)

    class Factoid(bot.db.Model):
        """The postgres table for factoids
        Currently used in factoid.py"""

        __tablename__ = "factoids"

        factoid_id = bot.db.Column(bot.db.Integer, primary_key=True)
        name = bot.db.Column(bot.db.String)
        guild = bot.db.Column(bot.db.String)
        message = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)
        embed_config = bot.db.Column(bot.db.String, default=None)
        hidden = bot.db.Column(bot.db.Boolean, default=False)
        alias = bot.db.Column(bot.db.String, default=None)

    class FactoidJob(bot.db.Model):
        """The postgres table for factoid loops
        Currently used in factoid.py"""

        __tablename__ = "factoid_jobs"

        job_id = bot.db.Column(bot.db.Integer, primary_key=True)
        factoid = bot.db.Column(
            bot.db.Integer, bot.db.ForeignKey("factoids.factoid_id")
        )
        channel = bot.db.Column(bot.db.String)
        cron = bot.db.Column(bot.db.String)

    class Grab(bot.db.Model):
        """The postgres table for grabs
        Currently used in grab.py"""

        __tablename__ = "grabs"

        pk = bot.db.Column(bot.db.Integer, primary_key=True)
        author_id = bot.db.Column(bot.db.String)
        channel = bot.db.Column(bot.db.String)
        guild = bot.db.Column(bot.db.String)
        message = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)
        nsfw = bot.db.Column(bot.db.Boolean, default=False)

    class IRCChannelMapping(bot.db.Model):
        """The postgres table for IRC->discord maps
        Currently used in relay.py"""

        __tablename__ = "ircchannelmap"
        map_id = bot.db.Column(bot.db.Integer, primary_key=True)
        guild_id = bot.db.Column(bot.db.String, default=None)
        discord_channel_id = bot.db.Column(bot.db.String, default=None)
        irc_channel_id = bot.db.Column(bot.db.String, default=None)

    class UserNote(bot.db.Model):
        """The postgres table for notes
        Currently used in who.py"""

        __tablename__ = "usernote"

        pk = bot.db.Column(bot.db.Integer, primary_key=True, autoincrement=True)
        user_id = bot.db.Column(bot.db.String)
        guild_id = bot.db.Column(bot.db.String)
        updated = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)
        author_id = bot.db.Column(bot.db.String)
        body = bot.db.Column(bot.db.String)

    class Warning(bot.db.Model):
        """The postgres table for warnings
        Currently used in protect.py and who.py"""

        __tablename__ = "warnings"
        pk = bot.db.Column(bot.db.Integer, primary_key=True)
        user_id = bot.db.Column(bot.db.String)
        guild_id = bot.db.Column(bot.db.String)
        reason = bot.db.Column(bot.db.String)
        time = bot.db.Column(bot.db.DateTime, default=datetime.datetime.utcnow)

    bot.models.DuckUser = DuckUser
    bot.models.Factoid = Factoid
    bot.models.FactoidJob = FactoidJob
    bot.models.Grab = Grab
    bot.models.IRCChannelMapping = IRCChannelMapping
    bot.models.UserNote = UserNote
    bot.models.Warning = Warning