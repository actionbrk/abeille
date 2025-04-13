import { InteractionContextType, MessageFlags, SlashCommandBuilder } from "discord.js";
import type { Command } from "../../models/command";
import { LocaleHelper } from "../../utils/locale-helper";
import { deleteUserMessage } from "../../database/bee-database";
import logger from "../../logger";

const translations = LocaleHelper.getCommandTranslations("delete");

const DeleteCommand: Command = {
  data: new SlashCommandBuilder()
    .setName("delete")
    .setNameLocalizations(translations.localizedNames)
    .setDescription("Delete a specific message from Abeille's database.")
    .setDescriptionLocalizations(translations.localizedDescriptions)
    .setContexts([InteractionContextType.Guild])
    .addStringOption((option) =>
      option
        .setName("message_id")
        .setNameLocalizations(translations.options!.message_id!.localizedNames)
        .setDescription("ID of the message to delete.")
        .setDescriptionLocalizations(translations.options!.message_id!.localizedDescriptions)
        .setRequired(true)
    ),
  async execute(interaction) {
    await interaction.deferReply({ flags: [MessageFlags.Ephemeral] });

    const guildId = interaction.guildId!;
    const userId = interaction.user.id;
    const messageId = interaction.options.getString("message_id", true);

    // Validate message ID format
    if (!/^\d+$/.test(messageId)) {
      await interaction.editReply({
        content:
          translations.responses?.invalidId?.[interaction.locale] ??
          "Invalid message ID format. Please provide a valid message ID.",
      });
      return;
    }

    try {
      const deleted = deleteUserMessage(guildId, userId, messageId);

      if (deleted) {
        await interaction.editReply({
          content:
            translations.responses?.success?.[interaction.locale] ??
            "Message has been deleted from Abeille's database.",
        });
        logger.info("User %s deleted message %s from guild %s", userId, messageId, guildId);
      } else {
        await interaction.editReply({
          content:
            translations.responses?.notFound?.[interaction.locale] ??
            "Message not found or you don't have permission to delete it.",
        });
      }
    } catch (error) {
      logger.error("Error deleting message: %o", error);
      await interaction.editReply({
        content:
          translations.responses?.error?.[interaction.locale] ??
          "An error occurred while trying to delete the message.",
      });
    }
  },
};

export default DeleteCommand;
