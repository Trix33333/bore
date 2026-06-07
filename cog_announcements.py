"""
cogs/cog_logs.py — Logs de modération automatiques.

Fonctionnalités loggées :
- Arrivées / départs de membres
- Messages supprimés
- Messages modifiés
- Création / fermeture de tickets (géré dans cog_tickets)
- Bans / unbans
"""

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands

logger = logging.getLogger("bot.logs")

COLOR_JOIN    = discord.Color.from_rgb(88, 196, 120)
COLOR_LEAVE   = discord.Color.from_rgb(237, 100, 100)
COLOR_DELETE  = discord.Color.from_rgb(255, 80, 80)
COLOR_EDIT    = discord.Color.from_rgb(255, 200, 60)
COLOR_BAN     = discord.Color.from_rgb(180, 0, 0)
COLOR_UNBAN   = discord.Color.from_rgb(0, 180, 80)


class LogsCog(commands.Cog, name="Logs"):
    """Cog de journalisation des événements de modération."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self):
        return self.bot.db  # type: ignore

    async def _get_log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        """Retourne le salon de logs configuré pour le serveur."""
        config = self.db.get_guild_config(guild.id)
        if not config or not config["log_channel"]:
            return None
        channel = guild.get_channel(config["log_channel"])
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    async def _send_log(self, guild: discord.Guild, embed: discord.Embed) -> None:
        """Envoie un embed dans le salon de logs du serveur."""
        log_channel = await self._get_log_channel(guild)
        if log_channel:
            try:
                await log_channel.send(embed=embed)
            except discord.Forbidden:
                logger.warning(f"[{guild.name}] Permission refusée pour envoyer dans le salon de logs")

    # ── Membres ───────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Log quand un membre rejoint le serveur."""
        created_ts = int(member.created_at.timestamp())
        embed = discord.Embed(
            title="📥 Membre rejoint",
            description=f"{member.mention} ({member})",
            color=COLOR_JOIN,
            timestamp=datetime.now(tz=timezone.utc),
        )
        embed.add_field(name="🆔 ID", value=str(member.id), inline=True)
        embed.add_field(name="📅 Compte créé", value=f"<t:{created_ts}:R>", inline=True)
        embed.add_field(name="👥 Membres total", value=str(member.guild.member_count), inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        await self._send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """Log quand un membre quitte le serveur."""
        embed = discord.Embed(
            title="📤 Membre parti",
            description=f"{member} (ID: {member.id})",
            color=COLOR_LEAVE,
            timestamp=datetime.now(tz=timezone.utc),
        )
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        embed.add_field(
            name=f"🎭 Rôles ({len(roles)})",
            value=" ".join(roles[:10]) if roles else "Aucun",
            inline=False,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await self._send_log(member.guild, embed)

    # ── Messages ──────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        """Log quand un message est supprimé."""
        if not message.guild or message.author.bot:
            return
        if not message.content and not message.attachments:
            return  # Message vide ou inconnu (cache miss)

        embed = discord.Embed(
            title="🗑️ Message supprimé",
            color=COLOR_DELETE,
            timestamp=datetime.now(tz=timezone.utc),
        )
        embed.add_field(name="✍️ Auteur", value=f"{message.author.mention} ({message.author})", inline=True)
        embed.add_field(name="💬 Salon", value=message.channel.mention, inline=True)  # type: ignore

        # Troncature à 1024 car. (limite Discord)
        content = message.content[:1020] + "…" if len(message.content) > 1020 else message.content
        if content:
            embed.add_field(name="📝 Contenu", value=content or "*vide*", inline=False)

        if message.attachments:
            attach_list = "\n".join(f"• {a.filename}" for a in message.attachments)
            embed.add_field(name="📎 Fichiers", value=attach_list, inline=False)

        embed.set_footer(text=f"ID message: {message.id}")
        await self._send_log(message.guild, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """Log quand un message est modifié."""
        if not before.guild or before.author.bot:
            return
        if before.content == after.content:
            return  # Pas de changement de texte (embed ajouté, etc.)

        embed = discord.Embed(
            title="✏️ Message modifié",
            color=COLOR_EDIT,
            timestamp=datetime.now(tz=timezone.utc),
        )
        embed.add_field(name="✍️ Auteur", value=f"{before.author.mention} ({before.author})", inline=True)
        embed.add_field(name="💬 Salon", value=before.channel.mention, inline=True)  # type: ignore

        before_content = before.content[:500] + "…" if len(before.content) > 500 else before.content
        after_content  = after.content[:500] + "…"  if len(after.content) > 500  else after.content

        embed.add_field(name="📝 Avant", value=before_content or "*vide*", inline=False)
        embed.add_field(name="📝 Après", value=after_content or "*vide*", inline=False)
        embed.add_field(
            name="🔗 Lien",
            value=f"[Aller au message]({after.jump_url})",
            inline=False,
        )
        embed.set_footer(text=f"ID message: {before.id}")
        await self._send_log(before.guild, embed)

    # ── Bans ──────────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        """Log quand un membre est banni."""
        embed = discord.Embed(
            title="🔨 Membre banni",
            description=f"{user.mention} ({user})",
            color=COLOR_BAN,
            timestamp=datetime.now(tz=timezone.utc),
        )
        embed.add_field(name="🆔 ID", value=str(user.id), inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)
        await self._send_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User) -> None:
        """Log quand un membre est débanni."""
        embed = discord.Embed(
            title="✅ Membre débanni",
            description=f"{user.mention} ({user})",
            color=COLOR_UNBAN,
            timestamp=datetime.now(tz=timezone.utc),
        )
        embed.add_field(name="🆔 ID", value=str(user.id), inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)
        await self._send_log(guild, embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LogsCog(bot))
