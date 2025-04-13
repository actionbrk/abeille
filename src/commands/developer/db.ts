import { ChatInputCommandInteraction, InteractionContextType, MessageFlags, SlashCommandBuilder } from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import logger from "../../logger";
import { optimizeDatabase, rebuildIndexes } from "../../database/bee-database";

const translations = LocaleHelper.getCommandTranslations("db");

const DatabaseCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("db")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("Database maintenance commands.")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild])
    .addSubcommand((subcommand) =>
      subcommand
        .setName("optimize")
        .setNameLocalizations(translations.options!.optimize!.localizedNames)
        .setDescription("Optimize database indexes.")
        .setDescriptionLocalizations(translations.options!.optimize!.localizedDescriptions)
    )
    .addSubcommand((subcommand) =>
      subcommand
        .setName("rebuild")
        .setNameLocalizations(translations.options!.rebuild!.localizedNames)
        .setDescription("Rebuild database indexes.")
        .setDescriptionLocalizations(translations.options!.rebuild!.localizedDescriptions)
    ),
  async execute(interaction) {
    // Check if user is bot owner
    if (interaction.user.id !== process.env.OWNER_ID) {
      await interaction.reply({
        content: translations.responses?.notOwner?.[interaction.locale] ?? "Only the bot owner can use this command.",
        flags: [MessageFlags.Ephemeral],
      });
      return;
    }

    const subcommand = interaction.options.getSubcommand();
    const guildId = interaction.guildId!;

    await interaction.deferReply({ flags: [MessageFlags.Ephemeral] });

    try {
      switch (subcommand) {
        case "optimize":
          await handleOptimize(interaction, guildId);
          break;
        case "rebuild":
          await handleRebuild(interaction, guildId);
          break;
      }
    } catch (error) {
      logger.error("Error executing database command: %o", error);
      await interaction.editReply({
        content:
          translations.responses?.error?.[interaction.locale] ??
          "An error occurred while executing the database command.",
      });
    }
  },
};

export default DatabaseCommand;

async function handleOptimize(interaction: ChatInputCommandInteraction, guildId: string) {
  const startTime = Date.now();

  await optimizeDatabase(guildId);

  const duration = Date.now() - startTime;

  await interaction.editReply({
    content: (
      translations.responses?.optimizeSuccess?.[interaction.locale] ??
      "Successfully optimized database in {duration}ms."
    ).replace("{duration}", duration.toString()),
  });
}

async function handleRebuild(interaction: ChatInputCommandInteraction, guildId: string) {
  const startTime = Date.now();

  await rebuildIndexes(guildId);

  const duration = Date.now() - startTime;

  await interaction.editReply({
    content: (
      translations.responses?.rebuildSuccess?.[interaction.locale] ??
      "Successfully rebuilt database indexes in {duration}ms."
    ).replace("{duration}", duration.toString()),
  });
}
