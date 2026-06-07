"""
cogs/cog_utils.py — Commandes utilitaires communes.

Fonctionnalités :
- /ping          → Latence du bot
- /serverinfo    → Informations sur le serveur
- /userinfo      → Informations sur un utilisateur
- /clear <n>     → Suppression de messages (max 100)
- /avatar        → Affiche l'avatar d'un utilisateur
- /setup         → Configuration centralisée du bot (admin)
"""

import logging
import platform
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("bot.utils")

# ── Couleurs embed ────────────────────────────────────────────────────────────
COLOR_INFO  = discord.Color.from_rgb(100, 149, 237)
COLOR_OK    = discord.Color.green()
COLOR_WARN  = discord.Color.orange()


class UtilsCog(commands.Cog, name="Utilitaires"):
    """Cog des commandes utilitaires générales."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self):
        return self.bot.db  # type: ignore

    # ── /ping ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="ping", description="Affiche la latence du bot")
    async def ping(self, interaction: discord.Interaction) -> None:
        latency_ms = round(self.bot.latency * 1000)
        color = (
            COLOR_OK if latency_ms < 100
            else COLOR_WARN if latency_ms < 250
            else discord.Color.red()
        )
        embed = discord.Embed(
            title="🏓 Pong !",
            description=f"Latence WebSocket : **{latency_ms} ms**",
            color=color,
        )
        await interaction.response.send_message(embed=embed)

    # ── /serverinfo ───────────────────────────────────────────────────────────

    @app_commands.command(name="serverinfo", description="Affiche les informations du serveur")
    async def serverinfo(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild

        # Comptage des salons par type
        text_channels  = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories     = len(guild.categories)

        # Comptage des membres
        total  = guild.member_count
        bots   = sum(1 for m in guild.members if m.bot)
        humans = total - bots

        created_at_ts = int(guild.created_at.timestamp())

        embed = discord.Embed(
            title=f"🏠 {guild.name}",
            color=COLOR_INFO,
            timestamp=datetime.now(tz=timezone.utc),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if guild.banner:
            embed.set_image(url=guild.banner.url)

        embed.add_field(name="👑 Propriétaire", value=str(guild.owner), inline=True)
        embed.add_field(name="🆔 ID", value=str(guild.id), inline=True)
        embed.add_field(name="📅 Créé le", value=f"<t:{created_at_ts}:D> (<t:{created_at_ts}:R>)", inline=False)
        embed.add_field(name="👥 Membres", value=f"{total} total · {humans} humains · {bots} bots", inline=False)
        embed.add_field(name="💬 Salons", value=f"{text_channels} texte · {voice_channels} vocal · {categories} catégories", inline=False)
        embed.add_field(name="🎭 Rôles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="😀 Emojis", value=str(len(guild.emojis)), inline=True)
        embed.add_field(name="🔐 Vérification", value=str(guild.verification_level).capitalize(), inline=True)

        if guild.premium_subscription_count:
            embed.add_field(
                name="💎 Boosts",
                value=f"{guild.premium_subscription_count} boost(s) · Niveau {guild.premium_tier}",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    # ── /userinfo ─────────────────────────────────────────────────────────────

    @app_commands.command(name="userinfo", description="Affiche les informations d'un membre")
    @app_commands.describe(membre="Membre à inspecter (vous-même par défaut)")
    async def userinfo(
        self,
        interaction: discord.Interaction,
        membre: discord.Member | None = None,
    ) -> None:
        target = membre or interaction.user

        created_ts = int(target.created_at.timestamp())
        joined_ts  = int(target.joined_at.timestamp()) if target.joined_at else 0

        # Rôles (on enlève @everyone)
        roles = [r.mention for r in reversed(target.roles) if r.name != "@everyone"]
        roles_str = " ".join(roles[:15]) if roles else "Aucun"
        if len(target.roles) > 16:
            roles_str += f" … (+{len(target.roles) - 16})"

        badges = []
        if target.bot:
            badges.append("🤖 Bot")
        if target.guild_permissions.administrator:
            badges.append("🛡️ Admin")
        if target.premium_since:
            badges.append("💎 Booster")

        embed = discord.Embed(
            title=f"👤 {target.display_name}",
            color=target.color if target.color != discord.Color.default() else COLOR_INFO,
            timestamp=datetime.now(tz=timezone.utc),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🏷️ Tag", value=str(target), inline=True)
        embed.add_field(name="🆔 ID", value=str(target.id), inline=True)
        embed.add_field(name="🎖️ Badges", value=" · ".join(badges) if badges else "Aucun", inline=True)
        embed.add_field(name="📅 Compte créé", value=f"<t:{created_ts}:D> (<t:{created_ts}:R>)", inline=False)
        if joined_ts:
            embed.add_field(name="📥 A rejoint le", value=f"<t:{joined_ts}:D> (<t:{joined_ts}:R>)", inline=False)
        embed.add_field(name=f"🎭 Rôles ({len(roles)})", value=roles_str, inline=False)

        await interaction.response.send_message(embed=embed)

    # ── /clear ────────────────────────────────────────────────────────────────

    @app_commands.command(name="clear", description="Supprime des messages (max 100)")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(
        nombre="Nombre de messages à supprimer (1–100)",
        membre="Supprimer uniquement les messages de ce membre (optionnel)",
    )
    async def clear(
        self,
        interaction: discord.Interaction,
        nombre: app_commands.Range[int, 1, 100],
        membre: discord.Member | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        def check(msg: discord.Message) -> bool:
            return membre is None or msg.author == membre

        try:
            deleted = await interaction.channel.purge(limit=nombre, check=check)
            qualifier = f" de {membre.display_name}" if membre else ""
            embed = discord.Embed(
                description=f"🗑️ **{len(deleted)}** message(s){qualifier} supprimé(s).",
                color=COLOR_OK,
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(
                f"[{interaction.guild}] {len(deleted)} messages supprimés par {interaction.user}"
                + (f" (filtre: {membre})" if membre else "")
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Je n'ai pas la permission de supprimer des messages.", ephemeral=True
            )

    # ── /avatar ───────────────────────────────────────────────────────────────

    @app_commands.command(name="avatar", description="Affiche l'avatar d'un membre en grand")
    @app_commands.describe(membre="Membre dont afficher l'avatar (vous-même par défaut)")
    async def avatar(
        self,
        interaction: discord.Interaction,
        membre: discord.Member | None = None,
    ) -> None:
        target = membre or interaction.user
        embed = discord.Embed(
            title=f"🖼️ Avatar de {target.display_name}",
            color=COLOR_INFO,
        )
        embed.set_image(url=target.display_avatar.with_size(1024).url)
        embed.add_field(
            name="Liens",
            value=" | ".join([
                f"[PNG]({target.display_avatar.with_format('png').url})",
                f"[JPG]({target.display_avatar.with_format('jpg').url})",
                f"[WEBP]({target.display_avatar.with_format('webp').url})",
            ]),
        )
        await interaction.response.send_message(embed=embed)

    # ── /setup ────────────────────────────────────────────────────────────────

    setup_group = app_commands.Group(
        name="setup",
        description="Configuration centralisée du bot",
        default_permissions=discord.Permissions(administrator=True),
    )

    @setup_group.command(name="staff-role", description="Définit le rôle staff")
    @app_commands.describe(role="Rôle qui aura les accès staff")
    async def setup_staff_role(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        self.db.upsert_guild_config(interaction.guild_id, staff_role=role.id)
        await interaction.response.send_message(
            f"✅ Rôle staff défini sur {role.mention}", ephemeral=True
        )

    @setup_group.command(name="log-channel", description="Définit le salon de logs")
    @app_commands.describe(channel="Salon où envoyer les logs du bot")
    async def setup_log_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        self.db.upsert_guild_config(interaction.guild_id, log_channel=channel.id)
        await interaction.response.send_message(
            f"✅ Salon de logs défini sur {channel.mention}", ephemeral=True
        )

    @setup_group.command(name="view", description="Affiche la configuration complète du serveur")
    async def setup_view(self, interaction: discord.Interaction) -> None:
        config = self.db.get_guild_config(interaction.guild_id)

        def resolve_channel(cid) -> str:
            if not cid:
                return "❌ Non configuré"
            ch = interaction.guild.get_channel(cid)
            return ch.mention if ch else f"❌ Introuvable (ID: {cid})"

        def resolve_role(rid) -> str:
            if not rid:
                return "❌ Non configuré"
            r = interaction.guild.get_role(rid)
            return r.mention if r else f"❌ Introuvable (ID: {rid})"

        def resolve_category(cid) -> str:
            if not cid:
                return "❌ Non configuré"
            cat = interaction.guild.get_channel(cid)
            return f"📁 {cat.name}" if cat else f"❌ Introuvable (ID: {cid})"

        embed = discord.Embed(
            title="⚙️ Configuration du serveur",
            color=COLOR_INFO,
            timestamp=datetime.now(tz=timezone.utc),
        )
        embed.add_field(name="🎉 Bienvenue", value=resolve_channel(config["welcome_channel"] if config else None), inline=True)
        embed.add_field(name="📢 Annonces", value=resolve_channel(config["announce_channel"] if config else None), inline=True)
        embed.add_field(name="📜 Logs", value=resolve_channel(config["log_channel"] if config else None), inline=True)
        embed.add_field(name="🎫 Catégorie tickets", value=resolve_category(config["ticket_category"] if config else None), inline=True)
        embed.add_field(name="🛡️ Rôle staff", value=resolve_role(config["staff_role"] if config else None), inline=True)
        embed.set_footer(text=f"Bot v1.0.0 · Python {platform.python_version()} · discord.py")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UtilsCog(bot))
