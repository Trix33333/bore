"""
cogs/cog_announcements.py — Système d'annonces.

Fonctionnalités :
- /announce <message> [ping_role] → Envoie un embed stylisé dans le salon annonces configuré
- /announce-setup channel → Configure le salon d'annonces
"""

import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("bot.announcements")

EMBED_COLOR = discord.Color.from_rgb(255, 165, 0)  # Orange gaming


class AnnouncementsCog(commands.Cog, name="Annonces"):
    """Cog de gestion des annonces du serveur."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self):
        return self.bot.db  # type: ignore

    # ── Commandes d'annonce ───────────────────────────────────────────────────

    @app_commands.command(
        name="announce",
        description="Envoie une annonce dans le salon dédié",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        message="Le contenu de l'annonce (supporte le markdown Discord)",
        ping_role="Rôle à mentionner avec l'annonce (optionnel)",
        titre="Titre de l'embed (optionnel, défaut : 📢 Annonce)",
        couleur="Couleur hex de l'embed (ex: ff5733, optionnel)",
    )
    async def announce(
        self,
        interaction: discord.Interaction,
        message: str,
        ping_role: discord.Role | None = None,
        titre: str = "📢 Annonce",
        couleur: str | None = None,
    ) -> None:
        """Envoie une annonce formatée dans le salon configuré."""
        await interaction.response.defer(ephemeral=True)

        config = self.db.get_guild_config(interaction.guild_id)
        if not config or not config["announce_channel"]:
            await interaction.followup.send(
                "❌ Aucun salon d'annonces configuré. Utilisez `/announce-setup channel`.",
                ephemeral=True,
            )
            return

        channel = interaction.guild.get_channel(config["announce_channel"])
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send(
                "❌ Le salon d'annonces configuré est introuvable ou invalide.",
                ephemeral=True,
            )
            return

        # Vérification permission staff ou gestion du serveur
        member = interaction.user
        if not (
            member.guild_permissions.manage_guild  # type: ignore
            or (config["staff_role"] and any(r.id == config["staff_role"] for r in member.roles))  # type: ignore
        ):
            await interaction.followup.send("❌ Permission insuffisante.", ephemeral=True)
            return

        # Couleur personnalisée
        embed_color = EMBED_COLOR
        if couleur:
            try:
                embed_color = discord.Color(int(couleur.lstrip("#"), 16))
            except ValueError:
                pass  # On garde la couleur par défaut si invalide

        # Construction de l'embed
        embed = discord.Embed(
            title=titre,
            description=message,
            color=embed_color,
            timestamp=datetime.utcnow(),
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url,
        )
        embed.set_footer(
            text=interaction.guild.name,
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None,
        )

        # Mention du rôle si précisé
        content = ping_role.mention if ping_role else None

        try:
            await channel.send(content=content, embed=embed)
            logger.info(
                f"[{interaction.guild}] Annonce envoyée par {interaction.user} dans #{channel.name}"
            )
            await interaction.followup.send(
                f"✅ Annonce envoyée dans {channel.mention} !", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                f"❌ Je n'ai pas la permission d'écrire dans {channel.mention}.", ephemeral=True
            )

    # ── Configuration ─────────────────────────────────────────────────────────

    announce_setup_group = app_commands.Group(
        name="announce-setup",
        description="Configuration du système d'annonces",
        default_permissions=discord.Permissions(administrator=True),
    )

    @announce_setup_group.command(
        name="channel",
        description="Définit le salon des annonces",
    )
    @app_commands.describe(channel="Salon où envoyer les annonces")
    async def set_announce_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        self.db.upsert_guild_config(interaction.guild_id, announce_channel=channel.id)
        embed = discord.Embed(
            description=f"✅ Salon d'annonces défini sur {channel.mention}",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"[{interaction.guild}] Salon annonces → #{channel.name}")

    @announce_setup_group.command(
        name="info",
        description="Affiche la configuration actuelle des annonces",
    )
    async def announce_info(self, interaction: discord.Interaction) -> None:
        config = self.db.get_guild_config(interaction.guild_id)

        announce_channel = "Non configuré"
        if config and config["announce_channel"]:
            ch = interaction.guild.get_channel(config["announce_channel"])
            announce_channel = ch.mention if ch else "❌ Salon introuvable"

        staff_role = "Non configuré"
        if config and config["staff_role"]:
            role = interaction.guild.get_role(config["staff_role"])
            staff_role = role.mention if role else "❌ Rôle introuvable"

        embed = discord.Embed(
            title="⚙️ Configuration des annonces",
            color=EMBED_COLOR,
        )
        embed.add_field(name="📢 Salon", value=announce_channel, inline=True)
        embed.add_field(name="🛡️ Rôle staff", value=staff_role, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AnnouncementsCog(bot))
