import { InteractionContextType, MessageFlags, SlashCommandBuilder } from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import logger from "../../logger";

const translations = LocaleHelper.getCommandTranslations("logging");

const LoggingCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("logging")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("Configure logging level.")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild])
    .addStringOption((option) =>
      option
        .setName("level")
        .setNameLocalizations(translations.options!.level!.localizedNames)
        .setDescription("Logging level to set.")
        .setDescriptionLocalizations(translations.options!.level!.localizedDescriptions)
        .setRequired(true)
        .addChoices(
          { name: "error", value: "error" },
          { name: "warn", value: "warn" },
          { name: "info", value: "info" },
          { name: "debug", value: "debug" }
        )
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

    const level = interaction.options.getString("level", true);

    try {
      logger.level = level;

      await interaction.reply({
        content: (
          translations.responses?.success?.[interaction.locale] ?? "Successfully set logging level to {level}."
        ).replace("{level}", level),
        flags: [MessageFlags.Ephemeral],
      });
    } catch (error) {
      logger.error("Error setting logging level: %o", error);
      await interaction.reply({
        content:
          translations.responses?.error?.[interaction.locale] ?? "An error occurred while setting the logging level.",
        flags: [MessageFlags.Ephemeral],
      });
    }
  },
};

export default LoggingCommand;
