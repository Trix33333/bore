"""
cogs/cog_tickets.py — Système de tickets complet.

Fonctionnalités :
- /ticket open [raison]       → Crée un salon privé dans la catégorie dédiée
- /ticket close               → Ferme le ticket avec transcript + confirmation
- /ticket add <@user>         → Ajoute un utilisateur au ticket
- /ticket remove <@user>      → Retire un utilisateur du ticket
- Bouton "Fermer" via View persistante
- Transcript sauvegardé en BDD avant suppression
"""

import asyncio
import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("bot.tickets")

COLOR_OPEN    = discord.Color.from_rgb(88, 196, 120)
COLOR_CLOSE   = discord.Color.from_rgb(237, 100, 100)
COLOR_INFO    = discord.Color.from_rgb(100, 149, 237)


# ── Vue persistante de confirmation de fermeture ──────────────────────────────

class TicketCloseView(discord.ui.View):
    """Boutons de confirmation de fermeture d'un ticket."""

    def __init__(self, cog: "TicketsCog") -> None:
        super().__init__(timeout=300)  # 5 min pour répondre
        self.cog = cog

    @discord.ui.button(label="✅ Confirmer la fermeture", style=discord.ButtonStyle.danger, custom_id="ticket_confirm_close")
    async def confirm_close(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Génère le transcript, log dans la BDD, et supprime le salon."""
        await interaction.response.defer()
        await self.cog._do_close_ticket(interaction)

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.secondary, custom_id="ticket_cancel_close")
    async def cancel_close(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_message("↩️ Fermeture annulée.", ephemeral=True)
        self.stop()


# ── Cog principal ─────────────────────────────────────────────────────────────

class TicketsCog(commands.Cog, name="Tickets"):
    """Cog du système de tickets."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def db(self):
        return self.bot.db  # type: ignore

    def _staff_overwrites(
        self, guild: discord.Guild, staff_role_id: int | None
    ) -> dict:
        """Construit les permissions de base pour un salon de ticket."""
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_channels=True,
                attach_files=True,
            ),
        }
        if staff_role_id:
            staff_role = guild.get_role(staff_role_id)
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=True, attach_files=True
                )
        return overwrites

    async def _generate_transcript(self, channel: discord.TextChannel) -> str:
        """Génère un transcript texte des messages du salon."""
        lines = [
            f"=== TRANSCRIPT — #{channel.name} ===",
            f"Serveur  : {channel.guild.name}",
            f"Salon    : #{channel.name}",
            f"Généré le: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
            "=" * 50,
            "",
        ]
        async for msg in channel.history(limit=500, oldest_first=True):
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            content = msg.content or "[embed/fichier sans texte]"
            lines.append(f"[{timestamp}] {msg.author} : {content}")
            for att in msg.attachments:
                lines.append(f"  📎 Fichier : {att.url}")

        return "\n".join(lines)

    async def _do_close_ticket(self, interaction: discord.Interaction) -> None:
        """Logique de fermeture effective d'un ticket."""
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return

        ticket = self.db.get_ticket_by_channel(channel.id)
        if not ticket:
            await interaction.followup.send("❌ Ce salon n'est pas un ticket.", ephemeral=True)
            return

        # Génération du transcript
        try:
            transcript = await self._generate_transcript(channel)
            self.db.save_transcript(ticket["ticket_id"], transcript)
            self.db.close_ticket(channel.id)
            logger.info(f"[{interaction.guild}] Ticket #{channel.name} fermé par {interaction.user}")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du transcript : {e}", exc_info=True)

        # Log dans le salon de logs
        config = self.db.get_guild_config(interaction.guild_id)
        if config and config["log_channel"]:
            log_ch = interaction.guild.get_channel(config["log_channel"])
            if isinstance(log_ch, discord.TextChannel):
                creator = interaction.guild.get_member(ticket["creator_id"])
                embed = discord.Embed(
                    title="🎫 Ticket fermé",
                    color=COLOR_CLOSE,
                    timestamp=datetime.utcnow(),
                )
                embed.add_field(name="Salon", value=channel.name, inline=True)
                embed.add_field(name="Créé par", value=str(creator) if creator else str(ticket["creator_id"]), inline=True)
                embed.add_field(name="Fermé par", value=str(interaction.user), inline=True)
                embed.add_field(name="Ouvert le", value=ticket["created_at"], inline=True)
                embed.set_footer(text=f"Ticket ID: {ticket['ticket_id']}")
                try:
                    # Envoi du transcript en fichier attaché
                    transcript_bytes = transcript.encode("utf-8")
                    file = discord.File(
                        fp=__import__("io").BytesIO(transcript_bytes),
                        filename=f"transcript_{channel.name}.txt",
                    )
                    await log_ch.send(embed=embed, file=file)
                except Exception as e:
                    logger.warning(f"Impossible d'envoyer le log de fermeture : {e}")

        # Message avant suppression
        await interaction.followup.send("🔒 Fermeture du ticket dans 5 secondes…")
        await asyncio.sleep(5)

        try:
            await channel.delete(reason=f"Ticket fermé par {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send("❌ Je n'ai pas la permission de supprimer ce salon.")

    # ── Slash Commands ────────────────────────────────────────────────────────

    ticket_group = app_commands.Group(
        name="ticket",
        description="Gestion des tickets de support",
    )

    @ticket_group.command(name="open", description="Ouvre un ticket de support")
    @app_commands.describe(raison="Raison de votre ticket (optionnel)")
    async def ticket_open(
        self,
        interaction: discord.Interaction,
        raison: str = "Aucune raison précisée",
    ) -> None:
        """Crée un salon de ticket privé pour l'utilisateur."""
        await interaction.response.defer(ephemeral=True)

        config = self.db.get_guild_config(interaction.guild_id)
        if not config or not config["ticket_category"]:
            await interaction.followup.send(
                "❌ Le système de tickets n'est pas configuré. Utilisez `/setup ticket-category`.",
                ephemeral=True,
            )
            return

        category = interaction.guild.get_channel(config["ticket_category"])
        if not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(
                "❌ La catégorie de tickets est introuvable. Vérifiez la configuration.",
                ephemeral=True,
            )
            return

        # Vérification : ticket déjà ouvert pour cet utilisateur dans cette catégorie
        for channel in category.channels:
            existing = self.db.get_ticket_by_channel(channel.id)
            if existing and existing["creator_id"] == interaction.user.id and existing["status"] == "open":
                await interaction.followup.send(
                    f"❌ Vous avez déjà un ticket ouvert : {channel.mention}", ephemeral=True
                )
                return

        # Permissions du salon
        overwrites = self._staff_overwrites(interaction.guild, config["staff_role"])
        overwrites[interaction.user] = discord.PermissionOverwrite(
            read_messages=True, send_messages=True, attach_files=True
        )

        # Nom du salon : ticket-username (normalisé)
        safe_name = "".join(
            c for c in interaction.user.name.lower() if c.isalnum() or c == "-"
        )[:20]
        channel_name = f"ticket-{safe_name}"

        try:
            ticket_channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                topic=f"Ticket de {interaction.user} | {raison}",
                reason=f"Ticket ouvert par {interaction.user}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Je n'ai pas la permission de créer des salons dans cette catégorie.",
                ephemeral=True,
            )
            return

        # Enregistrement en BDD
        ticket_id = self.db.create_ticket(
            interaction.guild_id, ticket_channel.id, interaction.user.id
        )

        # Message d'accueil dans le ticket
        embed = discord.Embed(
            title="🎫 Ticket ouvert",
            description=(
                f"Bonjour {interaction.user.mention} !\n\n"
                f"**Raison :** {raison}\n\n"
                "Notre équipe vous répondra dès que possible.\n"
                "Utilisez `/ticket close` pour fermer ce ticket."
            ),
            color=COLOR_OPEN,
            timestamp=datetime.utcnow(),
        )
        embed.set_footer(text=f"Ticket #{ticket_id} • {interaction.guild.name}")

        view = TicketCloseView(self)
        await ticket_channel.send(
            content=interaction.user.mention, embed=embed, view=view
        )

        await interaction.followup.send(
            f"✅ Votre ticket a été ouvert : {ticket_channel.mention}", ephemeral=True
        )

        # Log d'ouverture
        config = self.db.get_guild_config(interaction.guild_id)
        if config and config["log_channel"]:
            log_ch = interaction.guild.get_channel(config["log_channel"])
            if isinstance(log_ch, discord.TextChannel):
                log_embed = discord.Embed(
                    title="🎫 Ticket ouvert",
                    color=COLOR_OPEN,
                    timestamp=datetime.utcnow(),
                )
                log_embed.add_field(name="Créateur", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="Salon", value=ticket_channel.mention, inline=True)
                log_embed.add_field(name="Raison", value=raison, inline=False)
                try:
                    await log_ch.send(embed=log_embed)
                except discord.Forbidden:
                    pass

        logger.info(f"[{interaction.guild}] Ticket #{ticket_id} ouvert par {interaction.user}")

    @ticket_group.command(name="close", description="Ferme le ticket actuel")
    async def ticket_close(self, interaction: discord.Interaction) -> None:
        """Demande confirmation avant de fermer le ticket."""
        ticket = self.db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            await interaction.response.send_message(
                "❌ Cette commande doit être utilisée dans un salon de ticket.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="⚠️ Fermeture du ticket",
            description=(
                "Êtes-vous sûr de vouloir fermer ce ticket ?\n"
                "Un **transcript** sera sauvegardé, puis le salon sera supprimé."
            ),
            color=COLOR_CLOSE,
        )
        view = TicketCloseView(self)
        await interaction.response.send_message(embed=embed, view=view)

    @ticket_group.command(name="add", description="Ajoute un membre au ticket")
    @app_commands.describe(membre="Membre à ajouter au ticket")
    async def ticket_add(
        self, interaction: discord.Interaction, membre: discord.Member
    ) -> None:
        """Donne accès à un utilisateur dans le salon de ticket."""
        ticket = self.db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            await interaction.response.send_message(
                "❌ Cette commande doit être utilisée dans un salon de ticket.", ephemeral=True
            )
            return

        # Vérif : seul le créateur ou le staff peut ajouter
        config = self.db.get_guild_config(interaction.guild_id)
        is_staff = (
            interaction.user.guild_permissions.manage_channels  # type: ignore
            or (config and config["staff_role"] and any(
                r.id == config["staff_role"] for r in interaction.user.roles  # type: ignore
            ))
        )
        is_creator = interaction.user.id == ticket["creator_id"]

        if not (is_staff or is_creator):
            await interaction.response.send_message(
                "❌ Seul le créateur du ticket ou le staff peut ajouter des membres.", ephemeral=True
            )
            return

        try:
            await interaction.channel.set_permissions(
                membre,
                read_messages=True,
                send_messages=True,
                attach_files=True,
                reason=f"Ajouté au ticket par {interaction.user}",
            )
            await interaction.response.send_message(
                f"✅ {membre.mention} a été ajouté au ticket."
            )
            logger.info(f"[{interaction.guild}] {membre} ajouté au ticket #{interaction.channel.name}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Je n'ai pas la permission de modifier les accès.", ephemeral=True
            )

    @ticket_group.command(name="remove", description="Retire un membre du ticket")
    @app_commands.describe(membre="Membre à retirer du ticket")
    async def ticket_remove(
        self, interaction: discord.Interaction, membre: discord.Member
    ) -> None:
        """Retire l'accès d'un utilisateur dans le salon de ticket."""
        ticket = self.db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            await interaction.response.send_message(
                "❌ Cette commande doit être utilisée dans un salon de ticket.", ephemeral=True
            )
            return

        if membre.id == ticket["creator_id"]:
            await interaction.response.send_message(
                "❌ Vous ne pouvez pas retirer le créateur du ticket.", ephemeral=True
            )
            return

        config = self.db.get_guild_config(interaction.guild_id)
        is_staff = (
            interaction.user.guild_permissions.manage_channels  # type: ignore
            or (config and config["staff_role"] and any(
                r.id == config["staff_role"] for r in interaction.user.roles  # type: ignore
            ))
        )

        if not is_staff:
            await interaction.response.send_message(
                "❌ Seul le staff peut retirer des membres.", ephemeral=True
            )
            return

        try:
            await interaction.channel.set_permissions(
                membre,
                overwrite=None,  # Supprime l'overwrite → retombe sur @everyone
                reason=f"Retiré du ticket par {interaction.user}",
            )
            await interaction.response.send_message(
                f"✅ {membre.mention} a été retiré du ticket."
            )
            logger.info(f"[{interaction.guild}] {membre} retiré du ticket #{interaction.channel.name}")
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Je n'ai pas la permission de modifier les accès.", ephemeral=True
            )

    # ── Configuration ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="ticket-setup",
        description="Configure la catégorie pour les tickets",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(category="Catégorie où créer les salons de tickets")
    async def ticket_setup(
        self,
        interaction: discord.Interaction,
        category: discord.CategoryChannel,
    ) -> None:
        self.db.upsert_guild_config(interaction.guild_id, ticket_category=category.id)
        embed = discord.Embed(
            description=f"✅ Catégorie de tickets définie sur **{category.name}**",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"[{interaction.guild}] Catégorie tickets → {category.name}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketsCog(bot))
