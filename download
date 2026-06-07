"""
cogs/cog_welcome.py — Gestion des arrivées et départs de membres.

Fonctionnalités :
- on_member_join  → embed de bienvenue dans le salon configuré
- on_member_remove → embed d'au revoir dans le même salon
- Placeholders : {user}, {user_mention}, {server}, {member_count}
- Commande /welcome-setup pour configurer le message et le salon
"""

import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("bot.welcome")

# ── Couleurs des embeds ───────────────────────────────────────────────────────
COLOR_JOIN  = discord.Color.from_rgb(88, 196, 120)   # Vert
COLOR_LEAVE = discord.Color.from_rgb(237, 100, 100)  # Rouge


def resolve_placeholders(text: str, member: discord.Member) -> str:
    """Remplace les placeholders dans un message de bienvenue/au revoir."""
    return (
        text
        .replace("{user}", str(member))
        .replace("{user_mention}", member.mention)
        .replace("{username}", member.display_name)
        .replace("{server}", member.guild.name)
        .replace("{member_count}", str(member.guild.member_count))
    )


class WelcomeCog(commands.Cog, name="Bienvenue"):
    """Cog de gestion des arrivées et départs de membres."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self):
        return self.bot.db  # type: ignore

    # ── Événements ────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """Envoi d'un embed de bienvenue quand un membre rejoint."""
        config = self.db.get_guild_config(member.guild.id)
        if not config or not config["welcome_channel"]:
            return

        channel = member.guild.get_channel(config["welcome_channel"])
        if not isinstance(channel, discord.TextChannel):
            return

        message = resolve_placeholders(
            config["welcome_message"] or "Bienvenue {user_mention} sur **{server}** ! 🎉",
            member,
        )

        embed = discord.Embed(
            title="🎉 Nouveau membre !",
            description=message,
            color=COLOR_JOIN,
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Membre n°{member.guild.member_count}")

        try:
            await channel.send(embed=embed)
            logger.info(f"[{member.guild.name}] Bienvenue envoyée pour {member}")
        except discord.Forbidden:
            logger.warning(f"Permission refusée pour envoyer dans le salon bienvenue de {member.guild.name}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """Envoi d'un embed d'au revoir quand un membre quitte."""
        config = self.db.get_guild_config(member.guild.id)
        if not config or not config["welcome_channel"]:
            return

        channel = member.guild.get_channel(config["welcome_channel"])
        if not isinstance(channel, discord.TextChannel):
            return

        message = resolve_placeholders(
            config["goodbye_message"] or "Au revoir **{user}** ! Nous étions {member_count} membres.",
            member,
        )

        embed = discord.Embed(
            title="👋 Départ",
            description=message,
            color=COLOR_LEAVE,
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Il reste {member.guild.member_count} membres")

        try:
            await channel.send(embed=embed)
            logger.info(f"[{member.guild.name}] Au revoir envoyé pour {member}")
        except discord.Forbidden:
            logger.warning(f"Permission refusée pour l'au revoir dans {member.guild.name}")

    # ── Slash Commands ────────────────────────────────────────────────────────

    welcome_group = app_commands.Group(
        name="welcome",
        description="Configuration des messages de bienvenue/au revoir",
        default_permissions=discord.Permissions(administrator=True),
    )

    @welcome_group.command(name="set-channel", description="Définit le salon de bienvenue/au revoir")
    @app_commands.describe(channel="Salon où envoyer les messages")
    async def set_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        """Définit le salon de bienvenue."""
        self.db.upsert_guild_config(interaction.guild_id, welcome_channel=channel.id)
        embed = discord.Embed(
            description=f"✅ Salon de bienvenue défini sur {channel.mention}",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"[{interaction.guild}] Salon bienvenue → #{channel.name}")

    @welcome_group.command(name="set-join-message", description="Personnalise le message de bienvenue")
    @app_commands.describe(
        message="Message (placeholders : {user_mention}, {user}, {server}, {member_count})"
    )
    async def set_join_message(
        self,
        interaction: discord.Interaction,
        message: str,
    ) -> None:
        self.db.upsert_guild_config(interaction.guild_id, welcome_message=message)
        preview = resolve_placeholders(message, interaction.user)  # type: ignore
        embed = discord.Embed(
            title="✅ Message de bienvenue mis à jour",
            description=f"**Aperçu :**\n{preview}",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @welcome_group.command(name="set-leave-message", description="Personnalise le message d'au revoir")
    @app_commands.describe(
        message="Message (placeholders : {user}, {server}, {member_count})"
    )
    async def set_leave_message(
        self,
        interaction: discord.Interaction,
        message: str,
    ) -> None:
        self.db.upsert_guild_config(interaction.guild_id, goodbye_message=message)
        preview = resolve_placeholders(message, interaction.user)  # type: ignore
        embed = discord.Embed(
            title="✅ Message d'au revoir mis à jour",
            description=f"**Aperçu :**\n{preview}",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @welcome_group.command(name="test", description="Teste le message de bienvenue avec votre profil")
    async def test_welcome(self, interaction: discord.Interaction) -> None:
        """Simule un message de bienvenue pour tester la configuration."""
        config = self.db.get_guild_config(interaction.guild_id)
        msg = (config["welcome_message"] if config else None) or "Bienvenue {user_mention} sur **{server}** ! 🎉"
        preview = resolve_placeholders(msg, interaction.user)  # type: ignore

        embed = discord.Embed(
            title="🎉 Nouveau membre !",
            description=preview,
            color=COLOR_JOIN,
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"Aperçu du message de bienvenue")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(WelcomeCog(bot))
