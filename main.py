"""
main.py — Point d'entrée du bot Discord communautaire.

⚠️ RAILWAY : Le système de fichiers est ÉPHÉMÈRE.
Les fichiers créés (SQLite, transcripts) seront perdus à chaque redéploiement.
→ Activez un Volume Railway (ex: monté sur /data) et changez DB_PATH ci-dessous.
→ Ou utilisez une base externe (PostgreSQL via Railway, Supabase, etc.).
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from database import Database


# ── Chargement des variables d'environnement ──────────────────────────────────
load_dotenv()

DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))

# ⚠️ RAILWAY VOLUME : changez ce chemin vers votre volume persistant, ex: /data/bot.db
DB_PATH: str = os.getenv("DB_PATH", "data/bot.db")

if not DISCORD_TOKEN:
    sys.exit("❌ DISCORD_TOKEN manquant dans les variables d'environnement.")


# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("bot")


# ── Intents requis ────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True


# ── Classe principale du Bot ──────────────────────────────────────────────────
class CommunityBot(commands.Bot):
    """Bot Discord communautaire avec gestion modulaire via Cogs."""

    def __init__(self) -> None:
        super().__init__(
            command_prefix="!",
            intents=intents,
            owner_id=OWNER_ID,
            help_command=None,
        )
        self.db_path = DB_PATH
        self.db: Database | None = None

    async def setup_hook(self) -> None:
        """Initialise la base de données et charge les cogs."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = Database(self.db_path)

        cogs_dir = Path(__file__).parent / "cogs"
        cog_files = sorted(cogs_dir.glob("cog_*.py"))

        for cog_path in cog_files:
            cog_module = f"cogs.{cog_path.stem}"
            try:
                await self.load_extension(cog_module)
                logger.info(f"✅ Cog chargé : {cog_module}")
            except Exception as e:
                logger.error(f"❌ Erreur chargement {cog_module} : {e}", exc_info=True)

        try:
            synced = await self.tree.sync()
            logger.info(f"🔄 {len(synced)} commande(s) synchronisée(s).")
        except Exception as e:
            logger.error(f"❌ Erreur sync commandes : {e}", exc_info=True)

    async def on_ready(self) -> None:
        """Appelé lorsque le bot est connecté et prêt."""
        logger.info(f"🤖 Connecté : {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} serveur(s) | /help",
            )
        )

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        """Gestion globale des erreurs des slash commands."""
        if isinstance(error, discord.app_commands.MissingPermissions):
            msg = "❌ Permissions insuffisantes."
        elif isinstance(error, discord.app_commands.BotMissingPermissions):
            missing = ", ".join(error.missing_permissions)
            msg = f"❌ Il me manque des permissions : `{missing}`"
        elif isinstance(error, discord.app_commands.CommandOnCooldown):
            msg = f"⏳ Réessayez dans **{error.retry_after:.1f}s**."
        else:
            msg = f"❌ Erreur : `{error}`"
            logger.error(f"Erreur commande : {error}", exc_info=True)

        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            pass

    async def close(self) -> None:
        """Ferme proprement le bot et la base de données."""
        logger.info("🛑 Arrêt en cours…")
        if hasattr(self, "db") and self.db is not None:
            self.db.close()
        await super().close()


def handle_signal(bot: CommunityBot, sig: int) -> None:
    """Gère les signaux d'arrêt (SIGTERM, SIGINT) pour un shutdown propre."""
    asyncio.get_event_loop().create_task(bot.close())


async def main() -> None:
    """Point d'entrée asynchrone du bot."""
    bot = CommunityBot()
    loop = asyncio.get_event_loop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, bot, sig)

    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
